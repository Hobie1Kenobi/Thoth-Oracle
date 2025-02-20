"""
XRPL AMM Agent Module
Handles AMM interactions and liquidity pool operations on the XRPL.
"""

import asyncio
from decimal import Decimal
from typing import Dict, List, Optional
import logging
from xrpl.clients import JsonRpcClient
from xrpl.models import (
    AccountLines,
    BookOffers,
    Payment,
    AccountInfo
)

logger = logging.getLogger(__name__)

class XRPLAMMAgent:
    def __init__(self, client: JsonRpcClient):
        """Initialize the XRPL AMM Agent."""
        self.client = client
    
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
    
    async def get_pool_rates(
        self,
        base_currency: str,
        quote_currency: str,
        issuer: str
    ) -> Dict:
        """Get current exchange rates from the pool."""
        try:
            # Get asks (selling base for quote)
            asks = await self.client.request(
                BookOffers(
                    taker_gets={"currency": base_currency},
                    taker_pays={
                        "currency": quote_currency,
                        "issuer": issuer
                    }
                )
            )
            
            # Get bids (buying base with quote)
            bids = await self.client.request(
                BookOffers(
                    taker_gets={
                        "currency": quote_currency,
                        "issuer": issuer
                    },
                    taker_pays={"currency": base_currency}
                )
            )
            
            # Calculate rates
            ask_rate = float(asks.result["offers"][0]["quality"]) if asks.result["offers"] else None
            bid_rate = 1/float(bids.result["offers"][0]["quality"]) if bids.result["offers"] else None
            
            return {
                "pair": f"{base_currency}/{quote_currency}",
                "ask_rate": str(ask_rate) if ask_rate else None,
                "bid_rate": str(bid_rate) if bid_rate else None,
                "spread": str((ask_rate - bid_rate) / ask_rate) if ask_rate and bid_rate else None
            }
            
        except Exception as e:
            logger.error(f"Error getting pool rates: {e}")
            return {"error": str(e)}
    
    async def calculate_optimal_trade(
        self,
        base_currency: str,
        quote_currency: str,
        issuer: str,
        amount: Decimal
    ) -> Dict:
        """Calculate optimal trade parameters."""
        try:
            # Get current rates
            rates = await self.get_pool_rates(base_currency, quote_currency, issuer)
            if "error" in rates:
                return rates
            
            # Calculate optimal trade size based on pool liquidity
            book_offers = await self.client.request(
                BookOffers(
                    taker_gets={"currency": base_currency},
                    taker_pays={
                        "currency": quote_currency,
                        "issuer": issuer
                    }
                )
            )
            
            available_liquidity = Decimal(book_offers.result["offers"][0]["TakerGets"])
            optimal_size = min(amount, available_liquidity)
            
            # Calculate expected output
            ask_rate = Decimal(rates["ask_rate"]) if rates["ask_rate"] else Decimal("0")
            expected_output = optimal_size * ask_rate
            
            # Calculate fees
            fee_rate = Decimal("0.003")  # 0.3% fee
            fees = expected_output * fee_rate
            
            return {
                "optimal_input": str(optimal_size),
                "expected_output": str(expected_output),
                "fees": str(fees),
                "net_output": str(expected_output - fees),
                "rate": str(ask_rate)
            }
            
        except Exception as e:
            logger.error(f"Error calculating optimal trade: {e}")
            return {"error": str(e)}
    
    async def monitor_pool_health(
        self,
        pool_address: str,
        base_currency: str,
        quote_currency: str,
        issuer: str
    ) -> Dict:
        """Monitor pool health metrics."""
        try:
            # Get pool info
            pool_info = await self.get_pool_info(pool_address)
            if "error" in pool_info:
                return pool_info
            
            # Get current rates
            rates = await self.get_pool_rates(base_currency, quote_currency, issuer)
            if "error" in rates:
                return rates
            
            # Calculate health metrics
            total_liquidity_xrp = Decimal(pool_info["balance_xrp"])
            token_lines = [
                line for line in pool_info["lines"]
                if line["currency"] == quote_currency and line["account"] == issuer
            ]
            total_liquidity_token = Decimal(token_lines[0]["balance"]) if token_lines else Decimal("0")
            
            return {
                "address": pool_address,
                "liquidity_xrp": str(total_liquidity_xrp),
                "liquidity_token": str(total_liquidity_token),
                "spread": rates["spread"],
                "health_score": "high" if total_liquidity_xrp > 0 and total_liquidity_token > 0 else "low",
                "timestamp": "now"
            }
            
        except Exception as e:
            logger.error(f"Error monitoring pool health: {e}")
            return {"error": str(e)}
    
    async def get_arbitrage_paths(
        self,
        start_currency: str,
        issuer: str,
        min_profit: Decimal
    ) -> List[Dict]:
        """Find potential arbitrage paths."""
        try:
            paths = []
            
            # Get all trading pairs for the currency
            pairs = await self.get_trading_pairs(start_currency, issuer)
            
            for pair1 in pairs:
                quote1 = pair1["quote"]
                # Look for second leg opportunities
                for pair2 in pairs:
                    if pair2["base"] == quote1:
                        quote2 = pair2["quote"]
                        # Look for paths back to start
                        for pair3 in pairs:
                            if pair3["base"] == quote2 and pair3["quote"] == start_currency:
                                # Calculate potential profit
                                rates = await asyncio.gather(
                                    self.get_pool_rates(pair1["base"], pair1["quote"], issuer),
                                    self.get_pool_rates(pair2["base"], pair2["quote"], issuer),
                                    self.get_pool_rates(pair3["base"], pair3["quote"], issuer)
                                )
                                
                                if all(rate.get("ask_rate") for rate in rates):
                                    # Calculate triangular rate
                                    rate1 = Decimal(rates[0]["ask_rate"])
                                    rate2 = Decimal(rates[1]["ask_rate"])
                                    rate3 = Decimal(rates[2]["ask_rate"])
                                    
                                    tri_rate = rate1 * rate2 * rate3
                                    profit = (tri_rate - 1) * 100
                                    
                                    if profit > min_profit:
                                        paths.append({
                                            "path": [pair1, pair2, pair3],
                                            "rates": [str(rate) for rate in [rate1, rate2, rate3]],
                                            "profit": str(profit)
                                        })
            
            return paths
            
        except Exception as e:
            logger.error(f"Error finding arbitrage paths: {e}")
            return []
    
    async def get_trading_pairs(self, currency: str, issuer: str) -> List[Dict]:
        """Get all trading pairs for a currency."""
        try:
            book_offers = await self.client.request(
                BookOffers(
                    taker_gets={"currency": currency},
                    taker_pays={
                        "currency": currency,
                        "issuer": issuer
                    }
                )
            )
            
            pairs = []
            for offer in book_offers.result.get("offers", []):
                pairs.append({
                    "base": currency,
                    "quote": offer["TakerPays"]["currency"],
                    "issuer": issuer
                })
            
            return pairs
            
        except Exception as e:
            logger.error(f"Error getting trading pairs: {e}")
            return []
