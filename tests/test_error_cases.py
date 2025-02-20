"""Test error cases and edge conditions."""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock
from web3.exceptions import ContractLogicError
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.exceptions import XRPLException

from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager
from integrations.web3_client import Web3Client
from integrations.hooks_client import XRPLHooksClient

@pytest.mark.error_cases
class TestFlashLoanErrors:
    """Test flash loan error handling."""
    
    @pytest.fixture
    async def agent(self, web3_provider, http_client, xrpl_client, test_wallet):
        """Create flash loan agent."""
        return FlashLoanAgent(
            web3_client=Mock(Web3Client),
            bridge_client=Mock(),
            hooks_client=Mock(XRPLHooksClient)
        )
    
    @pytest.mark.asyncio
    async def test_insufficient_liquidity(self, agent):
        """Test handling of insufficient liquidity."""
        agent.web3_client.get_pool_liquidity.return_value = Decimal("0.5")
        
        with pytest.raises(ValueError, match="Insufficient liquidity"):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1.0"),
                target_chain=2
            )
    
    @pytest.mark.asyncio
    async def test_failed_transaction(self, agent):
        """Test handling of failed transactions."""
        agent.web3_client.submit_transaction.side_effect = ContractLogicError("Execution reverted")
        
        with pytest.raises(ContractLogicError):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1.0"),
                target_chain=2
            )
    
    @pytest.mark.asyncio
    async def test_bridge_timeout(self, agent):
        """Test handling of bridge timeouts."""
        agent.bridge_client.submit_bridge_transaction.side_effect = asyncio.TimeoutError()
        
        with pytest.raises(asyncio.TimeoutError):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1.0"),
                target_chain=2
            )

@pytest.mark.error_cases
class TestQuantumErrors:
    """Test quantum component error handling."""
    
    @pytest.fixture
    def predictor(self):
        """Create quantum price predictor."""
        return QuantumPricePredictor(n_qubits=2, n_layers=1)
    
    @pytest.fixture
    def risk_manager(self):
        """Create quantum risk manager."""
        return QuantumRiskManager(n_assets=3)
    
    @pytest.mark.asyncio
    async def test_invalid_circuit_params(self, predictor):
        """Test handling of invalid circuit parameters."""
        with pytest.raises(ValueError, match="Invalid parameter count"):
            await predictor.update_circuit_params([0.1, 0.2])  # Too few parameters
    
    @pytest.mark.asyncio
    async def test_training_data_validation(self, predictor):
        """Test validation of training data."""
        with pytest.raises(ValueError, match="Insufficient data points"):
            await predictor.train([100])  # Too few data points
    
    @pytest.mark.asyncio
    async def test_invalid_portfolio_weights(self, risk_manager):
        """Test handling of invalid portfolio weights."""
        with pytest.raises(ValueError, match="Portfolio weights must sum to 1"):
            await risk_manager.calculate_var(
                1000000,
                [0.5, 0.2, 0.2],  # Weights don't sum to 1
                [0.1, 0.1, 0.1]
            )

@pytest.mark.error_cases
class TestHookErrors:
    """Test XRPL Hook error handling."""
    
    @pytest.fixture
    async def hooks_client(self, xrpl_client, test_wallet):
        """Create XRPL Hooks client."""
        return XRPLHooksClient(xrpl_client, test_wallet, "test_hook_account")
    
    @pytest.mark.asyncio
    async def test_invalid_hook_params(self, hooks_client):
        """Test handling of invalid hook parameters."""
        with pytest.raises(ValueError, match="Invalid parameter"):
            await hooks_client.install_hook(
                "invalid_hook",
                {"invalid_param": "value"}
            )
    
    @pytest.mark.asyncio
    async def test_hook_execution_failure(self, hooks_client):
        """Test handling of hook execution failures."""
        with pytest.raises(XRPLException):
            await hooks_client.execute_hook(
                "amm_hook",
                "invalid_function",
                {"amount": "1000"}
            )
    
    @pytest.mark.asyncio
    async def test_network_disconnect(self, hooks_client):
        """Test handling of network disconnections."""
        hooks_client.client = AsyncWebsocketClient("wss://invalid.endpoint")
        
        with pytest.raises(ConnectionError):
            await hooks_client.get_hook_state("test_hook")
