"""
Demo script for testing the Quantum Arbitrage Agent
"""

import asyncio
import sys
import os

# Add project root and xrpl-py to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
xrpl_path = os.path.abspath(os.path.join(project_root, "../"))
sys.path.extend([project_root, xrpl_path])

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from agents.quantum_arbitrage_agent.quantum_arbitrage_agent import QuantumArbitrageAgent
from dotenv import load_dotenv

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize XRPL client (default to testnet)
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    # Create or load wallet
    try:
        # Try to load existing wallet
        seed = os.getenv("XRPL_SEED")
        if seed:
            wallet = Wallet.from_seed(seed)
            print(f"Loaded existing wallet: {wallet.classic_address}")
        else:
            # Create new wallet for testing
            wallet = Wallet.create()
            print(f"Created new wallet: {wallet.classic_address}")
            print(f"Seed (save this): {wallet.seed}")
    except Exception as e:
        print(f"Error loading wallet: {e}")
        print("Creating new wallet for testing...")
        wallet = Wallet.create()
        print(f"Created new wallet: {wallet.classic_address}")
        print(f"Seed (save this): {wallet.seed}")
    
    # Initialize agent
    agent = QuantumArbitrageAgent(
        client=client,
        wallet=wallet,
        initial_balance=1000.0  # Start with 1000 XRP
    )
    
    print("\nStarting Quantum Arbitrage Agent...")
    print("Press Ctrl+C to stop\n")
    
    try:
        # Run the agent
        await agent.run(interval=60)  # Check for opportunities every 60 seconds
    except KeyboardInterrupt:
        print("\nStopping agent...")
        # Print final performance metrics
        print("\nFinal Performance Metrics:")
        print(f"Starting Balance: {agent.initial_balance:.2f} XRP")
        print(f"Final Balance: {agent.current_balance:.2f} XRP")
        roi = (agent.current_balance - agent.initial_balance) / agent.initial_balance
        print(f"Total ROI: {roi*100:.2f}%")
        print(f"Total Trades: {len(agent.trade_history)}")
        print(f"Success Rate: {agent.performance_metrics['successful_trades']/len(agent.trade_history)*100:.2f}%" if agent.trade_history else "No trades executed")
    except Exception as e:
        print(f"Error running agent: {e}")

if __name__ == "__main__":
    asyncio.run(main())
