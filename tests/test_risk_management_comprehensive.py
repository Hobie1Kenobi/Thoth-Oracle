"""Comprehensive tests for risk management system."""

import pytest
import numpy as np
from decimal import Decimal
from examples.risk_management import QuantumRiskManager, QuantumHedgingOptimizer

@pytest.mark.comprehensive
class TestRiskManagementComprehensive:
    """Comprehensive test suite for risk management."""
    
    @pytest.fixture
    def risk_manager(self):
        """Create quantum risk manager."""
        return QuantumRiskManager(n_assets=3)
    
    @pytest.fixture
    def hedge_optimizer(self):
        """Create quantum hedging optimizer."""
        return QuantumHedgingOptimizer(n_instruments=3)
    
    @pytest.mark.asyncio
    async def test_portfolio_optimization_detailed(self, risk_manager):
        """Test detailed portfolio optimization."""
        test_cases = [
            {
                "returns": [0.1, 0.08, 0.12],
                "volatilities": [0.15, 0.12, 0.18],
                "correlations": [
                    [1.0, 0.3, 0.2],
                    [0.3, 1.0, 0.25],
                    [0.2, 0.25, 1.0]
                ],
                "risk_tolerance": 0.5
            },
            {
                "returns": [0.15, 0.05, 0.10],
                "volatilities": [0.20, 0.10, 0.15],
                "correlations": [
                    [1.0, -0.2, 0.1],
                    [-0.2, 1.0, -0.1],
                    [0.1, -0.1, 1.0]
                ],
                "risk_tolerance": 0.7
            }
        ]
        
        for case in test_cases:
            result = await risk_manager.optimize_portfolio(
                case["returns"],
                case["volatilities"],
                case["correlations"],
                case["risk_tolerance"]
            )
            
            assert "weights" in result
            assert len(result["weights"]) == 3
            assert abs(sum(result["weights"]) - 1.0) < 1e-6
            assert "expected_return" in result
            assert "expected_risk" in result
            
            # Verify Sharpe ratio
            risk_free_rate = 0.02  # Assume 2% risk-free rate
            sharpe_ratio = (result["expected_return"] - risk_free_rate) / result["expected_risk"]
            assert sharpe_ratio > 0
    
    @pytest.mark.asyncio
    async def test_var_calculation_detailed(self, risk_manager):
        """Test detailed VaR calculation."""
        test_cases = [
            {
                "portfolio_value": 1000000,
                "weights": [0.4, 0.3, 0.3],
                "volatilities": [0.15, 0.12, 0.18],
                "confidence_level": 0.95
            },
            {
                "portfolio_value": 2000000,
                "weights": [0.6, 0.2, 0.2],
                "volatilities": [0.20, 0.10, 0.15],
                "confidence_level": 0.99
            }
        ]
        
        for case in test_cases:
            var = await risk_manager.calculate_var(
                case["portfolio_value"],
                case["weights"],
                case["volatilities"],
                case["confidence_level"]
            )
            
            assert var > 0
            assert var < case["portfolio_value"]
            
            # Verify VaR is higher for higher confidence levels
            var_95 = await risk_manager.calculate_var(
                case["portfolio_value"],
                case["weights"],
                case["volatilities"],
                0.95
            )
            var_99 = await risk_manager.calculate_var(
                case["portfolio_value"],
                case["weights"],
                case["volatilities"],
                0.99
            )
            assert var_99 > var_95
    
    @pytest.mark.asyncio
    async def test_quantum_portfolio_optimization(self, risk_manager):
        """Test quantum-specific portfolio optimization."""
        returns = [0.1, 0.08, 0.12]
        volatilities = [0.15, 0.12, 0.18]
        correlations = [
            [1.0, 0.3, 0.2],
            [0.3, 1.0, 0.25],
            [0.2, 0.25, 1.0]
        ]
        
        # Test different quantum methods
        methods = ["qaoa", "vqe", "quantum_annealing"]
        
        for method in methods:
            result = await risk_manager.optimize_portfolio_quantum(
                returns,
                volatilities,
                correlations,
                risk_tolerance=0.5,
                method=method
            )
            
            assert "weights" in result
            assert "quantum_circuit" in result
            assert "optimization_steps" in result
            assert result["optimization_steps"] > 0
    
    @pytest.mark.asyncio
    async def test_hedging_optimization_detailed(self, hedge_optimizer):
        """Test detailed hedging optimization."""
        test_cases = [
            {
                "exposure": 1000000,
                "instruments": [
                    {"cost": 1000, "coverage": 50000},
                    {"cost": 2000, "coverage": 100000},
                    {"cost": 5000, "coverage": 300000}
                ],
                "max_cost": 10000
            },
            {
                "exposure": 2000000,
                "instruments": [
                    {"cost": 2000, "coverage": 100000},
                    {"cost": 4000, "coverage": 200000},
                    {"cost": 10000, "coverage": 600000}
                ],
                "max_cost": 20000
            }
        ]
        
        for case in test_cases:
            result = await hedge_optimizer.optimize_hedge(
                case["exposure"],
                case["instruments"],
                case["max_cost"]
            )
            
            assert "selected_instruments" in result
            assert "total_cost" in result
            assert "total_coverage" in result
            assert result["total_cost"] <= case["max_cost"]
            assert result["total_coverage"] > 0
    
    @pytest.mark.asyncio
    async def test_risk_metrics_detailed(self, risk_manager):
        """Test detailed risk metrics calculation."""
        portfolio = {
            "value": 1000000,
            "weights": [0.4, 0.3, 0.3],
            "returns": [0.1, 0.08, 0.12],
            "volatilities": [0.15, 0.12, 0.18],
            "correlations": [
                [1.0, 0.3, 0.2],
                [0.3, 1.0, 0.25],
                [0.2, 0.25, 1.0]
            ]
        }
        
        metrics = await risk_manager.calculate_risk_metrics(portfolio)
        
        assert "var_95" in metrics
        assert "var_99" in metrics
        assert "expected_shortfall" in metrics
        assert "beta" in metrics
        assert "tracking_error" in metrics
        assert "information_ratio" in metrics
        assert "sortino_ratio" in metrics
        
        # Verify relationships between metrics
        assert metrics["var_99"] > metrics["var_95"]
        assert metrics["expected_shortfall"] > metrics["var_99"]
    
    @pytest.mark.asyncio
    async def test_stress_testing_detailed(self, risk_manager):
        """Test detailed stress testing."""
        portfolio = {
            "value": 1000000,
            "weights": [0.4, 0.3, 0.3],
            "volatilities": [0.15, 0.12, 0.18]
        }
        
        scenarios = [
            {"name": "market_crash", "shock": -0.3},
            {"name": "interest_rate_hike", "shock": -0.1},
            {"name": "currency_crisis", "shock": -0.2}
        ]
        
        results = await risk_manager.perform_stress_test(portfolio, scenarios)
        
        for scenario in scenarios:
            assert scenario["name"] in results
            assert "impact" in results[scenario["name"]]
            assert "var_change" in results[scenario["name"]]
            assert results[scenario["name"]]["impact"] < 0
    
    @pytest.mark.asyncio
    async def test_quantum_risk_simulation(self, risk_manager):
        """Test quantum risk simulation."""
        portfolio = {
            "value": 1000000,
            "weights": [0.4, 0.3, 0.3],
            "returns": [0.1, 0.08, 0.12],
            "volatilities": [0.15, 0.12, 0.18]
        }
        
        n_scenarios = 1000
        simulation_results = await risk_manager.quantum_monte_carlo(
            portfolio,
            n_scenarios
        )
        
        assert "scenarios" in simulation_results
        assert len(simulation_results["scenarios"]) == n_scenarios
        assert "var_distribution" in simulation_results
        assert "expected_shortfall_distribution" in simulation_results
        
        # Verify statistical properties
        mean_return = np.mean([s["return"] for s in simulation_results["scenarios"]])
        assert abs(mean_return - np.dot(portfolio["weights"], portfolio["returns"])) < 0.1
