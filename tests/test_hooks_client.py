"""Tests for XRPL Hooks client integration."""

import pytest
from unittest.mock import Mock, patch
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from integrations.hooks_client import XRPLHooksClient

@pytest.fixture
def mock_client():
    """Create a mock XRPL client."""
    return Mock(spec=JsonRpcClient)

@pytest.fixture
def mock_wallet():
    """Create a mock wallet."""
    wallet = Mock(spec=Wallet)
    wallet.classic_address = "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh"
    return wallet

@pytest.fixture
def hooks_client(mock_client, mock_wallet):
    """Create an XRPLHooksClient instance for testing."""
    return XRPLHooksClient(
        mock_client,
        mock_wallet,
        "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
    )

@pytest.mark.asyncio
async def test_deploy_hook(hooks_client, mock_wallet):
    """Test deploying a hook."""
    mock_response = {
        "engine_result": "tesSUCCESS",
        "engine_result_code": 0,
        "tx_json": {
            "hash": "ABC123"
        }
    }
    
    hooks_client.client.submit = Mock(return_value=mock_response)
    mock_wallet.sign_transaction = Mock(return_value="signed_tx")
    
    result = await hooks_client.deploy_hook(
        b"hook_binary",
        {
            "HookOn": "Payment",
            "HookNamespace": "00000000",
            "HookParameters": []
        }
    )
    
    assert result is not None
    assert result["engine_result"] == "tesSUCCESS"
    assert result["tx_json"]["hash"] == "ABC123"

@pytest.mark.asyncio
async def test_get_hook_state(hooks_client):
    """Test getting hook state."""
    mock_response = {
        "node": {
            "HookState": b"state_data"
        }
    }
    
    hooks_client.client.request = Mock(return_value=mock_response)
    
    result = await hooks_client.get_hook_state(
        "namespace123",
        "key456"
    )
    
    assert result == b"state_data"
    hooks_client.client.request.assert_called_once()

@pytest.mark.asyncio
async def test_execute_hook_transaction(hooks_client, mock_wallet):
    """Test executing a hook transaction."""
    mock_response = {
        "engine_result": "tesSUCCESS",
        "engine_result_code": 0,
        "tx_json": {
            "hash": "XYZ789"
        }
    }
    
    hooks_client.client.submit = Mock(return_value=mock_response)
    mock_wallet.sign_transaction = Mock(return_value="signed_tx")
    
    result = await hooks_client.execute_hook_transaction(
        "Payment",
        {
            "Amount": "1000000",
            "Destination": "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
        }
    )
    
    assert result is not None
    assert result["engine_result"] == "tesSUCCESS"
    assert result["tx_json"]["hash"] == "XYZ789"

@pytest.mark.asyncio
async def test_get_hook_definitions(hooks_client):
    """Test getting hook definitions."""
    mock_response = {
        "account_data": {
            "Hooks": [
                {
                    "Hook": {
                        "CreateCode": "binary_data",
                        "HookOn": "Payment",
                        "HookNamespace": "00000000"
                    }
                }
            ]
        }
    }
    
    hooks_client.client.request = Mock(return_value=mock_response)
    
    result = await hooks_client.get_hook_definitions()
    
    assert result is not None
    assert len(result) == 1
    assert result[0]["Hook"]["HookOn"] == "Payment"
