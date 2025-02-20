"""
Flash Loan Trading Agent for Thoth Oracle
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from config.test_wallets import TESTNET_URL, FLASH_LOAN_WALLET
from agents.flash_loan_agent import FlashLoanAgent
from agents.xrpl_amm_agent import XRPLAMMAgent
from agents.risk_management_agent import RiskManagementAgent
from agents.monitoring_agent import MonitoringAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/flash_loan_trader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FlashLoanTradingAgent:
    """Agent for executing flash loan trades based on arbitrage opportunities."""
    
    def __init__(self):
        """Initialize the flash loan trading agent."""
        self.client = JsonRpcClient(TESTNET_URL)
        self.wallet = Wallet.from_seed(FLASH_LOAN_WALLET["seed"])
        self.flash_loan_agent = FlashLoanAgent(self.client, self.wallet)
        self.amm_agent = XRPLAMMAgent(self.client, self.wallet)
        self.risk_agent = RiskManagementAgent()
        self.monitoring_agent = MonitoringAgent()
        
        self.max_loan_size = FLASH_LOAN_WALLET["max_loan_size"]
        self.min_profit_threshold = FLASH_LOAN_WALLET["min_profit_threshold"]
        self.max_slippage = FLASH_LOAN_WALLET["max_slippage"]
        self.gas_buffer = FLASH_LOAN_WALLET["gas_buffer"]
        
        self.loans_executed = 0
        self.total_profit = Decimal("0")
        
    async def execute_flash_loan_trade(self, opportunity: Dict) -> bool:
        """Execute a flash loan trade based on an arbitrage opportunity."""
        try:
            # Validate opportunity
            if float(opportunity["details"]["profit_percentage"]) < float(self.min_profit_threshold):
                logger.info(f"Profit {opportunity['details']['profit_percentage']}% below threshold {self.min_profit_threshold}%")
                return False
            
            # Calculate loan size
            loan_size = min(
                Decimal(str(opportunity["details"]["size"])),
                self.max_loan_size
            )
            
            # Check loan availability
            loan_check = await self.flash_loan_agent.check_loan_availability(
                opportunity["details"]["base_currency"],
                loan_size
            )
            
            if not loan_check["available"]:
                logger.info(f"Flash loan not available: {loan_check['reason']}")
                return False
            
            # Calculate fees
            loan_fee = await self.flash_loan_agent.calculate_loan_fee(
                opportunity["details"]["base_currency"],
                loan_size
            )
            
            # Check if profitable after fees
            expected_profit = Decimal(str(opportunity["details"]["profit"]))
            total_fees = loan_fee * self.gas_buffer  # Add buffer for gas costs
            
            if expected_profit <= total_fees:
                logger.info(f"Not profitable after fees. Profit: {expected_profit}, Fees: {total_fees}")
                return False
            
            start_time = datetime.now()
            
            # Execute flash loan trade
            result = await self.flash_loan_agent.execute_flash_loan(
                base_currency=opportunity["details"]["base_currency"],
                quote_currency=opportunity["details"]["quote_currency"],
                issuer=opportunity["details"]["buy_exchange"],
                amount=loan_size,
                target_rate=Decimal(str(opportunity["details"]["sell_rate"]))
            )
            
            if not result["success"]:
                logger.error(f"Flash loan trade failed: {result['error']}")
                return False
            
            # Calculate actual profit
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            actual_profit = result["profit"]
            
            # Log trade
            self.loans_executed += 1
            self.total_profit += actual_profit
            
            self.monitoring_agent.log_trade(
                opportunity["details"]["pair"],
                loan_size,
                actual_profit,
                execution_time
            )
            
            logger.info(f"Flash loan trade executed successfully! Profit: {actual_profit} {opportunity['details']['quote_currency']}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing flash loan trade: {e}")
            return False
    
    async def monitor_opportunities(self):
        """Monitor for and act on arbitrage opportunities."""
        logger.info("Starting flash loan trading agent...")
        
        try:
            while True:
                try:
                    # Read latest opportunity
                    with open("logs/arbitrage_opportunities.log", "r") as f:
                        for line in f:
                            try:
                                opportunity = json.loads(line.strip())
                                # We handle both direct and triangular arbitrage
                                await self.execute_flash_loan_trade(opportunity)
                            except json.JSONDecodeError:
                                continue
                    
                    # Sleep briefly to prevent high CPU usage
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(5)  # Sleep longer on error
                    
        except KeyboardInterrupt:
            logger.info("Stopping flash loan trading agent...")
            
            logger.info("=== Flash Loan Trading Summary ===")
            logger.info(f"Total flash loans executed: {self.loans_executed}")
            logger.info(f"Total profit: {self.total_profit} XRP")
            logger.info("================================")

async def main():
    """Main entry point."""
    agent = FlashLoanTradingAgent()
    await agent.monitor_opportunities()

if __name__ == "__main__":
    asyncio.run(main())
