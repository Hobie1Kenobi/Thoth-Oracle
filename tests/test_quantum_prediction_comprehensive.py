"""Comprehensive tests for quantum prediction system."""

import pytest
import numpy as np
from qiskit import QuantumCircuit, execute, Aer
from qiskit.circuit import Parameter
from qiskit.algorithms.optimizers import SPSA
from examples.quantum_prediction import QuantumPricePredictor

@pytest.mark.comprehensive
class TestQuantumPredictionComprehensive:
    """Comprehensive test suite for quantum prediction."""
    
    @pytest.fixture
    def predictor(self):
        """Create quantum price predictor."""
        return QuantumPricePredictor(n_qubits=2, n_layers=2)
    
    @pytest.fixture
    def simulator(self):
        """Create quantum simulator."""
        return Aer.get_backend('aer_simulator')
    
    def test_circuit_initialization_detailed(self, predictor):
        """Test detailed circuit initialization."""
        # Test circuit structure
        assert predictor.circuit.num_qubits == predictor.n_qubits
        assert predictor.circuit.num_clbits == predictor.n_qubits
        
        # Test parameter count
        expected_params = predictor.n_qubits * predictor.n_layers * 3  # 3 parameters per qubit per layer
        assert len(predictor.parameters) == expected_params
        
        # Test parameter names
        for i in range(predictor.n_layers):
            for j in range(predictor.n_qubits):
                param_names = [
                    f"θ_{i}_{j}",
                    f"φ_{i}_{j}",
                    f"λ_{i}_{j}"
                ]
                for name in param_names:
                    assert any(p.name == name for p in predictor.parameters)
    
    @pytest.mark.asyncio
    async def test_feature_mapping_detailed(self, predictor):
        """Test detailed feature mapping."""
        # Test with various input types
        test_cases = [
            [100, 101, 102],  # Simple increasing
            [100, 99, 98],    # Simple decreasing
            [100, 100, 100],  # Constant
            [100, 150, 50]    # Volatile
        ]
        
        for data in test_cases:
            features = await predictor.create_quantum_features(data)
            assert features.shape[1] == predictor.n_qubits * 2
            assert np.all(features >= -1) and np.all(features <= 1)
            
            # Test normalization
            assert np.abs(np.mean(features)) < 0.1  # Should be roughly centered
            assert np.std(features) < 1.1  # Should have reasonable spread
    
    @pytest.mark.asyncio
    async def test_circuit_execution_detailed(self, predictor, simulator):
        """Test detailed circuit execution."""
        # Test with various parameter sets
        test_params = [
            np.zeros(len(predictor.parameters)),
            np.ones(len(predictor.parameters)),
            np.random.random(len(predictor.parameters))
        ]
        
        for params in test_params:
            # Bind parameters
            bound_circuit = predictor.circuit.bind_parameters(
                dict(zip(predictor.parameters, params))
            )
            
            # Execute circuit
            result = execute(
                bound_circuit,
                simulator,
                shots=1000
            ).result()
            
            # Check counts
            counts = result.get_counts(bound_circuit)
            assert sum(counts.values()) == 1000
            assert all(len(state) == predictor.n_qubits for state in counts.keys())
    
    @pytest.mark.asyncio
    async def test_training_detailed(self, predictor):
        """Test detailed training process."""
        # Test with different data patterns
        test_cases = [
            {
                "data": [100 + i for i in range(10)],  # Trend
                "expected_trend": "up"
            },
            {
                "data": [100 - i for i in range(10)],  # Trend
                "expected_trend": "down"
            },
            {
                "data": [100 + ((-1)**i) for i in range(10)],  # Oscillating
                "expected_trend": "oscillating"
            }
        ]
        
        for case in test_cases:
            # Train model
            await predictor.train(case["data"])
            
            # Verify optimal parameters exist
            assert hasattr(predictor, 'optimal_params')
            assert len(predictor.optimal_params) == len(predictor.parameters)
            
            # Make prediction
            prediction = await predictor.predict_price(window_size=5)
            
            # Verify prediction is valid
            assert 0 <= prediction <= 1
            
            # Verify trend alignment
            if case["expected_trend"] == "up":
                assert prediction > 0.5
            elif case["expected_trend"] == "down":
                assert prediction < 0.5
    
    @pytest.mark.asyncio
    async def test_optimization_detailed(self, predictor):
        """Test detailed optimization process."""
        # Test SPSA optimizer with different configurations
        test_configs = [
            {"maxiter": 50, "learning_rate": 0.1},
            {"maxiter": 100, "learning_rate": 0.01},
            {"maxiter": 200, "learning_rate": 0.001}
        ]
        
        test_data = [100 + i for i in range(10)]
        
        for config in test_configs:
            optimizer = SPSA(
                maxiter=config["maxiter"],
                learning_rate=config["learning_rate"]
            )
            
            # Set optimizer
            predictor.optimizer = optimizer
            
            # Train model
            await predictor.train(test_data)
            
            # Verify optimization results
            assert hasattr(predictor, 'optimal_params')
            assert len(predictor.optimal_params) == len(predictor.parameters)
            assert predictor.optimization_result is not None
            assert predictor.optimization_result.nfev <= config["maxiter"]
    
    @pytest.mark.asyncio
    async def test_prediction_confidence_detailed(self, predictor):
        """Test detailed prediction confidence calculation."""
        # Train model first
        train_data = [100 + i for i in range(10)]
        await predictor.train(train_data)
        
        # Test confidence calculation with different window sizes
        window_sizes = [3, 5, 7]
        
        for window_size in window_sizes:
            prediction, confidence = await predictor.predict_with_confidence(
                window_size=window_size
            )
            
            assert 0 <= prediction <= 1
            assert 0 <= confidence <= 1
            
            # Verify confidence calculation
            # More recent data should give higher confidence
            recent_confidence = await predictor.predict_with_confidence(window_size=3)
            older_confidence = await predictor.predict_with_confidence(window_size=7)
            assert recent_confidence[1] >= older_confidence[1]
    
    @pytest.mark.asyncio
    async def test_error_metrics_detailed(self, predictor):
        """Test detailed error metrics calculation."""
        # Train and generate predictions
        train_data = [100 + i for i in range(20)]
        test_data = train_data[-5:]
        
        await predictor.train(train_data[:-5])
        
        predictions = []
        for i in range(len(test_data)):
            pred = await predictor.predict_price(window_size=5)
            predictions.append(pred)
        
        # Calculate various error metrics
        metrics = await predictor.calculate_error_metrics(
            actual=test_data,
            predicted=predictions
        )
        
        assert "mae" in metrics
        assert "mse" in metrics
        assert "rmse" in metrics
        assert metrics["mae"] >= 0
        assert metrics["mse"] >= 0
        assert metrics["rmse"] >= 0
        assert metrics["rmse"] == np.sqrt(metrics["mse"])
    
    @pytest.mark.asyncio
    async def test_ensemble_prediction_detailed(self, predictor):
        """Test detailed ensemble prediction."""
        # Create ensemble of predictors
        n_models = 5
        predictors = [
            QuantumPricePredictor(n_qubits=2, n_layers=2)
            for _ in range(n_models)
        ]
        
        # Train all models
        train_data = [100 + i for i in range(10)]
        for pred in predictors:
            await pred.train(train_data)
        
        # Get ensemble prediction
        predictions = []
        for pred in predictors:
            pred_value = await pred.predict_price(window_size=5)
            predictions.append(pred_value)
        
        # Calculate ensemble statistics
        ensemble_mean = np.mean(predictions)
        ensemble_std = np.std(predictions)
        
        assert 0 <= ensemble_mean <= 1
        assert ensemble_std >= 0
        
        # Verify ensemble reduces variance
        individual_predictions = []
        for _ in range(5):
            pred = await predictor.predict_price(window_size=5)
            individual_predictions.append(pred)
        
        individual_std = np.std(individual_predictions)
        assert ensemble_std <= individual_std
