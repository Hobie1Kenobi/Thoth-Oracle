"""
Flash Loan Agent Module
Handles flash loan operations and arbitrage opportunities on the XRPL.
"""

from decimal import Decimal
from typing import Dict, Optional
import logging
from xrpl.clients import JsonRpcClient
from xrpl.models import Payment, AccountInfo, BookOffers
from xrpl.wallet import Wallet
from xrpl.utils import xrp_to_drops
from integrations.web3_client import Web3Client
from integrations.across_bridge import AcrossBridgeClient
from integrations.hooks_client import XRPLHooksClient

logger = logging.getLogger(__name__)

class FlashLoanAgent:
    def __init__(
        self,
        web3_client: Optional[Web3Client] = None,
        bridge_client: Optional[AcrossBridgeClient] = None,
        hooks_client: Optional[XRPLHooksClient] = None
    ):
        """Initialize the Flash Loan Agent."""
        self.web3_client = web3_client
        self.bridge_client = bridge_client
        self.hooks_client = hooks_client
        
    async def execute_flash_loan(
        self,
        token_address: str,
        amount: Decimal,
        target_chain: int
    ) -> Dict:
        """Execute a flash loan on XRPL."""
        try:
            # Verify the hook account exists
            if not self.hooks_client:
                raise ValueError("Hooks client not initialized")
            
            hook_info = await self.hooks_client.client.request(
                AccountInfo(
                    account=self.hooks_client.hook_account
                )
            )
            
            if not hook_info or "error" in hook_info.result:
                raise ValueError(f"Hook account {self.hooks_client.hook_account} not found")
            
            # Check if there's enough liquidity
            book_offers = await self.hooks_client.client.request(
                BookOffers(
                    taker_gets={"currency": "XRP"},
                    taker_pays={
                        "currency": token_address,
                        "issuer": self.hooks_client.hook_account
                    }
                )
            )
            
            if not book_offers.result.get("offers"):
                raise ValueError("Insufficient liquidity in the pool")
            
            # Calculate optimal amount based on available liquidity
            available_liquidity = Decimal(book_offers.result["offers"][0]["TakerGets"])
            loan_amount = min(amount, available_liquidity)
            
            logger.info(f"Executing flash loan for {loan_amount} XRP")
            
            # Prepare flash loan parameters
            flash_loan_params = {
                "amount": str(loan_amount),
                "token": token_address,
                "target_chain": target_chain
            }
            
            # Execute flash loan via hook
            result = await self.hooks_client.execute_hook(
                "flash_loan",
                "borrow",
                flash_loan_params
            )
            
            if result.get("engine_result") == "tesSUCCESS":
                # Calculate profit
                fees = Decimal("0.001") * loan_amount  # 0.1% fee
                profit = loan_amount - fees
                
                return {
                    "status": "success",
                    "tx_hash": result["tx_hash"],
                    "amount": str(loan_amount),
                    "fees": str(fees),
                    "profit": str(profit)
                }
            else:
                logger.error(f"Flash loan failed: {result}")
                return {
                    "status": "failed",
                    "error": result.get("engine_result_message", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error executing flash loan: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def check_profitability(
        self,
        token_address: str,
        amount: Decimal,
        expected_profit: Decimal
    ) -> bool:
        """Check if a flash loan would be profitable."""
        try:
            # Get current fees
            fees = Decimal("0.001") * amount  # 0.1% fee
            
            # Get current market rates
            book_offers = await self.hooks_client.client.request(
                BookOffers(
                    taker_gets={"currency": "XRP"},
                    taker_pays={
                        "currency": token_address,
                        "issuer": self.hooks_client.hook_account
                    }
                )
            )
            
            if not book_offers.result.get("offers"):
                return False
            
            # Calculate potential profit
            market_rate = Decimal(book_offers.result["offers"][0]["quality"])
            potential_profit = (market_rate * amount) - amount - fees
            
            return potential_profit >= expected_profit
            
        except Exception as e:
            logger.error(f"Error checking profitability: {e}")
            return False
    
    async def monitor_pool_liquidity(self, token_address: str) -> Dict:
        """Monitor liquidity in the flash loan pool."""
        try:
            book_offers = await self.hooks_client.client.request(
                BookOffers(
                    taker_gets={"currency": "XRP"},
                    taker_pays={
                        "currency": token_address,
                        "issuer": self.hooks_client.hook_account
                    }
                )
            )
            
            total_liquidity = sum(
                Decimal(offer["TakerGets"])
                for offer in book_offers.result.get("offers", [])
            )
            
            return {
                "token": token_address,
                "total_liquidity": str(total_liquidity),
                "num_offers": len(book_offers.result.get("offers", [])),
                "timestamp": "now"
            }
            
        except Exception as e:
            logger.error(f"Error monitoring pool liquidity: {e}")
            return {
                "token": token_address,
                "error": str(e)
            }
    
    async def repay_flash_loan(
        self,
        token_address: str,
        amount: Decimal,
        loan_tx_hash: str
    ) -> Dict:
        """Repay a flash loan."""
        try:
            repay_params = {
                "amount": str(amount),
                "token": token_address,
                "loan_tx_hash": loan_tx_hash
            }
            
            result = await self.hooks_client.execute_hook(
                "flash_loan",
                "repay",
                repay_params
            )
            
            if result.get("engine_result") == "tesSUCCESS":
                return {
                    "status": "success",
                    "tx_hash": result["tx_hash"]
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("engine_result_message", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error repaying flash loan: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
