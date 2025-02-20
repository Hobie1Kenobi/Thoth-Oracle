"""Example script demonstrating quantum-enhanced risk management."""

import asyncio
import numpy as np
from typing import List, Dict, Optional
from qiskit import QuantumCircuit, execute, Aer
from qiskit.circuit.library import QFT
from dwave.system import DWaveSampler, EmbeddingComposite
from dimod import Binary, BinaryQuadraticModel

class QuantumRiskManager:
    """Quantum-based risk management system."""
    
    def __init__(self, n_assets: int = 5):
        """Initialize quantum risk manager.
        
        Args:
            n_assets: Number of assets to manage
        """
        self.n_assets = n_assets
        self.qft = QFT(n_assets)
        self.sampler = EmbeddingComposite(DWaveSampler())
    
    async def optimize_portfolio(
        self,
        returns: List[float],
        volatilities: List[float],
        correlations: List[List[float]],
        risk_tolerance: float = 0.5
    ) -> Optional[Dict]:
        """Optimize portfolio using quantum annealing.
        
        Args:
            returns: Expected returns for each asset
            volatilities: Volatility measures for each asset
            correlations: Correlation matrix between assets
            risk_tolerance: Risk tolerance parameter (0-1)
            
        Returns:
            Optimized portfolio weights
        """
        try:
            # Create binary quadratic model
            bqm = BinaryQuadraticModel('BINARY')
            
            # Add variables for each asset
            x = [Binary(f'x_{i}') for i in range(self.n_assets)]
            
            # Objective function: Maximize returns while minimizing risk
            # Returns component
            for i in range(self.n_assets):
                bqm.add_variable(f'x_{i}', -returns[i])
            
            # Risk component
            for i in range(self.n_assets):
                for j in range(self.n_assets):
                    bqm.add_interaction(
                        f'x_{i}',
                        f'x_{j}',
                        volatilities[i] * volatilities[j] * correlations[i][j] * risk_tolerance
                    )
            
            # Add constraint: Sum of weights = 1
            lagrange = 10.0  # Lagrange multiplier
            for i in range(self.n_assets):
                for j in range(i + 1, self.n_assets):
                    bqm.add_interaction(f'x_{i}', f'x_{j}', 2 * lagrange)
                bqm.add_variable(f'x_{i}', lagrange)
            
            # Run quantum annealing
            response = await asyncio.to_thread(
                self.sampler.sample,
                bqm,
                num_reads=1000,
                chain_strength=2.0
            )
            
            # Get best solution
            sample = response.first.sample
            
            # Convert to portfolio weights
            weights = np.array([sample[f'x_{i}'] for i in range(self.n_assets)])
            weights = weights / np.sum(weights)  # Normalize
            
            # Calculate expected return and risk
            expected_return = np.sum(weights * returns)
            portfolio_risk = np.sqrt(
                np.sum(weights * np.dot(np.diag(volatilities), np.dot(correlations, weights)))
            )
            
            return {
                "weights": weights.tolist(),
                "expected_return": float(expected_return),
                "risk": float(portfolio_risk)
            }
            
        except Exception as e:
            print(f"Error in portfolio optimization: {str(e)}")
            return None
    
    async def calculate_var(
        self,
        portfolio_value: float,
        weights: List[float],
        volatilities: List[float],
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ) -> Optional[float]:
        """Calculate Value at Risk using quantum Fourier transform.
        
        Args:
            portfolio_value: Current portfolio value
            weights: Portfolio weights
            volatilities: Asset volatilities
            confidence_level: VaR confidence level
            time_horizon: Time horizon in days
            
        Returns:
            VaR estimate
        """
        try:
            # Create quantum circuit for VaR calculation
            n_qubits = self.n_assets + 3  # Additional qubits for precision
            qc = QuantumCircuit(n_qubits, n_qubits)
            
            # Encode portfolio information
            for i in range(self.n_assets):
                angle = np.arcsin(np.sqrt(weights[i] * volatilities[i]))
                qc.ry(angle, i)
            
            # Apply QFT
            qc.append(self.qft, range(self.n_assets))
            
            # Measurement
            qc.measure(range(n_qubits), range(n_qubits))
            
            # Execute circuit
            job = execute(qc, Aer.get_backend('qasm_simulator'), shots=1000)
            counts = job.result().get_counts()
            
            # Process results
            measurements = []
            for state, count in counts.items():
                value = int(state, 2) / (2**n_qubits)
                measurements.extend([value] * count)
            
            # Calculate VaR
            measurements = np.array(measurements)
            var_index = int((1 - confidence_level) * len(measurements))
            sorted_measurements = np.sort(measurements)
            var = sorted_measurements[var_index]
            
            # Scale VaR
            var = var * portfolio_value * np.sqrt(time_horizon)
            
            return float(var)
            
        except Exception as e:
            print(f"Error in VaR calculation: {str(e)}")
            return None

