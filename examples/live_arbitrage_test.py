"""
Live Arbitrage Testing Script
Tests the Thoth Oracle system with live market data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List
import os
from datetime import datetime
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet

from agents.xrpl_amm_agent import XRPLAMMAgent
from agents.flash_loan_agent import FlashLoanAgent
from agents.risk_management_agent import RiskManagementAgent
from agents.monitoring_agent import MonitoringAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('arbitrage_opportunities.log')
    ]
)
logger = logging.getLogger(__name__)

# Common issuers
ISSUERS = {
    "Bitstamp": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",
    "Gatehub": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
    "GateHub_Five": "rchGBxcD1A1C2tdxF6papQYZ8kjRKMYcL",
    "Ripple": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
    "RippleGateway": "rf1BiGeXwwQoi8Z2ueFYTEXSwuJYfV2Jpn",
    "Bitso": "rG6FZ31hDHN1K5Dkbma3PSB5uVCuVVRzfn"
}

# Additional common currencies
CURRENCIES = {
    "FIAT": ["USD", "EUR", "JPY", "GBP"],
    "CRYPTO": ["XRP", "BTC", "ETH", "LTC", "BCH", "XLM"],
    "STABLECOIN": ["USDT", "USDC", "BUSD", "DAI"]
}

class ArbitrageTrader:
    """Main trader class that coordinates all agents."""
    
    def __init__(self, wallet_seed: str):
        """Initialize the arbitrage trader."""
        # Initialize XRPL client
        self.client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
        self.wallet = Wallet.from_seed(wallet_seed)
        
        # Initialize agents
        self.amm_agent = XRPLAMMAgent(self.client, self.wallet)
        self.flash_loan_agent = FlashLoanAgent(self.client, self.wallet)
        self.risk_agent = RiskManagementAgent()
        self.monitoring_agent = MonitoringAgent()
        
        # Trading pairs to monitor (dynamically generated)
        self.pairs = self._generate_trading_pairs()
        
        # Opportunity detection parameters
        self.min_profit_threshold = Decimal("0.0008")  # 0.08% minimum profit
        self.min_triangular_profit = Decimal("0.0015") # 0.15% for triangular
        self.min_liquidity = Decimal("1000")          # Minimum liquidity in USD
        self.max_slippage = Decimal("0.005")          # Maximum 0.5% slippage
        
        # Analytics
        self.opportunity_stats = {
            "direct": {
                "total_found": 0,
                "total_profit_potential": Decimal("0"),
                "best_profit_percentage": Decimal("0"),
                "most_profitable_pair": None,
                "best_exchanges": None
            },
            "triangular": {
                "total_found": 0,
                "total_profit_potential": Decimal("0"),
                "best_profit_percentage": Decimal("0"),
                "most_profitable_path": None,
                "best_exchange": None
            }
        }
        
        # Trading state
        self.is_running = False
        self.opportunities = []
        
    def _generate_trading_pairs(self) -> List[Dict]:
        """Dynamically generate trading pairs."""
        pairs = []
        
        # Generate pairs for each issuer
        for issuer_name, issuer_address in ISSUERS.items():
            # Add major pairs
            for base in CURRENCIES["CRYPTO"]:
                # Crypto to Fiat
                for quote in CURRENCIES["FIAT"]:
                    pairs.append({
                        "base": base,
                        "quote": quote,
                        "issuer": issuer_address
                    })
                
                # Crypto to Crypto
                for quote in CURRENCIES["CRYPTO"]:
                    if base != quote:
                        pairs.append({
                            "base": base,
                            "quote": quote,
                            "issuer": issuer_address
                        })
                
                # Crypto to Stablecoin
                for quote in CURRENCIES["STABLECOIN"]:
                    pairs.append({
                        "base": base,
                        "quote": quote,
                        "issuer": issuer_address
                    })
        
        return pairs

    def log_opportunity(self, type: str, details: Dict):
        """Log an arbitrage opportunity."""
        timestamp = datetime.now().isoformat()
        opportunity = {
            "timestamp": timestamp,
            "type": type,
            **details
        }
        self.opportunities.append(opportunity)
        
        # Update analytics
        stats = self.opportunity_stats[type]
        profit_percentage = Decimal(details["profit_percentage"])
        
        stats["total_found"] += 1
        stats["total_profit_potential"] += Decimal(details["profit"])
        
        if profit_percentage > stats["best_profit_percentage"]:
            stats["best_profit_percentage"] = profit_percentage
            if type == "direct":
                stats["most_profitable_pair"] = details["pair"]
                stats["best_exchanges"] = (details["buy_exchange"], details["sell_exchange"])
            else:
                stats["most_profitable_path"] = details["path"]
                stats["best_exchange"] = details["exchanges"]
        
        # Enhanced logging
        if type == "direct":
            logger.info(
                f"\n{'='*50}\n"
                f"Direct Arbitrage Opportunity Found!\n"
                f"{'='*50}\n"
                f"Pair: {details['pair']}\n"
                f"Buy Exchange: {details['buy_exchange']} @ {details['buy_rate']}\n"
                f"Sell Exchange: {details['sell_exchange']} @ {details['sell_rate']}\n"
                f"Size: {details['size']} {details['base_currency']}\n"
                f"Potential Profit: {details['profit']} {details['quote_currency']}\n"
                f"Profit Percentage: {details['profit_percentage']}%\n"
                f"Estimated Slippage: {details.get('estimated_slippage', 'N/A')}%\n"
                f"Liquidity Score: {details.get('liquidity_score', 'N/A')}/10\n"
                f"{'='*50}\n"
            )
        elif type == "triangular":
            logger.info(
                f"\n{'='*50}\n"
                f"Triangular Arbitrage Opportunity Found!\n"
                f"{'='*50}\n"
                f"Path: {details['path']}\n"
                f"Exchange: {details['exchanges']}\n"
                f"Initial Size: {details['initial_size']} {details['start_currency']}\n"
                f"Final Size: {details['final_size']} {details['start_currency']}\n"
                f"Potential Profit: {details['profit']} {details['start_currency']}\n"
                f"Profit Percentage: {details['profit_percentage']}%\n"
                f"Path Efficiency: {details.get('path_efficiency', 'N/A')}%\n"
                f"Execution Time Estimate: {details.get('execution_time_estimate', 'N/A')}ms\n"
                f"{'='*50}\n"
            )
    
    async def monitor_opportunities(self):
        """Monitor trading pairs for arbitrage opportunities."""
        while self.is_running:
            try:
                # Group rates by currency pair for cross-exchange comparison
                rates_by_pair = {}
                all_rates = {}  # Store all rates for triangular arbitrage
                
                for pair in self.pairs:
                    pair_key = f"{pair['base']}/{pair['quote']}"
                    
                    # Get pool rates
                    rates = await self.amm_agent.get_pool_rates(
                        pair["base"],
                        pair["quote"],
                        pair["issuer"]
                    )
                    
                    if rates:
                        # Store for direct arbitrage
                        if pair_key not in rates_by_pair:
                            rates_by_pair[pair_key] = []
                        rates_by_pair[pair_key].append({
                            "issuer": pair["issuer"],
                            "rates": rates
                        })
                        
                        # Store for triangular arbitrage
                        issuer_name = next(name for name, addr in ISSUERS.items() if addr == pair["issuer"])
                        key = f"{pair_key}@{issuer_name}"
                        all_rates[key] = {
                            "rate": Decimal(rates["rate"]),
                            "size": Decimal(rates["optimal_size"])
                        }
                
                # Check for direct arbitrage opportunities
                await self.check_direct_arbitrage(rates_by_pair)
                
                # Check for triangular arbitrage opportunities
                await self.check_triangular_arbitrage(all_rates)
                
                # Health check
                await self.monitoring_agent.log_health_check()
                
                # Wait before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await self.monitoring_agent.log_error("monitoring", str(e))
                await asyncio.sleep(5)  # Wait longer on error
    
    async def check_direct_arbitrage(self, rates_by_pair: Dict):
        """Check for direct arbitrage opportunities between exchanges."""
        for pair_key, exchange_rates in rates_by_pair.items():
            if len(exchange_rates) > 1:
                # Find best buy and sell rates
                best_buy = min(exchange_rates, key=lambda x: float(x["rates"]["rate"]))
                best_sell = max(exchange_rates, key=lambda x: float(x["rates"]["rate"]))
                
                # Calculate potential profit
                buy_rate = Decimal(best_buy["rates"]["rate"])
                sell_rate = Decimal(best_sell["rates"]["rate"])
                size = Decimal(best_buy["rates"]["optimal_size"])
                
                # Calculate profit metrics
                potential_profit = (sell_rate - buy_rate) * size
                profit_percentage = (potential_profit / (buy_rate * size)) * 100
                
                # Log if profit threshold is met
                if profit_percentage > self.min_profit_threshold:
                    buy_exchange = next(name for name, addr in ISSUERS.items() if addr == best_buy["issuer"])
                    sell_exchange = next(name for name, addr in ISSUERS.items() if addr == best_sell["issuer"])
                    
                    self.log_opportunity("direct", {
                        "pair": pair_key,
                        "base_currency": pair_key.split("/")[0],
                        "quote_currency": pair_key.split("/")[1],
                        "buy_exchange": buy_exchange,
                        "sell_exchange": sell_exchange,
                        "buy_rate": str(buy_rate),
                        "sell_rate": str(sell_rate),
                        "size": str(size),
                        "profit": str(potential_profit),
                        "profit_percentage": str(profit_percentage)
                    })
    
    async def check_triangular_arbitrage(self, all_rates: Dict):
        """Check for triangular arbitrage opportunities."""
        # Define common triangular paths
        paths = [
            # Classic paths
            ["XRP/BTC", "BTC/USD", "USD/XRP"],
            ["XRP/EUR", "EUR/USD", "USD/XRP"],
            ["BTC/ETH", "ETH/USD", "USD/BTC"],
            
            # Stablecoin paths
            ["USDT/USD", "USD/BTC", "BTC/USDT"],
            ["USDC/USD", "USD/ETH", "ETH/USDC"],
            
            # Cross-currency paths
            ["XRP/JPY", "JPY/USD", "USD/XRP"],
            ["BTC/EUR", "EUR/ETH", "ETH/BTC"],
            ["ETH/GBP", "GBP/USD", "USD/ETH"],
            
            # Alternative crypto paths
            ["LTC/BTC", "BTC/USD", "USD/LTC"],
            ["BCH/ETH", "ETH/USD", "USD/BCH"],
            ["XLM/XRP", "XRP/USD", "USD/XLM"],
            
            # Four-leg paths (more complex but potentially more profitable)
            ["XRP/BTC", "BTC/ETH", "ETH/USD", "USD/XRP"],
            ["BTC/ETH", "ETH/USDT", "USDT/USD", "USD/BTC"],
            ["ETH/EUR", "EUR/USD", "USD/BTC", "BTC/ETH"]
        ]
        
        for path in paths:
            for exchange in ISSUERS.keys():
                try:
                    rates = []
                    for pair in path:
                        rate_key = f"{pair}@{exchange}"
                        if rate_key in all_rates:
                            rates.append(all_rates[rate_key])
                    
                    if len(rates) == len(path):  # All rates found
                        # Calculate round trip with slippage consideration
                        initial_size = Decimal("1000")  # Start with 1000 units
                        current_size = initial_size
                        execution_times = []
                        
                        # Simulate the trades
                        for i, rate_info in enumerate(rates):
                            # Apply estimated slippage based on size
                            slippage = min(
                                self.max_slippage,
                                current_size / rate_info["size"] * Decimal("0.001")
                            )
                            effective_rate = rate_info["rate"] * (1 - slippage)
                            current_size *= effective_rate
                            execution_times.append(10)  # Assume 10ms per trade
                        
                        # Calculate metrics
                        profit = current_size - initial_size
                        profit_percentage = (profit / initial_size) * 100
                        path_efficiency = (profit_percentage / len(path)) * 100
                        total_execution_time = sum(execution_times)
                        
                        if profit_percentage > self.min_triangular_profit:
                            self.log_opportunity("triangular", {
                                "path": " -> ".join(path),
                                "exchanges": exchange,
                                "start_currency": path[0].split("/")[0],
                                "initial_size": str(initial_size),
                                "final_size": str(current_size),
                                "profit": str(profit),
                                "profit_percentage": str(profit_percentage),
                                "path_efficiency": str(path_efficiency),
                                "execution_time_estimate": str(total_execution_time)
                            })
                
                except Exception as e:
                    logger.error(f"Error checking triangular arbitrage for path {path} on {exchange}: {e}")
    
    async def start(self):
        """Start the trading system."""
        logger.info("Starting arbitrage opportunity detection...")
        self.is_running = True
        await self.monitor_opportunities()
    
    async def stop(self):
        """Stop the trading system."""
        logger.info("Stopping arbitrage opportunity detection...")
        self.is_running = False
        
        # Log detailed summary
        logger.info("\n" + "="*70)
        logger.info("Opportunity Detection Summary")
        logger.info("="*70)
        
        # Direct arbitrage summary
        direct_stats = self.opportunity_stats["direct"]
        logger.info("\nDirect Arbitrage Statistics:")
        logger.info(f"Total opportunities found: {direct_stats['total_found']}")
        logger.info(f"Total profit potential: {direct_stats['total_profit_potential']} USD")
        if direct_stats['most_profitable_pair']:
            logger.info(f"Best profit percentage: {direct_stats['best_profit_percentage']}%")
            logger.info(f"Most profitable pair: {direct_stats['most_profitable_pair']}")
            logger.info(f"Best exchanges: {direct_stats['best_exchanges']}")
        
        # Triangular arbitrage summary
        tri_stats = self.opportunity_stats["triangular"]
        logger.info("\nTriangular Arbitrage Statistics:")
        logger.info(f"Total opportunities found: {tri_stats['total_found']}")
        logger.info(f"Total profit potential: {tri_stats['total_profit_potential']} USD")
        if tri_stats['most_profitable_path']:
            logger.info(f"Best profit percentage: {tri_stats['best_profit_percentage']}%")
            logger.info(f"Most profitable path: {tri_stats['most_profitable_path']}")
            logger.info(f"Best exchange: {tri_stats['best_exchange']}")
        
        logger.info("\nOverall Statistics:")
        total_ops = direct_stats['total_found'] + tri_stats['total_found']
        total_profit = direct_stats['total_profit_potential'] + tri_stats['total_profit_potential']
        logger.info(f"Total opportunities: {total_ops}")
        logger.info(f"Total profit potential: {total_profit} USD")
        logger.info("="*70)

async def main():
    """Main entry point."""
    # Test wallet seed (don't use in production!)
    wallet_seed = "sn3nxiW7v8KXzPzAqzyHXbSSKNuN9"
    
    # Initialize and start trader
    trader = ArbitrageTrader(wallet_seed)
    
    try:
        await trader.start()
    except KeyboardInterrupt:
        await trader.stop()
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        await trader.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl+C
