"""Example script demonstrating quantum-enhanced risk management."""

import asyncio
import numpy as np
from typing import List, Dict, Optional
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT
from qiskit_aer import AerSimulator
from dimod import BinaryQuadraticModel, SimulatedAnnealingSampler

def run_circuit(circuit, backend=None, shots=1000):
    """Run a quantum circuit on either local Aer or IBM Quantum hardware."""
    if backend is None:
        backend = AerSimulator()

    if isinstance(backend, AerSimulator):
        result = backend.run(circuit, shots=shots).result()
        return result.get_counts()

    from quantum_tools.ibm_backend import run_on_hardware
    return run_on_hardware(circuit, backend, shots)

class QuantumRiskManager:
    """Quantum-based risk management system."""
    
    def __init__(self, n_assets: int = 5, backend=None, sampler=None):
        self.n_assets = n_assets
        self.qft = QFT(n_assets)
        self.backend = backend or AerSimulator()
        self.sampler = sampler or SimulatedAnnealingSampler()
    
    async def optimize_portfolio(
        self,
        returns: List[float],
        volatilities: List[float],
        correlations: List[List[float]],
        risk_tolerance: float = 0.5
    ) -> Optional[Dict]:
        """Optimize portfolio using quantum/simulated annealing."""
        try:
            bqm = BinaryQuadraticModel('BINARY')
            
            for i in range(self.n_assets):
                bqm.add_variable(f'x_{i}', -returns[i])
            
            for i in range(self.n_assets):
                for j in range(self.n_assets):
                    if i != j:
                        bqm.add_interaction(
                            f'x_{i}',
                            f'x_{j}',
                            volatilities[i] * volatilities[j] * correlations[i][j] * risk_tolerance
                        )
            
            lagrange = 10.0
            for i in range(self.n_assets):
                for j in range(i + 1, self.n_assets):
                    bqm.add_interaction(f'x_{i}', f'x_{j}', 2 * lagrange)
                bqm.add_variable(f'x_{i}', lagrange)
            
            response = await asyncio.to_thread(
                self.sampler.sample,
                bqm,
                num_reads=1000
            )
            
            sample = response.first.sample
            
            weights = np.array([sample[f'x_{i}'] for i in range(self.n_assets)])
            total = np.sum(weights)
            if total > 0:
                weights = weights / total
            
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
        """Calculate Value at Risk using quantum Fourier transform."""
        try:
            n_qubits = self.n_assets + 3
            qc = QuantumCircuit(n_qubits, n_qubits)
            
            for i in range(self.n_assets):
                angle = np.arcsin(np.sqrt(weights[i] * volatilities[i]))
                qc.ry(angle, i)
            
            qc.append(self.qft, range(self.n_assets))
            qc.measure(range(n_qubits), range(n_qubits))
            
            counts = run_circuit(qc, self.backend, shots=1000)
            
            measurements = []
            for state, count in counts.items():
                value = int(state, 2) / (2**n_qubits)
                measurements.extend([value] * count)
            
            measurements = np.array(measurements)
            var_index = int((1 - confidence_level) * len(measurements))
            sorted_measurements = np.sort(measurements)
            var = sorted_measurements[var_index]
            var = var * portfolio_value * np.sqrt(time_horizon)
            
            return float(var)
            
        except Exception as e:
            print(f"Error in VaR calculation: {str(e)}")
            return None

class QuantumHedgingOptimizer:
    """Quantum optimizer for hedging strategies."""
    
    def __init__(self, n_instruments: int = 3, backend=None):
        self.n_instruments = n_instruments
        self.backend = backend or AerSimulator()
        self.circuit = self._create_hedging_circuit()
    
    def _create_hedging_circuit(self) -> QuantumCircuit:
        """Create quantum circuit for hedging optimization."""
        qc = QuantumCircuit(self.n_instruments * 2, self.n_instruments)
        
        qc.h(range(self.n_instruments))
        
        for i in range(self.n_instruments - 1):
            qc.cx(i, i + 1)
        
        qc.measure(range(self.n_instruments), range(self.n_instruments))
        return qc
    
    async def optimize_hedge(
        self,
        exposure: float,
        instruments: List[Dict],
        cost_threshold: float
    ) -> Optional[Dict]:
        """Optimize hedging strategy using quantum computing."""
        try:
            counts = run_circuit(self.circuit, self.backend, shots=1000)
            
            best_strategy = None
            best_coverage = 0
            
            for state, count in counts.items():
                selected = [int(x) for x in state]
                
                total_coverage = sum(
                    instruments[i]["coverage"] * selected[i]
                    for i in range(self.n_instruments)
                )
                
                total_cost = sum(
                    instruments[i]["cost"] * selected[i]
                    for i in range(self.n_instruments)
                )
                
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
    risk_manager = QuantumRiskManager(n_assets=5)
    
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
        returns, volatilities, correlations, risk_tolerance=0.5
    )
    
    if portfolio:
        print("Optimal portfolio weights:")
        for i, weight in enumerate(portfolio["weights"]):
            print(f"Asset {i + 1}: {weight:.2%}")
        print(f"Expected return: {portfolio['expected_return']:.2%}")
        print(f"Portfolio risk: {portfolio['risk']:.2%}")
        
        print("\nCalculating Value at Risk...")
        var = await risk_manager.calculate_var(
            portfolio_value=1000000,
            weights=portfolio["weights"],
            volatilities=volatilities
        )
        
        if var:
            print(f"1-day 95% VaR: ${var:,.2f}")
    
    hedge_optimizer = QuantumHedgingOptimizer(n_instruments=3)
    
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
