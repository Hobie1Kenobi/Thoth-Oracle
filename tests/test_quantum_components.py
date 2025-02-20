"""Tests for quantum components."""

import pytest
import numpy as np
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager, QuantumHedgingOptimizer

@pytest.mark.quantum
class TestQuantumPricePredictor:
    """Test quantum price prediction functionality."""
    
    @pytest.fixture
    def predictor(self):
        """Create a quantum price predictor instance."""
        return QuantumPricePredictor(n_qubits=2, n_layers=1)
    
    @pytest.mark.asyncio
    async def test_circuit_creation(self, predictor):
        """Test quantum circuit creation."""
        assert predictor.circuit is not None
        assert len(predictor.parameters) == 6  # 3 parameters per qubit per layer
    
    @pytest.mark.asyncio
    async def test_training(self, predictor, mock_quantum_circuit):
        """Test model training."""
        price_data = [100, 102, 98, 103, 105]
        await predictor.train(price_data)
        assert hasattr(predictor, 'optimal_params')
        assert len(predictor.optimal_params) == len(predictor.parameters)
    
    @pytest.mark.asyncio
    async def test_prediction(self, predictor, mock_quantum_circuit):
        """Test price prediction."""
        price_data = [100, 102, 98, 103, 105]
        await predictor.train(price_data)
        prediction = await predictor.predict_price(window_size=5)
        assert prediction is not None
        assert 0 <= prediction <= 1  # Normalized prediction

@pytest.mark.quantum
class TestQuantumRiskManager:
    """Test quantum risk management functionality."""
    
    @pytest.fixture
    def risk_manager(self):
        """Create a quantum risk manager instance."""
        return QuantumRiskManager(n_assets=3)
    
    @pytest.mark.asyncio
    async def test_portfolio_optimization(self, risk_manager, mock_dwave_sampler):
        """Test portfolio optimization."""
        returns = [0.1, 0.08, 0.12]
        volatilities = [0.15, 0.12, 0.18]
        correlations = [
            [1.0, 0.3, 0.2],
            [0.3, 1.0, 0.25],
            [0.2, 0.25, 1.0]
        ]
        
        result = await risk_manager.optimize_portfolio(
            returns,
            volatilities,
            correlations,
            risk_tolerance=0.5
        )
        
        assert result is not None
        assert "weights" in result
        assert len(result["weights"]) == 3
        assert abs(sum(result["weights"]) - 1.0) < 1e-6
    
    @pytest.mark.asyncio
    async def test_var_calculation(self, risk_manager, mock_quantum_circuit):
        """Test VaR calculation."""
        portfolio_value = 1000000
        weights = [0.4, 0.3, 0.3]
        volatilities = [0.15, 0.12, 0.18]
        
        var = await risk_manager.calculate_var(
            portfolio_value,
            weights,
            volatilities,
            confidence_level=0.95
        )
        
        assert var is not None
        assert var > 0
        assert var < portfolio_value

@pytest.mark.quantum
class TestQuantumHedgingOptimizer:
    """Test quantum hedging optimization functionality."""
    
    @pytest.fixture
    def hedge_optimizer(self):
        """Create a quantum hedging optimizer instance."""
        return QuantumHedgingOptimizer(n_instruments=3)
    
    def test_circuit_creation(self, hedge_optimizer):
        """Test hedging circuit creation."""
        assert hedge_optimizer.circuit is not None
        assert hedge_optimizer.circuit.num_qubits == 6  # 2 * n_instruments
    
    @pytest.mark.asyncio
    async def test_hedge_optimization(self, hedge_optimizer, mock_quantum_circuit):
        """Test hedge optimization."""
        exposure = 1000000
        instruments = [
            {"cost": 1000, "coverage": 50000},
            {"cost": 2000, "coverage": 100000},
            {"cost": 5000, "coverage": 300000}
        ]
        cost_threshold = 5000
        
        result = await hedge_optimizer.optimize_hedge(
            exposure,
            instruments,
            cost_threshold
        )
        
        assert result is not None
        assert "instruments" in result
        assert len(result["instruments"]) == 3
        assert result["cost"] <= cost_threshold
        assert result["coverage"] > 0
        assert 0 <= result["confidence"] <= 1
