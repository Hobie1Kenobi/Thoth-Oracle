"""Load and performance tests for the Thoth Oracle system."""

import pytest
import asyncio
import time
import numpy as np
from decimal import Decimal
from unittest.mock import Mock, patch
from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager
from integrations.hooks_client import XRPLHooksClient
from integrations.across_bridge import AcrossBridgeClient

@pytest.mark.performance
class TestLoadAndPerformance:
    """Load and performance test suite."""
    
    @pytest.fixture
    async def system_components(self):
        """Initialize all system components."""
        mock_web3 = Mock()
        mock_xrpl = Mock()
        mock_http = Mock()
        
        flash_loan_agent = FlashLoanAgent(
            web3_client=mock_web3,
            bridge_client=mock_http,
            hooks_client=mock_xrpl
        )
        
        price_predictor = QuantumPricePredictor(n_qubits=3, n_layers=2)
        risk_manager = QuantumRiskManager(n_assets=3)
        hooks_client = XRPLHooksClient(
            client=mock_xrpl,
            wallet=None,
            hook_account="rHookAccount"
        )
        bridge_client = AcrossBridgeClient(http_client=mock_http)
        
        return {
            "flash_loan_agent": flash_loan_agent,
            "price_predictor": price_predictor,
            "risk_manager": risk_manager,
            "hooks_client": hooks_client,
            "bridge_client": bridge_client
        }
    
    @pytest.mark.asyncio
    async def test_concurrent_flash_loans(self, system_components):
        """Test system performance under concurrent flash loan operations."""
        flash_loan_agent = system_components["flash_loan_agent"]
        
        # Configure test parameters
        n_concurrent = 100
        expected_max_time = 10  # seconds
        
        # Prepare concurrent tasks
        tasks = []
        start_time = time.time()
        
        for i in range(n_concurrent):
            tasks.append(
                flash_loan_agent.execute_flash_loan(
                    token_address=f"0xtoken_{i}",
                    amount=Decimal("1000"),
                    target_chain=2
                )
            )
        
        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        execution_time = end_time - start_time
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        # Assert performance metrics
        assert execution_time < expected_max_time
        assert success_count / n_concurrent >= 0.95  # 95% success rate
        assert error_count / n_concurrent <= 0.05    # 5% error rate
    
    @pytest.mark.asyncio
    async def test_quantum_prediction_scaling(self, system_components):
        """Test quantum prediction system scaling with increasing load."""
        price_predictor = system_components["price_predictor"]
        
        # Test parameters
        batch_sizes = [10, 50, 100, 200]
        max_time_per_prediction = 0.1  # seconds
        
        for batch_size in batch_sizes:
            # Generate test data
            historical_prices = [
                100 + i + np.random.normal(0, 1)
                for i in range(batch_size)
            ]
            
            # Measure training time
            start_time = time.time()
            await price_predictor.train(historical_prices)
            training_time = time.time() - start_time
            
            # Measure prediction time
            start_time = time.time()
            prediction = await price_predictor.predict_price(window_size=5)
            prediction_time = time.time() - start_time
            
            # Assert performance
            assert 0 <= prediction <= 1
            assert prediction_time < max_time_per_prediction
            assert training_time < max_time_per_prediction * batch_size
    
    @pytest.mark.asyncio
    async def test_risk_calculation_performance(self, system_components):
        """Test risk calculation performance under heavy load."""
        risk_manager = system_components["risk_manager"]
        
        # Test parameters
        n_portfolios = 100
        max_time_per_calculation = 0.1  # seconds
        
        # Generate test portfolios
        portfolios = []
        for _ in range(n_portfolios):
            weights = np.random.random(3)
            weights = weights / sum(weights)
            portfolios.append({
                "value": Decimal(str(np.random.randint(1000000, 10000000))),
                "weights": weights.tolist(),
                "volatilities": [0.15, 0.12, 0.18]
            })
        
        # Measure calculation time
        start_time = time.time()
        tasks = [
            risk_manager.calculate_risk_metrics(portfolio)
            for portfolio in portfolios
        ]
        results = await asyncio.gather(*tasks)
        calculation_time = time.time() - start_time
        
        # Assert performance
        assert calculation_time < max_time_per_calculation * n_portfolios
        assert all("var_95" in result for result in results)
    
    @pytest.mark.asyncio
    async def test_hook_execution_throughput(self, system_components):
        """Test XRPL hook execution throughput."""
        hooks_client = system_components["hooks_client"]
        
        # Test parameters
        n_executions = 1000
        target_tps = 100  # transactions per second
        max_latency = 0.1  # seconds
        
        # Prepare hook calls
        tasks = []
        latencies = []
        
        for i in range(n_executions):
            start_time = time.time()
            task = hooks_client.execute_hook(
                "amm",
                "swap",
                {"amount": str(1000 + i)}
            )
            tasks.append(task)
            
            # Measure latency
            result = await task
            latency = time.time() - start_time
            latencies.append(latency)
            
            # Simulate natural transaction flow
            if i % target_tps == 0:
                await asyncio.sleep(1)
        
        # Calculate metrics
        average_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        actual_tps = n_executions / sum(latencies)
        
        # Assert performance
        assert average_latency < max_latency
        assert p95_latency < max_latency * 2
        assert actual_tps >= target_tps * 0.9  # Within 90% of target
    
    @pytest.mark.asyncio
    async def test_bridge_scaling_performance(self, system_components):
        """Test bridge performance under increasing load."""
        bridge_client = system_components["bridge_client"]
        
        # Test parameters
        n_requests = [10, 50, 100, 500]
        max_time_per_request = 0.2  # seconds
        
        for n in n_requests:
            # Prepare concurrent requests
            tasks = []
            start_time = time.time()
            
            for i in range(n):
                tasks.append(
                    bridge_client.get_bridge_quote(
                        "USDC",
                        "USDC",
                        str(1000 + i),
                        1,
                        2
                    )
                )
            
            # Execute requests
            results = await asyncio.gather(*tasks)
            execution_time = time.time() - start_time
            
            # Assert performance
            assert execution_time < max_time_per_request * n
            assert all(r["quoteId"] is not None for r in results)
    
    @pytest.mark.asyncio
    async def test_system_memory_usage(self, system_components):
        """Test system memory usage under load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Execute heavy operations
        tasks = []
        components = system_components
        
        # 1. Multiple price predictions
        for _ in range(10):
            tasks.append(components["price_predictor"].predict_price(window_size=5))
        
        # 2. Multiple risk calculations
        portfolio = {
            "value": Decimal("1000000"),
            "weights": [0.4, 0.3, 0.3],
            "volatilities": [0.15, 0.12, 0.18]
        }
        for _ in range(10):
            tasks.append(components["risk_manager"].calculate_risk_metrics(portfolio))
        
        # 3. Multiple flash loan operations
        for _ in range(10):
            tasks.append(
                components["flash_loan_agent"].find_opportunities(
                    token_address="0xtoken",
                    min_profit=Decimal("0.1"),
                    max_slippage=Decimal("0.01")
                )
            )
        
        # Execute all tasks
        await asyncio.gather(*tasks)
        
        # Check memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Assert reasonable memory usage (less than 500MB increase)
        assert memory_increase < 500 * 1024 * 1024  # 500MB in bytes
    
    @pytest.mark.asyncio
    async def test_error_rate_under_load(self, system_components):
        """Test system error rates under heavy load."""
        components = system_components
        
        # Test parameters
        n_operations = 1000
        max_error_rate = 0.05  # 5%
        
        # Track errors
        error_counts = {
            "flash_loan": 0,
            "prediction": 0,
            "risk": 0,
            "hook": 0,
            "bridge": 0
        }
        
        # Execute operations
        for _ in range(n_operations):
            try:
                await components["flash_loan_agent"].execute_flash_loan(
                    token_address="0xtoken",
                    amount=Decimal("1000"),
                    target_chain=2
                )
            except Exception:
                error_counts["flash_loan"] += 1
            
            try:
                await components["price_predictor"].predict_price(window_size=5)
            except Exception:
                error_counts["prediction"] += 1
            
            try:
                await components["risk_manager"].calculate_risk_metrics({
                    "value": Decimal("1000000"),
                    "weights": [0.4, 0.3, 0.3],
                    "volatilities": [0.15, 0.12, 0.18]
                })
            except Exception:
                error_counts["risk"] += 1
            
            try:
                await components["hooks_client"].execute_hook(
                    "amm",
                    "swap",
                    {"amount": "1000"}
                )
            except Exception:
                error_counts["hook"] += 1
            
            try:
                await components["bridge_client"].get_bridge_quote(
                    "USDC",
                    "USDC",
                    "1000",
                    1,
                    2
                )
            except Exception:
                error_counts["bridge"] += 1
        
        # Assert error rates
        for component, count in error_counts.items():
            error_rate = count / n_operations
            assert error_rate <= max_error_rate, f"{component} error rate too high: {error_rate}"
