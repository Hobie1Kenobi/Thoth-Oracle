"""
Live Arbitrage Testing Script
Tests the Thoth Oracle system with live XRPL data.
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet

from agents.flash_loan_agent import FlashLoanAgent
from agents.xrpl_amm_agent import XRPLAMMAgent
from agents.risk_management_agent import RiskManagementAgent
from agents.monitoring_agent import MonitoringAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# XRPL testnet configuration
TESTNET_URL = "https://s.altnet.rippletest.net:51234"
TEST_WALLET_SEED = "sEd7rBGm5kxzauRTAV2kb7xEdghtY"  # Example seed, replace with your own

# Trading pairs to monitor
TRADING_PAIRS = [
    {
        "base": "XRP",
        "quote": "USD",
        "issuer": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"  # Bitstamp
    },
    {
        "base": "XRP",
        "quote": "EUR",
        "issuer": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq"  # GateHub
    },
    {
        "base": "XRP",
        "quote": "BTC",
        "issuer": "rMwjYedjc7qqtKYVLiAccJSmCwih4LnE2q"  # SnapSwap
    }
]

class ArbitrageTrader:
    def __init__(self):
        """Initialize the arbitrage trader."""
        # Initialize XRPL client and wallet
        self.client = JsonRpcClient(TESTNET_URL)
        self.wallet = Wallet.from_seed(TEST_WALLET_SEED)
        
        # Initialize agents
        self.flash_loan_agent = FlashLoanAgent()
        self.amm_agent = XRPLAMMAgent(self.client)
        self.risk_agent = RiskManagementAgent()
        self.monitor_agent = MonitoringAgent()
        
        # Trading state
        self.active = False
        self.min_profit = Decimal("0.01")  # 1% minimum profit
        self.trade_size = Decimal("1000")  # 1000 XRP per trade
    
    async def start(self):
        """Start the arbitrage trading system."""
        try:
            logger.info("Starting arbitrage trading system...")
            self.active = True
            
            # Start monitoring
            monitor_task = asyncio.create_task(
                self.monitor_agent.start_monitoring()
            )
            
            # Start main trading loop
            while self.active:
                await self.check_arbitrage_opportunities()
                await asyncio.sleep(1)  # Check every second
                
        except Exception as e:
            logger.error(f"Error in trading system: {e}")
            await self.monitor_agent.log_error("trading_system", str(e), "critical")
            
        finally:
            self.active = False
    
    async def check_arbitrage_opportunities(self):
        """Check for arbitrage opportunities across trading pairs."""
        try:
            for base_pair in TRADING_PAIRS:
                # Find arbitrage paths
                paths = await self.amm_agent.get_arbitrage_paths(
                    base_pair["base"],
                    base_pair["issuer"],
                    self.min_profit
                )
                
                for path in paths:
                    # Assess trade risk
                    risk = await self.risk_agent.assess_trade_risk(
                        path["path"][0]["pair"],
                        self.trade_size,
                        Decimal(path["profit"])
                    )
                    
                    if risk["allowed"]:
                        # Execute arbitrage trade
                        start_time = datetime.now()
                        
                        result = await self.execute_arbitrage_trade(
                            path["path"],
                            self.trade_size
                        )
                        
                        # Calculate latency
                        latency = (datetime.now() - start_time).total_seconds()
                        
                        # Log trade
                        if result["status"] == "success":
                            await self.monitor_agent.log_trade(
                                path["path"][0]["pair"],
                                self.trade_size,
                                Decimal(result["profit"]),
                                latency
                            )
                            
                            # Update risk metrics
                            await self.risk_agent.update_position(
                                path["path"][0]["pair"],
                                self.trade_size,
                                Decimal(result["profit"])
                            )
                        else:
                            await self.monitor_agent.log_error(
                                "arbitrage_execution",
                                result["error"]
                            )
                    
        except Exception as e:
            logger.error(f"Error checking arbitrage opportunities: {e}")
            await self.monitor_agent.log_error(
                "arbitrage_check",
                str(e)
            )
    
    async def execute_arbitrage_trade(
        self,
        path: list,
        size: Decimal
    ) -> dict:
        """Execute an arbitrage trade along a path."""
        try:
            # Get flash loan
            loan_result = await self.flash_loan_agent.execute_flash_loan(
                path[0]["base"],
                size,
                1  # XRPL chain ID
            )
            
            if loan_result["status"] != "success":
                return loan_result
            
            # Execute trades along path
            for step in path:
                trade_result = await self.amm_agent.calculate_optimal_trade(
                    step["base"],
                    step["quote"],
                    step["issuer"],
                    size
                )
                
                if "error" in trade_result:
                    # Repay flash loan and return error
                    await self.flash_loan_agent.repay_flash_loan(
                        path[0]["base"],
                        size,
                        loan_result["tx_hash"]
                    )
                    return {"status": "failed", "error": trade_result["error"]}
                
                # Update size for next trade
                size = Decimal(trade_result["net_output"])
            
            # Repay flash loan
            repay_result = await self.flash_loan_agent.repay_flash_loan(
                path[0]["base"],
                size,
                loan_result["tx_hash"]
            )
            
            if repay_result["status"] != "success":
                return repay_result
            
            # Calculate final profit
            profit = size - Decimal(loan_result["amount"])
            
            return {
                "status": "success",
                "profit": str(profit),
                "path": path
            }
            
        except Exception as e:
            logger.error(f"Error executing arbitrage trade: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

async def main():
    """Main entry point."""
    trader = ArbitrageTrader()
    await trader.start()

if __name__ == "__main__":
    asyncio.run(main())
