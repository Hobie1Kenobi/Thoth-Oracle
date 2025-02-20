"""Tests for monitoring and logging functionality."""

import pytest
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

@pytest.mark.monitoring
class TestLogging:
    """Test logging functionality."""
    
    @pytest.fixture
    def log_file(self, tmp_path):
        """Create temporary log file."""
        return tmp_path / "test.log"
    
    @pytest.fixture
    def logger(self, log_file):
        """Set up logger."""
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def test_log_levels(self, logger, log_file):
        """Test different log levels."""
        test_messages = {
            "debug": "Debug message",
            "info": "Info message",
            "warning": "Warning message",
            "error": "Error message",
            "critical": "Critical message"
        }
        
        for level, message in test_messages.items():
            getattr(logger, level)(message)
        
        log_content = log_file.read_text()
        for message in test_messages.values():
            assert message in log_content
    
    def test_structured_logging(self, logger, log_file):
        """Test structured logging with JSON."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "flash_loan_execution",
            "amount": "1.0 ETH",
            "gas_price": "50 gwei",
            "status": "success"
        }
        
        logger.info(json.dumps(log_data))
        
        log_content = log_file.read_text()
        assert "flash_loan_execution" in log_content
        assert "1.0 ETH" in log_content

@pytest.mark.monitoring
class TestMetrics:
    """Test metrics collection."""
    
    @pytest.fixture
    def metrics_file(self, tmp_path):
        """Create temporary metrics file."""
        return tmp_path / "metrics.json"
    
    def _write_metrics(self, metrics_file: Path, metrics: Dict[str, Any]):
        """Write metrics to file."""
        metrics_file.write_text(json.dumps(metrics))
    
    def _read_metrics(self, metrics_file: Path) -> Dict[str, Any]:
        """Read metrics from file."""
        return json.loads(metrics_file.read_text())
    
    def test_performance_metrics(self, metrics_file):
        """Test performance metrics collection."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "quantum_circuit_creation_time": 0.5,
            "prediction_time": 1.2,
            "memory_usage": 256.5,
            "cpu_usage": 45.2
        }
        
        self._write_metrics(metrics_file, metrics)
        loaded_metrics = self._read_metrics(metrics_file)
        
        assert loaded_metrics["quantum_circuit_creation_time"] == 0.5
        assert loaded_metrics["prediction_time"] == 1.2
    
    def test_transaction_metrics(self, metrics_file):
        """Test transaction metrics collection."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "total_transactions": 100,
            "successful_transactions": 95,
            "failed_transactions": 5,
            "average_gas_price": "45 gwei",
            "total_gas_used": 1500000
        }
        
        self._write_metrics(metrics_file, metrics)
        loaded_metrics = self._read_metrics(metrics_file)
        
        assert loaded_metrics["total_transactions"] == 100
        assert loaded_metrics["successful_transactions"] == 95
        assert loaded_metrics["failed_transactions"] == 5

@pytest.mark.monitoring
class TestAlerts:
    """Test alerting functionality."""
    
    @pytest.fixture
    def alert_file(self, tmp_path):
        """Create temporary alert file."""
        return tmp_path / "alerts.json"
    
    def _write_alert(self, alert_file: Path, alert: Dict[str, Any]):
        """Write alert to file."""
        alerts = []
        if alert_file.exists():
            alerts = json.loads(alert_file.read_text())
        alerts.append(alert)
        alert_file.write_text(json.dumps(alerts))
    
    def test_error_alerts(self, alert_file):
        """Test error alerting."""
        error_alert = {
            "timestamp": datetime.now().isoformat(),
            "level": "ERROR",
            "component": "flash_loan_agent",
            "message": "Flash loan execution failed",
            "details": {
                "error_type": "ContractError",
                "transaction_hash": "0x123..."
            }
        }
        
        self._write_alert(alert_file, error_alert)
        alerts = json.loads(alert_file.read_text())
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "ERROR"
        assert alerts[0]["component"] == "flash_loan_agent"
    
    def test_threshold_alerts(self, alert_file):
        """Test threshold-based alerting."""
        threshold_alert = {
            "timestamp": datetime.now().isoformat(),
            "level": "WARNING",
            "component": "risk_manager",
            "message": "VaR threshold exceeded",
            "details": {
                "current_var": 150000,
                "threshold": 100000,
                "portfolio_id": "port_123"
            }
        }
        
        self._write_alert(alert_file, threshold_alert)
        alerts = json.loads(alert_file.read_text())
        
        assert len(alerts) == 1
        assert alerts[0]["level"] == "WARNING"
        assert alerts[0]["component"] == "risk_manager"
    
    def test_multiple_alerts(self, alert_file):
        """Test handling multiple alerts."""
        alerts = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "component": "quantum_predictor",
                "message": "Prediction accuracy below threshold",
                "details": {"accuracy": 0.85, "threshold": 0.9}
            },
            {
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "component": "bridge_client",
                "message": "Bridge transaction timeout",
                "details": {"tx_hash": "0x456..."}
            }
        ]
        
        for alert in alerts:
            self._write_alert(alert_file, alert)
        
        saved_alerts = json.loads(alert_file.read_text())
        assert len(saved_alerts) == 2
        assert saved_alerts[0]["level"] == "INFO"
        assert saved_alerts[1]["level"] == "ERROR"
