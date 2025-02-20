"""
Spot Trading Agent Module
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import BookOffers, AccountLines
from xrpl.utils import get_issuer_address
from agents.xrpl_amm_agent import XRPLAMMAgent
from config.test_wallets import TESTNET_URL, SPOT_TRADER_WALLET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/spot_trader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SpotTradingAgent:
    def __init__(
        self,
        client: JsonRpcClient,
        wallet: Optional[Wallet] = None,
        risk_threshold: float = 0.6,
        min_profit: Decimal = Decimal("0.01")
    ):
        """Initialize the Spot Trading Agent."""
        self.client = client
        self.wallet = wallet
        self.risk_threshold = risk_threshold
        self.min_profit = min_profit
        self.amm_agent = XRPLAMMAgent(client, wallet)
        
        # Initialize trade tracking
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = Decimal("0")
    
    def calculate_risk_score(self, opportunity: Dict) -> float:
        """Calculate risk score for an opportunity using multiple factors."""
        try:
            details = opportunity["details"]
            
            # Extract key metrics
            profit_percentage = Decimal(details["profit_percentage"])
            size = Decimal(details["size"])
            
            # Weight factors
            PROFIT_WEIGHT = 0.5
            SIZE_WEIGHT = 0.3
            TIME_WEIGHT = 0.2
            
            # Calculate component scores
            
            # Profit score - higher profit is better, but diminishing returns
            # Normalize to max 10% profit
            profit_score = float(min((profit_percentage / 10), 1.0))
            
            # Size score - prefer smaller trades initially for safety
            # Normalize to 1000 XRP max size
            size_ratio = float(size / Decimal("1000"))
            size_score = 1.0 - min(size_ratio, 1.0)  # Smaller size = higher score
            
            # Time-based score - prefer newer opportunities
            try:
                opportunity_time = datetime.fromisoformat(details["timestamp"])
                time_diff = (datetime.now() - opportunity_time).total_seconds()
                time_score = max(0.0, 1.0 - (time_diff / 60.0))  # Decay over 1 minute
            except (KeyError, ValueError):
                time_score = 0.5  # Default if no timestamp
            
            # Calculate weighted score
            risk_score = (
                profit_score * PROFIT_WEIGHT +
                size_score * SIZE_WEIGHT +
                time_score * TIME_WEIGHT
            )
            
            logger.debug(
                f"Risk components: profit={profit_score:.4f} ({profit_percentage}%), "
                f"size={size_score:.4f} ({size} XRP), "
                f"time={time_score:.4f}"
            )
            
            return risk_score
            
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Error calculating risk score: {e}")
            return 0.0
    
    async def analyze_opportunity(self, opportunity: Dict) -> Dict:
        """Analyze an arbitrage opportunity in detail."""
        try:
            details = opportunity["details"]
            pair = details["pair"].split("/")
            base_currency = pair[0]
            quote_currency = pair[1]
            
            # Get order book depth for buy side
            buy_exchange = details["buy_exchange"]
            buy_offers = await self.amm_agent.client.request(BookOffers(
                taker_gets={
                    "currency": base_currency.upper(),
                    "issuer": get_issuer_address(buy_exchange)
                } if base_currency.upper() != "XRP" else "XRP",
                taker_pays={
                    "currency": quote_currency.upper(),
                    "issuer": get_issuer_address(buy_exchange)
                } if quote_currency.upper() != "XRP" else "XRP"
            ))
            
            # Calculate market liquidity
            buy_liquidity = Decimal("0")
            if buy_offers.is_successful():
                for offer in buy_offers.result.get("offers", []):
                    if base_currency.upper() == "XRP":
                        amount = Decimal(offer["TakerGets"]) / Decimal("1000000")
                    else:
                        amount = Decimal(offer["TakerGets"]["value"])
                    buy_liquidity += amount
            
            # Calculate market impact
            size = Decimal(details["size"])
            market_impact = float(size / buy_liquidity) if buy_liquidity > 0 else 1.0
            
            # Calculate volatility using price data
            buy_price = Decimal(details["buy_price"])
            sell_price = Decimal(details["sell_price"])
            price_change = abs(buy_price - sell_price)
            avg_price = (buy_price + sell_price) / 2
            volatility = float(price_change / avg_price)
            
            # Get account lines for currency trust lines
            if base_currency.upper() != "XRP":
                trust_lines = await self.amm_agent.client.request(AccountLines(
                    account=self.wallet.classic_address,
                    peer=get_issuer_address(buy_exchange)
                ))
                has_trust_line = any(
                    line["currency"] == base_currency.upper()
                    for line in trust_lines.result.get("lines", [])
                )
            else:
                has_trust_line = True
            
            # Estimate execution probability
            execution_factors = [
                1.0 - market_impact,  # Market impact factor
                1.0 - volatility,     # Volatility factor
                0.9 if has_trust_line else 0.3,  # Trust line factor
                0.8 if buy_liquidity > size else 0.2  # Liquidity factor
            ]
            execution_prob = max(0.0, min(1.0, sum(execution_factors) / len(execution_factors)))
            
            # Calculate expected value
            profit = Decimal(details["profit"])
            expected_value = float(profit * Decimal(str(execution_prob)))
            
            analysis = {
                "market_impact": market_impact,
                "volatility": volatility,
                "execution_probability": execution_prob,
                "expected_value": expected_value,
                "buy_liquidity": str(buy_liquidity),
                "has_trust_line": has_trust_line,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.debug(f"Opportunity analysis: {analysis}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing opportunity: {str(e)}")
            return {}
    
    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute a trade based on an arbitrage opportunity."""
        try:
            details = opportunity["details"]
            pair = details["pair"].split("/")
            base_currency = pair[0]
            quote_currency = pair[1]
            
            # Extract exchanges
            buy_exchange = details["buy_exchange"]
            
            # Execute buy trade
            buy_result = await self.amm_agent.execute_trade_with_retry(
                base_currency=base_currency,
                quote_currency=quote_currency,
                exchange_name=buy_exchange,
                amount=Decimal(details["size"])
            )
            
            if not buy_result["success"]:
                logger.error(f"Buy trade failed: {buy_result['error']}")
                self.failed_trades += 1
                return False
            
            logger.info(f"Buy trade successful: {buy_result['hash']}")
            self.successful_trades += 1
            self.total_trades += 1
            
            # Update profit tracking
            try:
                profit = Decimal(details["profit"])
                self.total_profit += profit
                logger.info(f"Trade profit: {profit}, Total profit: {self.total_profit}")
            except (KeyError, ValueError, TypeError):
                logger.warning("Could not calculate profit for trade")
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            self.failed_trades += 1
            return False
    
    async def monitor_opportunities(self):
        """Monitor for arbitrage opportunities."""
        try:
            while True:
                try:
                    # Read latest opportunity
                    with open("logs/arbitrage_opportunities.log", "r") as f:
                        last_line = f.readlines()[-1]
                        opportunity = json.loads(last_line)
                    
                    # Analyze opportunity
                    analysis = await self.analyze_opportunity(opportunity)
                    
                    # Calculate risk score with analysis
                    risk_score = self.calculate_risk_score(opportunity)
                    
                    # Adjust risk score based on analysis
                    if analysis:
                        execution_prob = analysis.get("execution_probability", 0.0)
                        expected_value = analysis.get("expected_value", 0.0)
                        
                        # Blend risk score with execution probability
                        final_score = (risk_score * 0.7) + (execution_prob * 0.3)
                        
                        if final_score >= 0.6 and expected_value > 0:
                            logger.info(f"Found viable opportunity - Risk: {final_score:.4f}, Expected Value: {expected_value:.4f}")
                            
                            # Execute the trade
                            success = await self.execute_trade(opportunity)
                            
                            if success:
                                # Get and log transaction stats
                                stats = await self.amm_agent.get_transaction_stats()
                                logger.info(f"Transaction stats: {stats}")
                                
                                # Log successful trade details
                                with open("logs/successful_trades.log", "a") as f:
                                    trade_log = {
                                        "timestamp": datetime.now().isoformat(),
                                        "opportunity": opportunity,
                                        "analysis": analysis,
                                        "final_score": final_score,
                                        "stats": stats
                                    }
                                    f.write(json.dumps(trade_log) + "\n")
                        else:
                            logger.debug(f"Opportunity rejected - Score: {final_score:.4f}, Expected Value: {expected_value:.4f}")
                    
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in opportunities log")
                except IndexError:
                    logger.debug("No opportunities found")
                except Exception as e:
                    logger.error(f"Error processing opportunity: {e}")
                
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Stopping opportunity monitoring")
            raise
    
    def get_performance_stats(self) -> Dict:
        """Get agent performance statistics."""
        return {
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": self.successful_trades / self.total_trades if self.total_trades > 0 else 0,
            "total_profit": str(self.total_profit),
            "average_profit": str(self.total_profit / self.successful_trades) if self.successful_trades > 0 else "0",
            "last_update": datetime.now().isoformat()
        }

async def main():
    """Main entry point."""
    # Initialize client and wallet
    client = JsonRpcClient(TESTNET_URL)
    wallet = Wallet.from_seed(SPOT_TRADER_WALLET["seed"])
    
    # Create and start agent
    agent = SpotTradingAgent(client, wallet)
    logger.info("Starting spot trading agent...")
    
    try:
        await agent.monitor_opportunities()
    except Exception as e:
        logger.error(f"Agent error: {e}")
    finally:
        # Log final stats
        stats = agent.get_performance_stats()
        logger.info(f"Final performance stats: {stats}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down spot trading agent...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
