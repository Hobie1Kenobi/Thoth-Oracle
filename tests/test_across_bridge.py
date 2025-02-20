"""Tests for Across Protocol bridge integration."""

import pytest
from unittest.mock import Mock, patch
from aiohttp import ClientSession
from integrations.across_bridge import AcrossBridgeClient

@pytest.fixture
async def bridge_client():
    """Create an AcrossBridgeClient instance for testing."""
    client = AcrossBridgeClient()
    await client.__aenter__()
    yield client
    await client.__aexit__(None, None, None)

@pytest.mark.asyncio
async def test_get_bridge_quote(bridge_client):
    """Test getting bridge quote."""
    mock_response = {
        "quoteId": "123",
        "estimatedTime": 120,
        "fee": "0.1",
        "route": {
            "fromChain": 1,
            "toChain": 2,
            "fromToken": "USDC",
            "toToken": "USDC",
            "amount": "1000"
        }
    }
    
    with patch.object(ClientSession, 'get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = Mock(
            return_value=mock_response
        )
        
        result = await bridge_client.get_bridge_quote(
            "USDC",
            "USDC",
            "1000",
            1,
            2
        )
        
        assert result is not None
        assert result["quoteId"] == "123"
        assert result["route"]["fromChain"] == 1
        assert result["route"]["toChain"] == 2

@pytest.mark.asyncio
async def test_submit_bridge_transaction(bridge_client):
    """Test submitting bridge transaction."""
    mock_response = {
        "status": "pending",
        "txHash": "0x123",
        "estimatedCompletionTime": 120
    }
    
    with patch.object(ClientSession, 'post') as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json = Mock(
            return_value=mock_response
        )
        
        result = await bridge_client.submit_bridge_transaction(
            "123",
            "0x456"
        )
        
        assert result is not None
        assert result["status"] == "pending"
        assert result["txHash"] == "0x123"

@pytest.mark.asyncio
async def test_get_bridge_status(bridge_client):
    """Test getting bridge status."""
    mock_response = {
        "status": "completed",
        "fromChain": {
            "txHash": "0x123",
            "confirmations": 12
        },
        "toChain": {
            "txHash": "0x456",
            "confirmations": 5
        }
    }
    
    with patch.object(ClientSession, 'get') as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.json = Mock(
            return_value=mock_response
        )
        
        result = await bridge_client.get_bridge_status("0x123")
        
        assert result is not None
        assert result["status"] == "completed"
        assert result["fromChain"]["confirmations"] == 12
