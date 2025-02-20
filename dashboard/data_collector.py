"""
Data Collector for Thoth Oracle Dashboard
Collects and processes real-time trading data from XRPL
"""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import logging
from collections import defaultdict
import websockets
from xrpl.clients import JsonRpcClient
from xrpl.models import AccountLines, BookOffers
from xrpl.utils import drops_to_xrp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataCollector:
    def __init__(self, client: JsonRpcClient, dashboard_state):
        self.client = client
        self.state = dashboard_state
        self.active_pairs = set()
        self.last_book_update = {}
        self.websocket = None
        
    async def start(self):
        """Start all data collection tasks."""
        tasks = [
            self.collect_trade_data(),
            self.monitor_order_books(),
            self.update_trust_lines(),
            self.calculate_market_metrics(),
            self.process_successful_trades()
        ]
        await asyncio.gather(*tasks)
    
    async def collect_trade_data(self):
        """Collect trade data from logs and XRPL."""
        while True:
            try:
                # Read from arbitrage opportunities log
                with open("logs/arbitrage_opportunities.log", "r") as f:
                    opportunities = [json.loads(line) for line in f.readlines()]
                
                # Read from successful trades log
                with open("logs/successful_trades.log", "r") as f:
                    trades = [json.loads(line) for line in f.readlines()]
                
                # Update active pairs
                for opp in opportunities:
                    if "details" in opp and "pair" in opp["details"]:
                        self.active_pairs.add(opp["details"]["pair"])
                
                # Process trades
                for trade in trades:
                    if trade["timestamp"] > self.state.last_processed_time:
                        self.process_trade(trade)
                
                # Update state
                self.state.last_processed_time = datetime.now().isoformat()
                
            except Exception as e:
                logger.error(f"Error collecting trade data: {e}")
            
            await asyncio.sleep(1)
    
    async def monitor_order_books(self):
        """Monitor order books for active trading pairs."""
        while True:
            try:
                for pair in self.active_pairs:
                    base, quote = pair.split("/")
                    
                    # Get order book data
                    book_offers = await self.client.request(BookOffers(
                        taker_gets={
                            "currency": base,
                            "issuer": self.get_issuer(base)
                        } if base != "XRP" else "XRP",
                        taker_pays={
                            "currency": quote,
                            "issuer": self.get_issuer(quote)
                        } if quote != "XRP" else "XRP"
                    ))
                    
                    if book_offers.is_successful():
                        # Process order book data
                        bids = []
                        asks = []
                        
                        for offer in book_offers.result.get("offers", []):
                            price = self.calculate_price(offer)
                            amount = self.calculate_amount(offer)
                            
                            if "Flags" in offer and offer["Flags"] & 0x80000:
                                asks.append({"price": price, "amount": amount})
                            else:
                                bids.append({"price": price, "amount": amount})
                        
                        # Sort and accumulate
                        bids.sort(key=lambda x: x["price"], reverse=True)
                        asks.sort(key=lambda x: x["price"])
                        
                        for i in range(1, len(bids)):
                            bids[i]["amount"] += bids[i-1]["amount"]
                        for i in range(1, len(asks)):
                            asks[i]["amount"] += asks[i-1]["amount"]
                        
                        # Store snapshot
                        snapshot = {
                            "timestamp": datetime.now().isoformat(),
                            "bids": bids,
                            "asks": asks
                        }
                        self.state.order_book_snapshots[pair].append(snapshot)
                        
                        # Keep only last hour of snapshots
                        cutoff = datetime.now() - timedelta(hours=1)
                        self.state.order_book_snapshots[pair] = [
                            s for s in self.state.order_book_snapshots[pair]
                            if datetime.fromisoformat(s["timestamp"]) > cutoff
                        ]
                        
            except Exception as e:
                logger.error(f"Error monitoring order books: {e}")
            
            await asyncio.sleep(5)
    
    async def update_trust_lines(self):
        """Update trust line information."""
        while True:
            try:
                for pair in self.active_pairs:
                    base, quote = pair.split("/")
                    
                    for currency in [base, quote]:
                        if currency != "XRP":
                            issuer = self.get_issuer(currency)
                            if issuer:
                                lines = await self.client.request(AccountLines(
                                    account=self.state.wallet_address,
                                    peer=issuer
                                ))
                                
                                if lines.is_successful():
                                    for line in lines.result.get("lines", []):
                                        if line["currency"] == currency:
                                            self.state.trust_line_stats[currency] = {
                                                "issuer": issuer,
                                                "limit": line["limit"],
                                                "balance": line["balance"]
                                            }
                
            except Exception as e:
                logger.error(f"Error updating trust lines: {e}")
            
            await asyncio.sleep(60)  # Update every minute
    
    async def calculate_market_metrics(self):
        """Calculate and update market metrics."""
        while True:
            try:
                # Calculate metrics from recent trades
                recent_trades = self.state.trade_history[-100:]  # Last 100 trades
                
                if recent_trades:
                    # Market impact
                    impacts = [t.get("market_impact", 0) for t in recent_trades]
                    self.state.avg_market_impact = sum(impacts) / len(impacts)
                    
                    # Execution probability
                    probs = [t.get("execution_probability", 0) for t in recent_trades]
                    self.state.avg_execution_prob = sum(probs) / len(probs)
                    
                    # Volatility
                    vols = [t.get("volatility", 0) for t in recent_trades]
                    self.state.avg_volatility = sum(vols) / len(vols)
                    
                    # Total liquidity
                    total_liquidity = 0
                    for pair in self.active_pairs:
                        if self.state.order_book_snapshots[pair]:
                            latest = self.state.order_book_snapshots[pair][-1]
                            total_liquidity += sum(b["amount"] for b in latest["bids"])
                    
                    self.state.total_liquidity = total_liquidity
                
            except Exception as e:
                logger.error(f"Error calculating market metrics: {e}")
            
            await asyncio.sleep(5)
    
    async def process_successful_trades(self):
        """Process successful trades from the log file."""
        while True:
            try:
                with open("logs/successful_trades.log", "r") as f:
                    for line in f:
                        trade = json.loads(line)
                        if trade["timestamp"] > self.state.last_trade_time:
                            # Update trade counts
                            self.state.total_trades += 1
                            if trade.get("success", False):
                                self.state.successful_trades += 1
                            else:
                                self.state.failed_trades += 1
                            
                            # Update profit
                            self.state.total_profit += float(trade["profit"])
                            
                            # Add to history
                            self.state.trade_history.append({
                                "timestamp": datetime.fromisoformat(trade["timestamp"]),
                                "pair": trade["pair"],
                                "profit": float(trade["profit"]),
                                "market_impact": trade["analysis"]["market_impact"],
                                "execution_prob": trade["analysis"]["execution_probability"],
                                "volatility": trade["analysis"]["volatility"]
                            })
                            
                            self.state.last_trade_time = trade["timestamp"]
                
            except Exception as e:
                logger.error(f"Error processing successful trades: {e}")
            
            await asyncio.sleep(1)
    
    def get_issuer(self, currency: str) -> Optional[str]:
        """Get issuer address for a currency."""
        # This should be implemented based on your exchange_issuers.py configuration
        pass
    
    def calculate_price(self, offer: Dict) -> float:
        """Calculate price from an offer."""
        taker_gets = (float(offer["TakerGets"]) / 1_000_000 
                     if isinstance(offer["TakerGets"], str)
                     else float(offer["TakerGets"]["value"]))
        
        taker_pays = (float(offer["TakerPays"]) / 1_000_000
                     if isinstance(offer["TakerPays"], str)
                     else float(offer["TakerPays"]["value"]))
        
        return taker_pays / taker_gets
    
    def calculate_amount(self, offer: Dict) -> float:
        """Calculate amount from an offer."""
        return (float(offer["TakerGets"]) / 1_000_000 
                if isinstance(offer["TakerGets"], str)
                else float(offer["TakerGets"]["value"]))

async def main():
    """Main entry point."""
    from app import app, state
    
    # Initialize client
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    # Create data collector
    collector = DataCollector(client, state)
    
    # Start data collection
    await collector.start()

if __name__ == "__main__":
    asyncio.run(main())
