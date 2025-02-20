"""Comprehensive tests for bridge client integration."""

import pytest
import json
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch
from integrations.across_bridge import AcrossBridgeClient

@pytest.mark.comprehensive
class TestBridgeClientComprehensive:
    """Comprehensive test suite for bridge client."""
    
    @pytest.fixture
    async def mock_http_client(self):
        """Create mock HTTP client."""
        client = Mock()
        client.post.return_value.json.return_value = {
            "status": "success",
            "data": {}
        }
        client.get.return_value.json.return_value = {
            "status": "success",
            "data": {}
        }
        return client
    
    @pytest.fixture
    async def bridge_client(self, mock_http_client):
        """Create bridge client."""
        return AcrossBridgeClient(http_client=mock_http_client)
    
    @pytest.mark.asyncio
    async def test_quote_retrieval_detailed(self, bridge_client):
        """Test detailed quote retrieval."""
        test_cases = [
            {
                "from_token": "USDC",
                "to_token": "USDC",
                "amount": "1000",
                "from_chain": 1,
                "to_chain": 2
            },
            {
                "from_token": "ETH",
                "to_token": "WETH",
                "amount": "10",
                "from_chain": 1,
                "to_chain": 137
            }
        ]
        
        for case in test_cases:
            quote = await bridge_client.get_bridge_quote(
                case["from_token"],
                case["to_token"],
                case["amount"],
                case["from_chain"],
                case["to_chain"]
            )
            
            assert quote is not None
            assert "quoteId" in quote
            assert "estimatedTime" in quote
            assert "fee" in quote
            assert "route" in quote
            assert quote["route"]["fromChain"] == case["from_chain"]
            assert quote["route"]["toChain"] == case["to_chain"]
    
    @pytest.mark.asyncio
    async def test_transaction_submission_detailed(self, bridge_client):
        """Test detailed transaction submission."""
        test_cases = [
            {
                "quote_id": "quote_123",
                "tx_hash": "0x123",
                "expected_status": "pending"
            },
            {
                "quote_id": "quote_456",
                "tx_hash": "0x456",
                "expected_status": "completed"
            }
        ]
        
        for case in test_cases:
            bridge_client.http_client.post.return_value.json.return_value = {
                "status": "success",
                "data": {
                    "status": case["expected_status"],
                    "txHash": case["tx_hash"]
                }
            }
            
            result = await bridge_client.submit_bridge_transaction(
                case["quote_id"],
                case["tx_hash"]
            )
            
            assert result is not None
            assert "status" in result
            assert "txHash" in result
            assert result["status"] == case["expected_status"]
            assert result["txHash"] == case["tx_hash"]
    
    @pytest.mark.asyncio
    async def test_transaction_status_detailed(self, bridge_client):
        """Test detailed transaction status checking."""
        test_cases = [
            {
                "tx_hash": "0x123",
                "status": "pending",
                "confirmations": 3
            },
            {
                "tx_hash": "0x456",
                "status": "completed",
                "confirmations": 12
            }
        ]
        
        for case in test_cases:
            bridge_client.http_client.get.return_value.json.return_value = {
                "status": "success",
                "data": {
                    "status": case["status"],
                    "fromChain": {
                        "confirmations": case["confirmations"]
                    }
                }
            }
            
            status = await bridge_client.get_bridge_status(case["tx_hash"])
            
            assert status is not None
            assert "status" in status
            assert "fromChain" in status
            assert status["status"] == case["status"]
            assert status["fromChain"]["confirmations"] == case["confirmations"]
    
    @pytest.mark.asyncio
    async def test_fee_calculation_detailed(self, bridge_client):
        """Test detailed fee calculation."""
        test_cases = [
            {
                "amount": "1000",
                "token": "USDC",
                "from_chain": 1,
                "to_chain": 2,
                "expected_fee": "10"
            },
            {
                "amount": "10",
                "token": "ETH",
                "from_chain": 1,
                "to_chain": 137,
                "expected_fee": "0.01"
            }
        ]
        
        for case in test_cases:
            bridge_client.http_client.get.return_value.json.return_value = {
                "status": "success",
                "data": {
                    "fee": case["expected_fee"]
                }
            }
            
            fee = await bridge_client.calculate_bridge_fee(
                case["amount"],
                case["token"],
                case["from_chain"],
                case["to_chain"]
            )
            
            assert fee is not None
            assert isinstance(fee, str)
            assert fee == case["expected_fee"]
    
    @pytest.mark.asyncio
    async def test_token_support_detailed(self, bridge_client):
        """Test detailed token support checking."""
        test_cases = [
            {
                "token": "USDC",
                "chain": 1,
                "expected": True
            },
            {
                "token": "INVALID",
                "chain": 1,
                "expected": False
            }
        ]
        
        for case in test_cases:
            bridge_client.http_client.get.return_value.json.return_value = {
                "status": "success",
                "data": {
                    "supported": case["expected"]
                }
            }
            
            supported = await bridge_client.is_token_supported(
                case["token"],
                case["chain"]
            )
            
            assert supported == case["expected"]
    
    @pytest.mark.asyncio
    async def test_chain_support_detailed(self, bridge_client):
        """Test detailed chain support checking."""
        test_cases = [
            {
                "from_chain": 1,
                "to_chain": 2,
                "expected": True
            },
            {
                "from_chain": 999,
                "to_chain": 1,
                "expected": False
            }
        ]
        
        for case in test_cases:
            bridge_client.http_client.get.return_value.json.return_value = {
                "status": "success",
                "data": {
                    "supported": case["expected"]
                }
            }
            
            supported = await bridge_client.is_route_supported(
                case["from_chain"],
                case["to_chain"]
            )
            
            assert supported == case["expected"]
    
    @pytest.mark.asyncio
    async def test_error_handling_detailed(self, bridge_client):
        """Test detailed error handling."""
        error_cases = [
            {
                "scenario": "invalid_quote",
                "expected_error": "Invalid quote ID"
            },
            {
                "scenario": "network_error",
                "expected_error": "Network error"
            },
            {
                "scenario": "insufficient_liquidity",
                "expected_error": "Insufficient liquidity"
            }
        ]
        
        for case in error_cases:
            if case["scenario"] == "invalid_quote":
                bridge_client.http_client.post.return_value.json.return_value = {
                    "status": "error",
                    "error": case["expected_error"]
                }
            elif case["scenario"] == "network_error":
                bridge_client.http_client.post.side_effect = asyncio.TimeoutError()
            elif case["scenario"] == "insufficient_liquidity":
                bridge_client.http_client.post.return_value.json.return_value = {
                    "status": "error",
                    "error": case["expected_error"]
                }
            
            with pytest.raises(Exception, match=case["expected_error"]):
                await bridge_client.submit_bridge_transaction(
                    "quote_123",
                    "0x123"
                )
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, bridge_client):
        """Test rate limiting functionality."""
        # Test rapid requests
        requests = []
        for _ in range(5):
            requests.append(
                bridge_client.get_bridge_quote(
                    "USDC",
                    "USDC",
                    "1000",
                    1,
                    2
                )
            )
        
        # Should not raise rate limit errors
        results = await asyncio.gather(*requests)
        assert len(results) == 5
        for result in results:
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, bridge_client):
        """Test timeout handling."""
        # Set a very short timeout
        bridge_client.timeout = 0.1
        bridge_client.http_client.post.side_effect = asyncio.sleep(0.2)
        
        with pytest.raises(asyncio.TimeoutError):
            await bridge_client.submit_bridge_transaction(
                "quote_123",
                "0x123"
            )
