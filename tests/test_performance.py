"""Performance benchmarks for critical operations."""

import pytest
import time
import asyncio
from decimal import Decimal
from typing import List, Dict, Any
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager
from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent

@pytest.mark.benchmark
class TestQuantumPerformance:
    """Benchmark quantum operations."""
    
    @pytest.fixture
    def predictor(self):
        """Create quantum price predictor."""
        return QuantumPricePredictor(n_qubits=2, n_layers=1)
    
    @pytest.fixture
    def risk_manager(self):
        """Create quantum risk manager."""
        return QuantumRiskManager(n_assets=3)
    
    async def _measure_execution_time(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Measure execution time of a function."""
        start_time = time.perf_counter()
        start_memory = self._get_memory_usage()
        
        result = await func(*args, **kwargs)
        
        end_time = time.perf_counter()
        end_memory = self._get_memory_usage()
        
        return {
            "execution_time": end_time - start_time,
            "memory_delta": end_memory - start_memory,
            "result": result
        }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage."""
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    
    @pytest.mark.asyncio
    async def test_circuit_creation_performance(self, predictor):
        """Benchmark circuit creation."""
        metrics = await self._measure_execution_time(
            predictor.create_circuit,
            n_qubits=4,
            n_layers=2
        )
        
        assert metrics["execution_time"] < 1.0  # Should take less than 1 second
        assert metrics["memory_delta"] < 50  # Should use less than 50MB additional memory
    
    @pytest.mark.asyncio
    async def test_training_performance(self, predictor):
        """Benchmark model training."""
        price_data = [100 + i for i in range(100)]  # 100 data points
        
        metrics = await self._measure_execution_time(
            predictor.train,
            price_data
        )
        
        assert metrics["execution_time"] < 5.0  # Should take less than 5 seconds
        assert metrics["memory_delta"] < 100  # Should use less than 100MB additional memory
    
    @pytest.mark.asyncio
    async def test_prediction_performance(self, predictor, mock_quantum_circuit):
        """Benchmark price prediction."""
        # Train first
        price_data = [100 + i for i in range(100)]
        await predictor.train(price_data)
        
        metrics = await self._measure_execution_time(
            predictor.predict_price,
            window_size=5
        )
        
        assert metrics["execution_time"] < 1.0  # Should take less than 1 second
        assert metrics["memory_delta"] < 50  # Should use less than 50MB additional memory

@pytest.mark.benchmark
class TestFlashLoanPerformance:
    """Benchmark flash loan operations."""
    
    @pytest.fixture
    async def agent(self, web3_provider, http_client, xrpl_client, test_wallet):
        """Create flash loan agent."""
        return FlashLoanAgent(
            web3_client=web3_provider,
            bridge_client=http_client,
            hooks_client=xrpl_client
        )
    
    @pytest.mark.asyncio
    async def test_opportunity_detection_performance(self, agent):
        """Benchmark opportunity detection."""
        metrics = await self._measure_execution_time(
            agent.find_opportunities,
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            min_profit=Decimal("0.1"),
            max_slippage=Decimal("0.01")
        )
        
        assert metrics["execution_time"] < 2.0  # Should take less than 2 seconds
        assert metrics["memory_delta"] < 100  # Should use less than 100MB additional memory
    
    @pytest.mark.asyncio
    async def test_flash_loan_execution_performance(self, agent):
        """Benchmark flash loan execution."""
        metrics = await self._measure_execution_time(
            agent.execute_flash_loan,
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            amount=Decimal("1000000000000000000"),
            target_chain=2
        )
        
        assert metrics["execution_time"] < 30.0  # Should take less than 30 seconds
        assert metrics["memory_delta"] < 200  # Should use less than 200MB additional memory

@pytest.mark.benchmark
class TestConcurrencyPerformance:
    """Benchmark concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_parallel_predictions(self):
        """Benchmark parallel price predictions."""
        predictors = [
            QuantumPricePredictor(n_qubits=2, n_layers=1)
            for _ in range(5)
        ]
        
        start_time = time.perf_counter()
        start_memory = self._get_memory_usage()
        
        # Run predictions in parallel
        tasks = [
            predictor.predict_price(window_size=5)
            for predictor in predictors
        ]
        results = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        end_memory = self._get_memory_usage()
        
        execution_time = end_time - start_time
        memory_delta = end_memory - start_memory
        
        assert execution_time < 2.0  # Should take less than 2 seconds
        assert memory_delta < 250  # Should use less than 250MB additional memory
        assert len(results) == 5  # Should have 5 predictions
    
    @pytest.mark.asyncio
    async def test_parallel_risk_calculations(self):
        """Benchmark parallel risk calculations."""
        risk_managers = [
            QuantumRiskManager(n_assets=3)
            for _ in range(3)
        ]
        
        portfolio_values = [1000000, 2000000, 3000000]
        weights = [[0.3, 0.3, 0.4] for _ in range(3)]
        volatilities = [[0.1, 0.15, 0.2] for _ in range(3)]
        
        start_time = time.perf_counter()
        start_memory = self._get_memory_usage()
        
        # Run VaR calculations in parallel
        tasks = [
            risk_manager.calculate_var(pv, w, v)
            for risk_manager, pv, w, v in zip(risk_managers, portfolio_values, weights, volatilities)
        ]
        results = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        end_memory = self._get_memory_usage()
        
        execution_time = end_time - start_time
        memory_delta = end_memory - start_memory
        
        assert execution_time < 3.0  # Should take less than 3 seconds
        assert memory_delta < 300  # Should use less than 300MB additional memory
        assert len(results) == 3  # Should have 3 VaR calculations
