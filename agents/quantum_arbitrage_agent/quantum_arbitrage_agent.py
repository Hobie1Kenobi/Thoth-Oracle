"""
Quantum Arbitrage Agent
Combines quantum prediction and optimization for advanced arbitrage detection
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np
import sys
import os

# Add xrpl-py to Python path
xrpl_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.append(xrpl_path)

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment
from xrpl.wallet import Wallet
from agents.quantum_arbitrage_agent.quantum_predictor import HybridQuantumPredictor
from agents.quantum_arbitrage_agent.quantum_optimizer import QuantumPathOptimizer
from agents.market_data_oracle.market_data_oracle import MarketDataOracle
from agents.market_data_oracle.xrpl_connector import XRPLConnector

class QuantumArbitrageAgent:
    def __init__(self, 
                client: JsonRpcClient, 
                wallet: Optional[Wallet] = None,
                initial_balance: float = 1000.0):
        """
        Initialize Quantum Arbitrage Agent
        
        Args:
            client: XRPL client connection
            wallet: XRPL wallet for transactions (optional)
            initial_balance: Starting XRP balance (default 1000 XRP)
        """
        self.client = client
        self.wallet = wallet or Wallet.create()  # Create new wallet if none provided
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Initialize components
        self.connector = XRPLConnector(client)
        self.predictor = HybridQuantumPredictor(n_qubits=4, n_layers=2)
        self.optimizer = QuantumPathOptimizer(n_markets=10)
        
        # Trading state
        self.active_trades = []
        self.trade_history = []
        self.performance_metrics = {
            'total_profit': 0.0,
            'successful_trades': 0,
            'failed_trades': 0,
            'avg_profit_per_trade': 0.0
        }
        
    async def get_wallet_balance(self) -> float:
        """Get current wallet balance."""
        try:
            account_info = await self.client.request(
                AccountInfo(account=self.wallet.classic_address)
            )
            return float(account_info.result['account_data']['Balance']) / 1_000_000.0
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            return self.current_balance
            
    async def analyze_market_conditions(self) -> Dict:
        """Analyze current market conditions using quantum prediction."""
        market_data = await self.connector.get_market_data()
        
        # Get price predictions
        qiskit_prediction = await self.predictor.predict_price_movement(
            market_data, use_qiskit=True
        )
        pennylane_prediction = await self.predictor.predict_price_movement(
            market_data, use_qiskit=False
        )
        
        # Combine predictions
        combined_confidence = (qiskit_prediction['confidence'] + 
                             pennylane_prediction['confidence']) / 2
        
        return {
            'market_trend': qiskit_prediction['direction'],
            'confidence': combined_confidence,
            'qiskit_probability': qiskit_prediction['probability'],
            'pennylane_probability': pennylane_prediction['probability']
        }
        
    async def find_arbitrage_opportunities(self, 
                                        min_profit: float = 0.005) -> List[Dict]:
        """
        Find arbitrage opportunities using quantum optimization
        
        Args:
            min_profit: Minimum profit threshold (0.5% default)
        """
        # Get market data
        market_data = await self.connector.get_market_data()
        
        # Create price matrix
        pairs = list(market_data['currency_pairs'].values())
        n_pairs = len(pairs)
        price_matrix = np.zeros((n_pairs, n_pairs))
        
        for i, pair1 in enumerate(pairs):
            for j, pair2 in enumerate(pairs):
                if i != j:
                    # Calculate cross-rate
                    price_matrix[i,j] = float(pair1.get('price', 1.0)) / \
                                      float(pair2.get('price', 1.0))
        
        # Find optimal paths using both methods
        annealing_result = await self.optimizer.find_optimal_path(
            price_matrix, min_profit, use_annealing=True
        )
        qaoa_result = await self.optimizer.find_optimal_path(
            price_matrix, min_profit, use_annealing=False
        )
        
        opportunities = []
        for result in [annealing_result, qaoa_result]:
            if result['profit'] > min_profit:
                path = result['path']
                opportunities.append({
                    'path': [pairs[i]['pair_id'] for i in path],
                    'expected_profit': result['profit'],
                    'confidence': result['confidence'],
                    'method': 'annealing' if result == annealing_result else 'qaoa'
                })
        
        return opportunities
        
    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute a trade based on an arbitrage opportunity."""
        try:
            # Validate opportunity
            if not opportunity['path'] or opportunity['expected_profit'] <= 0:
                return False
                
            # Get current market conditions
            conditions = await self.analyze_market_conditions()
            
            # Only proceed if market conditions are favorable
            if conditions['confidence'] < 0.6:
                print(f"Market conditions unfavorable, skipping trade")
                return False
                
            # Record trade start
            trade_start = {
                'timestamp': datetime.now().isoformat(),
                'path': opportunity['path'],
                'expected_profit': opportunity['expected_profit'],
                'market_conditions': conditions,
                'initial_balance': await self.get_wallet_balance()
            }
            
            # Execute trades (simulated for now)
            # TODO: Implement actual XRPL trades
            success = True  # Simulate trade success
            
            if success:
                # Update balance and metrics
                self.current_balance *= (1 + opportunity['expected_profit'])
                self.performance_metrics['successful_trades'] += 1
                self.performance_metrics['total_profit'] += opportunity['expected_profit']
            else:
                self.performance_metrics['failed_trades'] += 1
                
            # Record trade completion
            self.trade_history.append({
                **trade_start,
                'success': success,
                'final_balance': await self.get_wallet_balance(),
                'actual_profit': (await self.get_wallet_balance() - 
                                trade_start['initial_balance']) / 
                                trade_start['initial_balance']
            })
            
            # Update average profit
            total_trades = (self.performance_metrics['successful_trades'] + 
                          self.performance_metrics['failed_trades'])
            self.performance_metrics['avg_profit_per_trade'] = \
                self.performance_metrics['total_profit'] / total_trades \
                if total_trades > 0 else 0
                
            return success
            
        except Exception as e:
            print(f"Error executing trade: {e}")
            return False
            
    async def run(self, interval: int = 60):
        """
        Run the arbitrage agent continuously
        
        Args:
            interval: Time between checks in seconds
        """
        print(f"Starting Quantum Arbitrage Agent with {self.initial_balance} XRP")
        print(f"Wallet address: {self.wallet.classic_address}")
        
        while True:
            try:
                # Find opportunities
                opportunities = await self.find_arbitrage_opportunities()
                
                # Sort by expected profit * confidence
                opportunities.sort(
                    key=lambda x: x['expected_profit'] * x['confidence'],
                    reverse=True
                )
                
                # Execute best opportunities
                for opp in opportunities[:3]:  # Try top 3 opportunities
                    if opp['confidence'] > 0.7:  # High confidence threshold
                        success = await self.execute_trade(opp)
                        if success:
                            print(
                                f"Executed {opp['method']} arbitrage with "
                                f"{opp['expected_profit']*100:.2f}% profit"
                            )
                            
                # Print performance metrics
                print("\nPerformance Metrics:")
                print(f"Current Balance: {self.current_balance:.2f} XRP")
                print(f"Total Profit: {self.performance_metrics['total_profit']*100:.2f}%")
                print(f"Successful Trades: {self.performance_metrics['successful_trades']}")
                print(f"Failed Trades: {self.performance_metrics['failed_trades']}")
                print(
                    f"Avg Profit/Trade: "
                    f"{self.performance_metrics['avg_profit_per_trade']*100:.2f}%"
                )
                print("-" * 50)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"Error in arbitrage loop: {e}")
                await asyncio.sleep(interval)
