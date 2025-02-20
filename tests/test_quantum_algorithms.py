"""Tests for specific quantum algorithms."""

import pytest
import numpy as np
from qiskit import QuantumCircuit, execute, Aer
from qiskit.circuit import Parameter
from qiskit.algorithms.optimizers import SPSA
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager, QuantumHedgingOptimizer

@pytest.mark.quantum_algorithms
class TestQuantumCircuits:
    """Test quantum circuit implementations."""
    
    def test_circuit_initialization(self):
        """Test quantum circuit initialization."""
        circuit = QuantumCircuit(2, 2)
        circuit.h(0)
        circuit.cx(0, 1)
        circuit.measure_all()
        
        simulator = Aer.get_backend('aer_simulator')
        result = execute(circuit, simulator, shots=1000).result()
        counts = result.get_counts(circuit)
        
        # Should get roughly equal superposition
        assert abs(counts.get('00', 0) - 500) < 100
        assert abs(counts.get('11', 0) - 500) < 100
    
    def test_parameterized_circuit(self):
        """Test parameterized quantum circuit."""
        theta = Parameter('θ')
        circuit = QuantumCircuit(1, 1)
        circuit.rx(theta, 0)
        circuit.measure_all()
        
        # Test with different parameter values
        for angle in [0, np.pi/2, np.pi]:
            bound_circuit = circuit.bind_parameters({theta: angle})
            result = execute(bound_circuit, Aer.get_backend('aer_simulator'), shots=1000).result()
            counts = result.get_counts(bound_circuit)
            
            if angle == 0:
                assert counts.get('0', 0) > 900  # Should mostly measure 0
            elif angle == np.pi:
                assert counts.get('1', 0) > 900  # Should mostly measure 1

@pytest.mark.quantum_algorithms
class TestOptimizationAlgorithms:
    """Test quantum optimization algorithms."""
    
    @pytest.fixture
    def optimizer(self):
        """Create SPSA optimizer."""
        return SPSA(maxiter=100)
    
    def test_spsa_optimization(self, optimizer):
        """Test SPSA optimization."""
        def objective(params):
            """Simple objective function."""
            x, y = params
            return (x - 1)**2 + (y - 2)**2
        
        result = optimizer.optimize(
            num_vars=2,
            objective_function=objective,
            initial_point=[0, 0]
        )
        
        # Should converge close to minimum at (1, 2)
        assert abs(result[0][0] - 1) < 0.1
        assert abs(result[0][1] - 2) < 0.1

@pytest.mark.quantum_algorithms
class TestQuantumML:
    """Test quantum machine learning algorithms."""
    
    @pytest.fixture
    def predictor(self):
        """Create quantum price predictor."""
        return QuantumPricePredictor(n_qubits=2, n_layers=2)
    
    @pytest.mark.asyncio
    async def test_quantum_feature_map(self, predictor):
        """Test quantum feature mapping."""
        # Test with simple price data
        price_data = [100, 101, 102, 103, 104]
        features = await predictor.create_quantum_features(price_data)
        
        assert features.shape[1] == predictor.n_qubits * 2  # Should have 2 features per qubit
        assert np.all(features >= -1) and np.all(features <= 1)  # Features should be normalized
    
    @pytest.mark.asyncio
    async def test_quantum_kernel(self, predictor):
        """Test quantum kernel computation."""
        # Create simple test data
        X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
        kernel_matrix = await predictor.compute_quantum_kernel(X)
        
        assert kernel_matrix.shape == (4, 4)  # Should be square matrix
        assert np.allclose(kernel_matrix, kernel_matrix.T)  # Should be symmetric
        assert np.all(np.diag(kernel_matrix) == 1)  # Diagonal should be 1

@pytest.mark.quantum_algorithms
class TestQuantumRisk:
    """Test quantum risk management algorithms."""
    
    @pytest.fixture
    def risk_manager(self):
        """Create quantum risk manager."""
        return QuantumRiskManager(n_assets=3)
    
    @pytest.mark.asyncio
    async def test_quantum_amplitude_estimation(self, risk_manager):
        """Test quantum amplitude estimation for VaR."""
        portfolio_value = 1000000
        weights = [0.4, 0.3, 0.3]
        volatilities = [0.15, 0.12, 0.18]
        
        var = await risk_manager.estimate_var_quantum(
            portfolio_value,
            weights,
            volatilities,
            confidence_level=0.95
        )
        
        assert var > 0
        assert var < portfolio_value
        # VaR should be reasonable (e.g., 5-15% of portfolio value)
        assert 0.05 * portfolio_value <= var <= 0.15 * portfolio_value
    
    @pytest.mark.asyncio
    async def test_quantum_portfolio_optimization(self, risk_manager):
        """Test quantum portfolio optimization."""
        returns = [0.1, 0.08, 0.12]
        volatilities = [0.15, 0.12, 0.18]
        correlations = [
            [1.0, 0.3, 0.2],
            [0.3, 1.0, 0.25],
            [0.2, 0.25, 1.0]
        ]
        
        result = await risk_manager.optimize_portfolio_quantum(
            returns,
            volatilities,
            correlations,
            risk_tolerance=0.5
        )
        
        assert "weights" in result
        assert len(result["weights"]) == 3
        assert abs(sum(result["weights"]) - 1.0) < 1e-6
        assert "expected_return" in result
        assert "expected_risk" in result
        assert result["expected_return"] > min(returns)
        assert result["expected_risk"] < max(volatilities)

@pytest.mark.quantum_algorithms
class TestQuantumArbitrage:
    """Test quantum arbitrage detection algorithms."""
    
    @pytest.fixture
    def hedge_optimizer(self):
        """Create quantum hedging optimizer."""
        return QuantumHedgingOptimizer(n_instruments=3)
    
    @pytest.mark.asyncio
    async def test_grover_search(self, hedge_optimizer):
        """Test Grover's algorithm for arbitrage detection."""
        # Create test market data with known arbitrage
        market_data = {
            "ETH/USD": 2000,
            "ETH/EUR": 1700,
            "EUR/USD": 1.25
        }
        
        opportunities = await hedge_optimizer.find_arbitrage_quantum(market_data)
        
        assert len(opportunities) > 0
        for opp in opportunities:
            assert "profit" in opp
            assert opp["profit"] > 0
            assert "route" in opp
            assert len(opp["route"]) >= 2
    
    @pytest.mark.asyncio
    async def test_quantum_annealing_hedge(self, hedge_optimizer):
        """Test quantum annealing for optimal hedging."""
        exposure = 1000000
        instruments = [
            {"cost": 1000, "coverage": 50000},
            {"cost": 2000, "coverage": 100000},
            {"cost": 5000, "coverage": 300000}
        ]
        
        result = await hedge_optimizer.optimize_hedge_quantum(
            exposure,
            instruments,
            max_cost=10000
        )
        
        assert "selected_instruments" in result
        assert "total_cost" in result
        assert "total_coverage" in result
        assert result["total_cost"] <= 10000
        assert result["total_coverage"] > 0
        assert len(result["selected_instruments"]) <= len(instruments)
