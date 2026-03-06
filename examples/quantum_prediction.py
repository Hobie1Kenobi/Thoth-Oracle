"""Example script demonstrating quantum-enhanced market prediction."""

import asyncio
import numpy as np
from typing import List, Dict, Optional
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Parameter
from qiskit_aer import AerSimulator

def run_circuit(circuit, backend=None, shots=1000):
    """Run a quantum circuit on either local Aer or IBM Quantum hardware."""
    if backend is None:
        backend = AerSimulator()

    if isinstance(backend, AerSimulator):
        result = backend.run(circuit, shots=shots).result()
        return result.get_counts()

    from quantum_tools.ibm_backend import run_on_hardware
    return run_on_hardware(circuit, backend, shots)

class QuantumPricePredictor:
    """Quantum circuit-based price prediction model."""
    
    def __init__(self, n_qubits: int = 4, n_layers: int = 2, backend=None):
        self.n_qubits = n_qubits
        self.n_layers = n_layers
        self.parameters = []
        self.backend = backend or AerSimulator()
        self.local_backend = AerSimulator()
        self.circuit = self._create_variational_circuit()
        self.optimal_params = None
        
    def _create_variational_circuit(self) -> QuantumCircuit:
        """Create a variational quantum circuit for price prediction."""
        qr = QuantumRegister(self.n_qubits, 'q')
        cr = ClassicalRegister(self.n_qubits, 'c')
        circuit = QuantumCircuit(qr, cr)
        
        circuit.h(range(self.n_qubits))
        
        for layer in range(self.n_layers):
            for qubit in range(self.n_qubits):
                theta = Parameter(f'θ_{layer}_{qubit}')
                phi = Parameter(f'φ_{layer}_{qubit}')
                lambda_ = Parameter(f'λ_{layer}_{qubit}')
                
                circuit.u(theta, phi, lambda_, qubit)
                self.parameters.extend([theta, phi, lambda_])
            
            for qubit in range(self.n_qubits - 1):
                circuit.cx(qubit, qubit + 1)
            circuit.cx(self.n_qubits - 1, 0)
        
        circuit.measure(qr, cr)
        return circuit
    
    async def train(self, price_data: List[float]) -> None:
        """Train the quantum circuit on historical price data. Uses local simulator for speed."""
        normalized_data = np.array(price_data) / np.max(np.abs(price_data))
        
        def cost_function(params):
            bound_circuit = self.circuit.assign_parameters(
                dict(zip(self.parameters, params))
            )
            counts = run_circuit(bound_circuit, self.local_backend, shots=1000)
            
            predicted = sum(int(state, 2) * count for state, count in counts.items()) / 1000
            predicted = predicted / (2**self.n_qubits)
            
            target = normalized_data[-1]
            return (predicted - target) ** 2
        
        initial_params = np.random.rand(len(self.parameters)) * 2 * np.pi
        
        best_params = initial_params
        best_cost = cost_function(initial_params)
        
        for iteration in range(100):
            perturbation = np.random.randn(len(self.parameters)) * 0.1
            candidate = best_params + perturbation
            candidate_cost = cost_function(candidate)
            if candidate_cost < best_cost:
                best_params = candidate
                best_cost = candidate_cost
        
        self.optimal_params = best_params
    
    async def predict_price(self, window_size: int = 10) -> Optional[float]:
        """Predict next price using quantum circuit."""
        try:
            bound_circuit = self.circuit.assign_parameters(
                dict(zip(self.parameters, self.optimal_params))
            )
            
            predictions = []
            for _ in range(window_size):
                counts = run_circuit(bound_circuit, self.backend, shots=1000)
                predicted = sum(int(state, 2) * count for state, count in counts.items()) / 1000
                predicted = predicted / (2**self.n_qubits)
                predictions.append(predicted)
            
            return np.mean(predictions)
            
        except Exception as e:
            print(f"Error in price prediction: {str(e)}")
            return None

class QuantumArbitrageDetector:
    """Quantum algorithm for detecting arbitrage opportunities."""
    
    def __init__(self, n_markets: int, backend=None):
        self.n_markets = n_markets
        self.n_qubits = self._calculate_required_qubits()
        self.backend = backend or AerSimulator()
        self.circuit = self._create_grover_circuit()
    
    def _calculate_required_qubits(self) -> int:
        return int(np.ceil(np.log2(self.n_markets))) + 1
    
    def _create_grover_circuit(self) -> QuantumCircuit:
        """Create Grover's algorithm circuit for arbitrage detection."""
        qr = QuantumRegister(self.n_qubits, 'q')
        cr = ClassicalRegister(self.n_qubits, 'c')
        circuit = QuantumCircuit(qr, cr)
        
        circuit.h(range(self.n_qubits - 1))
        circuit.x(self.n_qubits - 1)
        circuit.h(self.n_qubits - 1)
        
        circuit.h(range(self.n_qubits - 1))
        circuit.x(range(self.n_qubits - 1))
        circuit.h(self.n_qubits - 1)
        circuit.mcx(list(range(self.n_qubits - 1)), self.n_qubits - 1)
        circuit.h(self.n_qubits - 1)
        circuit.x(range(self.n_qubits - 1))
        circuit.h(range(self.n_qubits - 1))
        
        circuit.measure(qr, cr)
        return circuit
    
    async def detect_arbitrage(
        self,
        price_matrix: List[List[float]],
        threshold: float = 0.01
    ) -> List[Dict]:
        """Detect arbitrage opportunities using quantum algorithm."""
        opportunities = []
        
        try:
            counts = run_circuit(self.circuit, self.backend, shots=1000)
            
            for state, count in counts.items():
                if count > 100:
                    path = [int(x) for x in state[:-1]]
                    
                    profit = 1.0
                    for i in range(len(path) - 1):
                        profit *= price_matrix[path[i]][path[i + 1]]
                    profit *= price_matrix[path[-1]][path[0]]
                    
                    if profit > 1 + threshold:
                        opportunities.append({
                            "path": path,
                            "profit": profit - 1,
                            "confidence": count / 1000
                        })
            
            return opportunities
            
        except Exception as e:
            print(f"Error in arbitrage detection: {str(e)}")
            return []

async def main():
    """Main execution function."""
    predictor = QuantumPricePredictor(n_qubits=4, n_layers=3)
    
    historical_prices = [100, 102, 98, 103, 105, 104, 107, 106, 108, 110]
    
    print("Training quantum price predictor...")
    await predictor.train(historical_prices)
    
    print("Predicting next price...")
    prediction = await predictor.predict_price(window_size=10)
    if prediction is not None:
        print(f"Predicted price: {prediction * max(historical_prices):.2f}")
    
    detector = QuantumArbitrageDetector(n_markets=4)
    
    price_matrix = [
        [1.0, 0.95, 1.05, 0.98],
        [1.05, 1.0, 0.97, 1.02],
        [0.95, 1.03, 1.0, 0.99],
        [1.02, 0.98, 1.01, 1.0]
    ]
    
    print("\nDetecting arbitrage opportunities...")
    opportunities = await detector.detect_arbitrage(price_matrix, threshold=0.01)
    
    if opportunities:
        print("Found arbitrage opportunities:")
        for opp in opportunities:
            path_str = " -> ".join(str(x) for x in opp["path"])
            print(f"Path: {path_str}")
            print(f"Potential profit: {opp['profit']*100:.2f}%")
            print(f"Confidence: {opp['confidence']*100:.2f}%\n")
    else:
        print("No significant arbitrage opportunities found")

if __name__ == "__main__":
    asyncio.run(main())
