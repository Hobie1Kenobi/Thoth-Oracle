"""Tests for Web3 client integration."""

import pytest
from unittest.mock import Mock, patch
from web3 import Web3
from eth_typing import Address
from integrations.web3_client import Web3Client

@pytest.fixture
def web3_client():
    """Create a Web3Client instance for testing."""
    return Web3Client("https://mainnet.infura.io/v3/test-project-id")

@pytest.fixture
def mock_contract():
    """Create a mock contract."""
    return Mock()

@pytest.mark.asyncio
async def test_get_flash_loan_contract(web3_client, mock_contract):
    """Test getting flash loan contract."""
    with patch.object(Web3, 'eth', create=True) as mock_eth:
        mock_eth.contract.return_value = mock_contract
        contract = await web3_client.get_flash_loan_contract(
            "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9"
        )
        assert contract is not None
        assert contract == mock_contract

@pytest.mark.asyncio
async def test_execute_flash_loan(web3_client, mock_contract):
    """Test executing flash loan."""
    test_params = {
        "onBehalfOf": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "params": b""
    }
    
    with patch.object(web3_client, 'get_flash_loan_contract') as mock_get_contract:
        mock_get_contract.return_value = mock_contract
        mock_contract.functions.flashLoan.return_value.build_transaction.return_value = {
            'hash': '0x123'
        }
        
        result = await web3_client.execute_flash_loan(
            "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
            1000000,
            Address(bytes.fromhex("6B175474E89094C44Da98b954EedeAC495271d0F")),
            test_params
        )
        
        assert result is not None
        assert result['hash'] == '0x123'
        mock_contract.functions.flashLoan.assert_called_once()

@pytest.mark.asyncio
async def test_execute_flash_loan_failure(web3_client):
    """Test flash loan execution failure."""
    with patch.object(web3_client, 'get_flash_loan_contract') as mock_get_contract:
        mock_get_contract.return_value = None
        
        with pytest.raises(Exception) as exc_info:
            await web3_client.execute_flash_loan(
                "0x123",
                1000000,
                Address(bytes.fromhex("6B175474E89094C44Da98b954EedeAC495271d0F")),
                {}
            )
        assert "Failed to get flash loan contract" in str(exc_info.value)
