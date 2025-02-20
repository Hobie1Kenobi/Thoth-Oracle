"""Comprehensive tests for XRPL hooks integration."""

import pytest
import json
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch
from xrpl.models.requests import Request
from xrpl.models.response import Response
from xrpl.models.transactions import Transaction
from xrpl.wallet import Wallet
from integrations.hooks_client import XRPLHooksClient

@pytest.mark.comprehensive
class TestXRPLHooksComprehensive:
    """Comprehensive test suite for XRPL hooks."""
    
    @pytest.fixture
    async def mock_xrpl_client(self):
        """Create mock XRPL client."""
        client = Mock()
        client.request.return_value = Response(
            status="success",
            result={"validated": True}
        )
        return client
    
    @pytest.fixture
    def test_wallet(self):
        """Create test wallet."""
        return Wallet.create()
    
    @pytest.fixture
    async def hooks_client(self, mock_xrpl_client, test_wallet):
        """Create XRPL Hooks client."""
        return XRPLHooksClient(
            client=mock_xrpl_client,
            wallet=test_wallet,
            hook_account="rHookAccount"
        )
    
    @pytest.mark.asyncio
    async def test_hook_installation_detailed(self, hooks_client):
        """Test detailed hook installation process."""
        # Test different hook types
        hook_types = ["amm", "flash_loan", "bridge"]
        
        for hook_type in hook_types:
            result = await hooks_client.install_hook(
                hook_type,
                {
                    "param1": "value1",
                    "param2": "value2"
                }
            )
            
            assert result is not None
            assert "tx_hash" in result
            assert "hook_hash" in result
            assert result["status"] == "success"
            
            # Verify hook installation
            hook_info = await hooks_client.get_hook_info(result["hook_hash"])
            assert hook_info["type"] == hook_type
            assert hook_info["account"] == hooks_client.hook_account
    
    @pytest.mark.asyncio
    async def test_hook_execution_detailed(self, hooks_client):
        """Test detailed hook execution."""
        test_cases = [
            {
                "hook_type": "amm",
                "function": "swap",
                "params": {"amount": "1000", "token": "XRP"}
            },
            {
                "hook_type": "flash_loan",
                "function": "borrow",
                "params": {"amount": "5000", "token": "USD"}
            },
            {
                "hook_type": "bridge",
                "function": "transfer",
                "params": {"amount": "1000", "destination": "ETH"}
            }
        ]
        
        for case in test_cases:
            result = await hooks_client.execute_hook(
                case["hook_type"],
                case["function"],
                case["params"]
            )
            
            assert result is not None
            assert "tx_hash" in result
            assert "status" in result
            assert result["status"] == "tesSUCCESS"
            
            # Verify transaction details
            tx_info = await hooks_client.get_transaction_info(result["tx_hash"])
            assert tx_info["validated"]
            assert tx_info["hook_type"] == case["hook_type"]
            assert tx_info["function"] == case["function"]
    
    @pytest.mark.asyncio
    async def test_hook_state_management(self, hooks_client):
        """Test hook state management."""
        # Test state operations
        test_states = [
            {
                "key": "total_liquidity",
                "value": "1000000",
                "type": "amount"
            },
            {
                "key": "last_price",
                "value": "1.2345",
                "type": "price"
            },
            {
                "key": "active_loans",
                "value": json.dumps({"loan1": "1000", "loan2": "2000"}),
                "type": "json"
            }
        ]
        
        for state in test_states:
            # Set state
            await hooks_client.set_hook_state(
                state["key"],
                state["value"],
                state["type"]
            )
            
            # Get state
            result = await hooks_client.get_hook_state(state["key"])
            assert result["value"] == state["value"]
            assert result["type"] == state["type"]
    
    @pytest.mark.asyncio
    async def test_hook_parameter_validation(self, hooks_client):
        """Test hook parameter validation."""
        test_cases = [
            {
                "valid": True,
                "params": {
                    "amount": "1000",
                    "token": "XRP",
                    "destination": "rDestination"
                }
            },
            {
                "valid": False,
                "params": {
                    "amount": "-1000",  # Invalid negative amount
                    "token": "XRP"
                }
            },
            {
                "valid": False,
                "params": {
                    "amount": "1000",
                    "token": "INVALID_TOKEN"  # Invalid token
                }
            }
        ]
        
        for case in test_cases:
            if case["valid"]:
                result = await hooks_client.validate_hook_params(case["params"])
                assert result is True
            else:
                with pytest.raises(ValueError):
                    await hooks_client.validate_hook_params(case["params"])
    
    @pytest.mark.asyncio
    async def test_hook_transaction_building(self, hooks_client):
        """Test hook transaction building."""
        test_cases = [
            {
                "type": "Payment",
                "params": {
                    "destination": "rDestination",
                    "amount": "1000",
                    "currency": "XRP"
                }
            },
            {
                "type": "TrustSet",
                "params": {
                    "currency": "USD",
                    "issuer": "rIssuer",
                    "value": "1000000"
                }
            }
        ]
        
        for case in test_cases:
            tx = await hooks_client.build_hook_transaction(
                case["type"],
                case["params"]
            )
            
            assert isinstance(tx, Transaction)
            assert tx.transaction_type == case["type"]
            
            # Verify transaction fields
            for key, value in case["params"].items():
                assert getattr(tx, key) == value
    
    @pytest.mark.asyncio
    async def test_hook_error_handling(self, hooks_client):
        """Test hook error handling."""
        error_cases = [
            {
                "scenario": "invalid_hook",
                "expected_error": "Hook not found"
            },
            {
                "scenario": "invalid_function",
                "expected_error": "Function not supported"
            },
            {
                "scenario": "insufficient_funds",
                "expected_error": "Insufficient funds"
            },
            {
                "scenario": "network_error",
                "expected_error": "Network error"
            }
        ]
        
        for case in error_cases:
            with pytest.raises(Exception, match=case["expected_error"]):
                if case["scenario"] == "invalid_hook":
                    await hooks_client.execute_hook(
                        "invalid_hook",
                        "function",
                        {}
                    )
                elif case["scenario"] == "invalid_function":
                    await hooks_client.execute_hook(
                        "amm",
                        "invalid_function",
                        {}
                    )
                elif case["scenario"] == "insufficient_funds":
                    hooks_client.client.request.side_effect = Exception("Insufficient funds")
                    await hooks_client.execute_hook(
                        "flash_loan",
                        "borrow",
                        {"amount": "1000000000"}
                    )
                elif case["scenario"] == "network_error":
                    hooks_client.client.request.side_effect = asyncio.TimeoutError()
                    await hooks_client.execute_hook(
                        "amm",
                        "swap",
                        {}
                    )
    
    @pytest.mark.asyncio
    async def test_hook_monitoring(self, hooks_client):
        """Test hook monitoring functionality."""
        # Test hook status monitoring
        hook_status = await hooks_client.get_hook_status("test_hook")
        assert "active" in hook_status
        assert "last_execution" in hook_status
        assert "total_executions" in hook_status
        
        # Test execution metrics
        metrics = await hooks_client.get_hook_metrics("test_hook")
        assert "success_rate" in metrics
        assert "average_execution_time" in metrics
        assert "error_rate" in metrics
        
        # Test resource usage
        resources = await hooks_client.get_hook_resources("test_hook")
        assert "memory_usage" in resources
        assert "storage_usage" in resources
        assert "execution_units" in resources
    
    @pytest.mark.asyncio
    async def test_hook_versioning(self, hooks_client):
        """Test hook versioning functionality."""
        # Test version management
        versions = await hooks_client.get_hook_versions("test_hook")
        assert len(versions) > 0
        for version in versions:
            assert "version" in version
            assert "deployment_date" in version
            assert "hash" in version
        
        # Test version upgrade
        upgrade_result = await hooks_client.upgrade_hook(
            "test_hook",
            "new_version"
        )
        assert upgrade_result["status"] == "success"
        assert upgrade_result["new_version"] == "new_version"
        
        # Verify upgrade
        current_version = await hooks_client.get_current_version("test_hook")
        assert current_version == "new_version"