class QuantumHedgingOptimizer:
    """Quantum optimizer for hedging strategies."""
    
    def __init__(self, n_instruments: int = 3):
        """Initialize hedging optimizer.
        
        Args:
            n_instruments: Number of hedging instruments
        """
        self.n_instruments = n_instruments
        self.circuit = self._create_hedging_circuit()
    
    def _create_hedging_circuit(self) -> QuantumCircuit:
        """Create quantum circuit for hedging optimization."""
        qc = QuantumCircuit(self.n_instruments * 2, self.n_instruments)
        
        # Initialize superposition
        qc.h(range(self.n_instruments))
        
        # Add entanglement
        for i in range(self.n_instruments - 1):
            qc.cx(i, i + 1)
        
        # Add measurement
        qc.measure(range(self.n_instruments), range(self.n_instruments))
        
        return qc
    
    async def optimize_hedge(
        self,
        exposure: float,
        instruments: List[Dict],
        cost_threshold: float
    ) -> Optional[Dict]:
        """Optimize hedging strategy using quantum computing.
        
        Args:
            exposure: Current market exposure
            instruments: List of hedging instruments with costs and coverages
            cost_threshold: Maximum acceptable hedging cost
            
        Returns:
            Optimized hedging strategy
        """
        try:
            # Execute quantum circuit
            job = execute(self.circuit, Aer.get_backend('qasm_simulator'), shots=1000)
            counts = job.result().get_counts()
            
            # Process results
            best_strategy = None
            best_coverage = 0
            
            for state, count in counts.items():
                # Convert quantum state to instrument selection
                selected = [int(x) for x in state]
                
                # Calculate coverage and cost
                total_coverage = sum(
                    instruments[i]["coverage"] * selected[i]
                    for i in range(self.n_instruments)
                )
                
                total_cost = sum(
                    instruments[i]["cost"] * selected[i]
                    for i in range(self.n_instruments)
                )
                
                # Check if strategy is valid and better than current best
                if (total_cost <= cost_threshold and
                    total_coverage > best_coverage):
                    best_strategy = {
                        "instruments": selected,
                        "coverage": float(total_coverage),
                        "cost": float(total_cost),
                        "confidence": count / 1000
                    }
                    best_coverage = total_coverage
            
            return best_strategy
            
        except Exception as e:
            print(f"Error in hedge optimization: {str(e)}")
            return None

async def main():
    """Main execution function."""
    # Example usage of quantum risk management
    risk_manager = QuantumRiskManager(n_assets=5)
    
    # Sample portfolio data
    returns = [0.10, 0.08, 0.12, 0.07, 0.09]
    volatilities = [0.15, 0.12, 0.18, 0.11, 0.14]
    correlations = [
        [1.00, 0.30, 0.20, 0.25, 0.15],
        [0.30, 1.00, 0.25, 0.20, 0.20],
        [0.20, 0.25, 1.00, 0.15, 0.30],
        [0.25, 0.20, 0.15, 1.00, 0.25],
        [0.15, 0.20, 0.30, 0.25, 1.00]
    ]
    
    print("Optimizing portfolio...")
    portfolio = await risk_manager.optimize_portfolio(
        returns,
        volatilities,
        correlations,
        risk_tolerance=0.5
    )
    
    if portfolio:
        print("Optimal portfolio weights:")
        for i, weight in enumerate(portfolio["weights"]):
            print(f"Asset {i + 1}: {weight:.2%}")
        print(f"Expected return: {portfolio['expected_return']:.2%}")
        print(f"Portfolio risk: {portfolio['risk']:.2%}")
        
        # Calculate VaR
        print("\nCalculating Value at Risk...")
        var = await risk_manager.calculate_var(
            portfolio_value=1000000,
            weights=portfolio["weights"],
            volatilities=volatilities
        )
        
        if var:
            print(f"1-day 95% VaR: ${var:,.2f}")
    
    # Example usage of quantum hedging optimization
    hedge_optimizer = QuantumHedgingOptimizer(n_instruments=3)
    
    # Sample hedging instruments
    instruments = [
        {"cost": 1000, "coverage": 50000},
        {"cost": 2000, "coverage": 100000},
        {"cost": 5000, "coverage": 300000}
    ]
    
    print("\nOptimizing hedging strategy...")
    hedge_strategy = await hedge_optimizer.optimize_hedge(
        exposure=1000000,
        instruments=instruments,
        cost_threshold=5000
    )
    
    if hedge_strategy:
        print("Optimal hedging strategy:")
        for i, selected in enumerate(hedge_strategy["instruments"]):
            if selected:
                print(f"Use instrument {i + 1}")
        print(f"Total coverage: ${hedge_strategy['coverage']:,.2f}")
        print(f"Total cost: ${hedge_strategy['cost']:,.2f}")
        print(f"Confidence: {hedge_strategy['confidence']:.2%}")

if __name__ == "__main__":
    asyncio.run(main())
