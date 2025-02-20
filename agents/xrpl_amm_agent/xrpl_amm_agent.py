"""
XRPL AMM Agent Module
Handles AMM interactions and liquidity pool operations on the XRPL.
"""

import asyncio
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
import time
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import (
    AccountLines,
    BookOffers,
    AccountInfo,
    RipplePathFind
)
from xrpl.models.transactions import Payment
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.utils import xrp_to_drops
from config.exchange_issuers import (
    get_issuer_address,
    PATH_FINDING,
    TRANSACTION_MONITORING,
    RETRY_CONFIG
)

logger = logging.getLogger(__name__)

class TransactionMonitor:
    """Monitor and track transaction status."""
    
    def __init__(self):
        self.transactions = {}
        self.success_count = 0
        self.failure_count = 0
    
    def add_transaction(self, tx_hash: str, details: Dict):
        """Add a transaction to monitor."""
        self.transactions[tx_hash] = {
            "status": "pending",
            "timestamp": time.time(),
            "details": details,
            "retries": 0
        }
    
    def update_status(self, tx_hash: str, status: str, error: Optional[str] = None):
        """Update transaction status."""
        if tx_hash in self.transactions:
            self.transactions[tx_hash]["status"] = status
            if error:
                self.transactions[tx_hash]["error"] = error
            
            if status == "success":
                self.success_count += 1
            elif status == "failed":
                self.failure_count += 1
    
    def get_success_rate(self) -> float:
        """Get the success rate of transactions."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

class XRPLAMMAgent:
    def __init__(self, client: JsonRpcClient, wallet: Optional[Wallet] = None):
        """Initialize the XRPL AMM Agent."""
        self.sync_client = client
        self.client = AsyncJsonRpcClient(client.url)
        self.wallet = wallet
        self.monitor = TransactionMonitor()
        
    async def find_paths(
        self,
        source_currency: str,
        destination_currency: str,
        destination_issuer: str,
        amount: Decimal
    ) -> List[Dict]:
        """Find payment paths between currencies."""
        try:
            # Convert amount for XRP
            if destination_currency.upper() == "XRP":
                dest_amount = str(int(amount * Decimal("1000000")))
            else:
                dest_amount = {
                    "currency": destination_currency.upper(),
                    "value": str(amount),
                    "issuer": destination_issuer
                }
            
            # Request paths
            paths_req = RipplePathFind(
                source_account=self.wallet.classic_address,
                destination_account=self.wallet.classic_address,
                destination_amount=dest_amount
            )
            
            paths_result = await self.client.request(paths_req)
            
            if not paths_result.is_successful():
                logger.error(f"Path finding failed: {paths_result.result}")
                return []
                
            return paths_result.result.get("alternatives", [])
            
        except Exception as e:
            logger.error(f"Error finding paths: {e}")
            return []
    
    async def validate_issuer(self, exchange_name: str) -> Tuple[bool, str]:
        """Validate issuer address and check if it's active."""
        try:
            issuer_address = get_issuer_address(exchange_name)
            
            # Check if account exists and is active
            account_info = await self.client.request(
                AccountInfo(
                    account=issuer_address
                )
            )
            
            if account_info.is_successful():
                return True, issuer_address
            return False, f"Issuer account not found: {issuer_address}"
            
        except ValueError as ve:
            return False, str(ve)
        except Exception as e:
            return False, f"Error validating issuer: {e}"
    
    async def execute_trade_with_retry(
        self,
        base_currency: str,
        quote_currency: str,
        exchange_name: str,
        amount: Decimal
    ) -> Dict:
        """Execute trade with retry logic."""
        attempts = 0
        last_error = None
        
        while attempts < RETRY_CONFIG["max_attempts"]:
            try:
                # Validate issuer
                is_valid, issuer_result = await self.validate_issuer(exchange_name)
                if not is_valid:
                    return {
                        "success": False,
                        "error": issuer_result
                    }
                
                issuer = issuer_result
                
                # Find optimal paths
                paths = await self.find_paths(
                    base_currency,
                    quote_currency,
                    issuer,
                    amount
                )
                
                if not paths:
                    raise ValueError("No valid payment paths found")
                
                # Execute the trade
                result = await self.execute_trade(
                    base_currency,
                    quote_currency,
                    issuer,
                    amount,
                    paths[0]  # Use the first (usually best) path
                )
                
                if result["success"]:
                    self.monitor.add_transaction(
                        result["hash"],
                        {
                            "type": "trade",
                            "base": base_currency,
                            "quote": quote_currency,
                            "amount": str(amount)
                        }
                    )
                    return result
                
                last_error = result["error"]
                
            except Exception as e:
                last_error = str(e)
            
            # Calculate retry delay
            delay = min(
                RETRY_CONFIG["base_delay"] * (RETRY_CONFIG["exponential_base"] ** attempts),
                RETRY_CONFIG["max_delay"]
            )
            
            logger.warning(f"Retrying trade after {delay}s (attempt {attempts + 1})")
            await asyncio.sleep(delay)
            attempts += 1
        
        return {
            "success": False,
            "error": f"Max retry attempts reached. Last error: {last_error}"
        }
    
    async def execute_trade(
        self,
        base_currency: str,
        quote_currency: str,
        issuer: str,
        amount: Decimal,
        path: Optional[Dict] = None
    ) -> Dict:
        """Execute a trade on the XRPL DEX."""
        try:
            if not self.wallet:
                raise ValueError("Wallet required for trading")
            
            # Handle XRP special case for amount
            if base_currency.upper() == "XRP":
                payment_amount = str(int(amount * Decimal("1000000")))  # Convert to drops
            else:
                payment_amount = {
                    "currency": base_currency.upper(),
                    "value": str(amount),
                    "issuer": issuer
                }
            
            # Calculate send_max (1% slippage tolerance)
            if quote_currency.upper() == "XRP":
                send_max = str(int(amount * Decimal("1.01") * Decimal("1000000")))
            else:
                send_max = {
                    "currency": quote_currency.upper(),
                    "value": str(amount * Decimal("1.01")),
                    "issuer": issuer
                }
            
            # Create payment transaction
            payment = Payment(
                account=self.wallet.classic_address,
                destination=self.wallet.classic_address,
                amount=payment_amount,
                send_max=send_max,
                paths=path["paths_computed"] if path else None,
                flags=131072  # tfNoDirectRipple flag
            )
            
            logger.info(f"Submitting payment: {payment.to_dict()}")
            
            # Sign and submit transaction
            response = await submit_and_wait(
                transaction=payment,
                client=self.client,
                wallet=self.wallet
            )
            
            if response.result.get("validated", False):
                logger.info(f"Trade executed successfully: {response.result['hash']}")
                return {
                    "success": True,
                    "hash": response.result["hash"],
                    "amount": str(amount),
                    "path_used": path["paths_computed"] if path else None
                }
            else:
                logger.error(f"Trade validation failed: {response.result}")
                return {
                    "success": False,
                    "error": f"Transaction not validated: {response.result}"
                }
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_transaction_stats(self) -> Dict:
        """Get transaction statistics."""
        return {
            "success_rate": self.monitor.get_success_rate(),
            "total_success": self.monitor.success_count,
            "total_failed": self.monitor.failure_count,
            "pending_transactions": len([
                tx for tx in self.monitor.transactions.values()
                if tx["status"] == "pending"
            ])
        }
    
    async def get_pool_info(self, pool_address: str) -> Dict:
        """Get information about a liquidity pool."""
        try:
            # Get pool account info
            pool_info = await self.client.request(
                AccountInfo(
                    account=pool_address
                )
            )
            
            # Get pool balances
            pool_lines = await self.client.request(
                AccountLines(
                    account=pool_address
                )
            )
            
            return {
                "address": pool_address,
                "balance_xrp": pool_info.result["account_data"]["Balance"],
                "lines": pool_lines.result["lines"],
                "status": "active" if pool_info.result["validated"] else "pending"
            }
            
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return {"error": str(e)}
    
    async def get_pool_rates(self, base_currency: str, quote_currency: str, issuer: str) -> Dict:
        """Get current exchange rates from liquidity pool."""
        try:
            # Get order book offers
            offers = await self.client.request(
                BookOffers(
                    taker_gets={"currency": base_currency},
                    taker_pays={"currency": quote_currency, "issuer": issuer}
                )
            )
            
            if not offers.result.get("offers"):
                return None
                
            # Calculate rates and profit potential
            best_offer = offers.result["offers"][0]
            rate = Decimal(best_offer["quality"])
            optimal_size = self.calculate_optimal_size(rate)
            profit_potential = self.calculate_profit_potential(rate, optimal_size)
            
            return {
                "rate": str(rate),
                "optimal_size": str(optimal_size),
                "profit_potential": str(profit_potential)
            }
            
        except Exception as e:
            logger.error(f"Error getting pool rates: {e}")
            return None
    
    def calculate_optimal_size(self, rate: Decimal) -> Decimal:
        """Calculate optimal trade size based on rate."""
        # Simple implementation - can be enhanced with more sophisticated logic
        return Decimal("1000")  # Default to 1000 XRP for now
    
    def calculate_profit_potential(self, rate: Decimal, size: Decimal) -> Decimal:
        """Calculate potential profit for a trade."""
        # Simple implementation - can be enhanced with more sophisticated logic
        return rate * size * Decimal("0.01")  # Assume 1% profit
