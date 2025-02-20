"""Unit tests for core components."""

import pytest
import asyncio
from decimal import Decimal
from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent
from integrations.web3_client import Web3Client
from integrations.across_bridge import AcrossBridgeClient
from integrations.hooks_client import XRPLHooksClient

@pytest.mark.core
class TestFlashLoanAgent:
    """Test flash loan agent functionality."""
    
    @pytest.fixture
    async def agent(self, web3_provider, http_client, xrpl_client, test_wallet):
        """Create flash loan agent."""
        web3_client = Web3Client(web3_provider)
        bridge_client = AcrossBridgeClient()
        hooks_client = XRPLHooksClient(xrpl_client, test_wallet, "test_hook_account")
        
        return FlashLoanAgent(
            web3_client=web3_client,
            bridge_client=bridge_client,
            hooks_client=hooks_client
        )
    
    @pytest.mark.asyncio
    async def test_opportunity_detection(self, agent, mock_quantum_circuit):
        """Test arbitrage opportunity detection."""
        opportunities = await agent.find_opportunities(
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            min_profit=Decimal("0.1"),
            max_slippage=Decimal("0.01")
        )
        
        assert opportunities is not None
        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert "profit" in opp
            assert "route" in opp
            assert "amount" in opp
            assert opp["profit"] >= Decimal("0.1")
    
    @pytest.mark.asyncio
    async def test_flash_loan_execution(self, agent):
        """Test flash loan execution."""
        result = await agent.execute_flash_loan(
            token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            amount=Decimal("1000000000000000000"),  # 1 ETH
            target_chain=2  # XRPL
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "status" in result
        assert result["status"] in ["pending", "completed"]
    
    @pytest.mark.asyncio
    async def test_profit_calculation(self, agent):
        """Test profit calculation."""
        profit = await agent.calculate_profit(
            input_amount=Decimal("1000000000000000000"),  # 1 ETH
            output_amount=Decimal("1010000000000000000"),  # 1.01 ETH
            fees=Decimal("5000000000000000")  # 0.005 ETH
        )
        
        assert profit is not None
        assert isinstance(profit, Decimal)
        assert profit == Decimal("5000000000000000")  # 0.005 ETH profit

@pytest.mark.core
class TestWeb3Client:
    """Test Web3 client functionality."""
    
    @pytest.fixture
    async def client(self, web3_provider):
        """Create Web3 client."""
        return Web3Client(web3_provider)
    
    @pytest.mark.asyncio
    async def test_token_balance(self, client):
        """Test token balance retrieval."""
        balance = await client.get_token_balance(
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        )
        
        assert balance is not None
        assert isinstance(balance, Decimal)
        assert balance >= 0
    
    @pytest.mark.asyncio
    async def test_transaction_submission(self, client):
        """Test transaction submission."""
        tx_hash = await client.submit_transaction({
            "to": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "value": 0,
            "data": "0x"
        })
        
        assert tx_hash is not None
        assert isinstance(tx_hash, str)
        assert tx_hash.startswith("0x")
        assert len(tx_hash) == 66

@pytest.mark.core
class TestHooksClient:
    """Test XRPL Hooks client functionality."""
    
    @pytest.fixture
    async def client(self, xrpl_client, test_wallet):
        """Create XRPL Hooks client."""
        return XRPLHooksClient(xrpl_client, test_wallet, "test_hook_account")
    
    @pytest.mark.asyncio
    async def test_hook_installation(self, client):
        """Test hook installation."""
        result = await client.install_hook(
            "amm_hook",
            {"param1": "value1"}
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "hook_hash" in result
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_hook_execution(self, client):
        """Test hook execution."""
        result = await client.execute_hook(
            "amm_hook",
            "swap",
            {"amount": "1000", "token": "XRP"}
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "status" in result
        assert result["status"] == "tesSUCCESS"
