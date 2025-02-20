"""Integration tests for Thoth Oracle components."""

import pytest
import asyncio
from decimal import Decimal
from examples.flash_loan_example import execute_cross_chain_flash_loan
from examples.amm_operations import AMMOperator
from integrations.web3_client import Web3Client
from integrations.across_bridge import AcrossBridgeClient
from integrations.hooks_client import XRPLHooksClient

@pytest.mark.integration
class TestFlashLoanIntegration:
    """Test flash loan integration across components."""
    
    @pytest.fixture
    async def web3_client(self, web3_provider):
        """Create Web3 client."""
        return Web3Client(web3_provider)
    
    @pytest.fixture
    async def bridge_client(self, http_client):
        """Create bridge client."""
        return AcrossBridgeClient()
    
    @pytest.fixture
    async def hooks_client(self, xrpl_client, test_wallet):
        """Create XRPL hooks client."""
        return XRPLHooksClient(xrpl_client, test_wallet, "test_hook_account")
    
    @pytest.mark.asyncio
    async def test_flash_loan_execution(
        self,
        web3_client,
        bridge_client,
        hooks_client,
        mock_quantum_circuit
    ):
        """Test complete flash loan execution flow."""
        result = await execute_cross_chain_flash_loan(
            Decimal("1000000000000000000"),  # 1 ETH
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            1,  # Ethereum
            2   # XRPL
        )
        
        assert result is not None
        assert "flash_loan_tx" in result
        assert "bridge_tx" in result
        assert "hook_tx" in result
        assert "return_tx" in result
        assert "profit" in result
        assert result["profit"] > 0

@pytest.mark.integration
class TestAMMIntegration:
    """Test AMM integration across components."""
    
    @pytest.fixture
    async def amm_operator(self, xrpl_client, test_wallet):
        """Create AMM operator."""
        return AMMOperator()
    
    @pytest.mark.asyncio
    async def test_liquidity_provision(self, amm_operator):
        """Test complete liquidity provision flow."""
        result = await amm_operator.provide_liquidity(
            Decimal("1000"),  # 1000 Token A
            Decimal("1000"),  # 1000 Token B
            Decimal("100")    # Minimum 100 LP tokens
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "lp_tokens" in result
        assert result["lp_tokens"] >= Decimal("100")
    
    @pytest.mark.asyncio
    async def test_swap_execution(self, amm_operator):
        """Test token swap execution."""
        result = await amm_operator.swap_tokens(
            Decimal("100"),  # Swap 100 tokens
            0,              # Token A to Token B
            Decimal("95")   # Minimum 95 tokens output
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "input_amount" in result
        assert "output_amount" in result
        assert "price" in result
        assert result["output_amount"] >= Decimal("95")
    
    @pytest.mark.asyncio
    async def test_liquidity_removal(self, amm_operator):
        """Test liquidity removal flow."""
        result = await amm_operator.remove_liquidity(
            Decimal("500"),    # Remove 500 LP tokens
            Decimal("450"),    # Minimum 450 Token A
            Decimal("450")     # Minimum 450 Token B
        )
        
        assert result is not None
        assert "tx_hash" in result
        assert "token_a_received" in result
        assert "token_b_received" in result
        assert result["token_a_received"] >= Decimal("450")
        assert result["token_b_received"] >= Decimal("450")

@pytest.mark.integration
class TestCrossChainIntegration:
    """Test cross-chain integration components."""
    
    @pytest.fixture
    async def bridge_client(self, http_client):
        """Create bridge client."""
        return AcrossBridgeClient()
    
    @pytest.mark.asyncio
    async def test_bridge_quote(self, bridge_client):
        """Test bridge quote retrieval."""
        quote = await bridge_client.get_bridge_quote(
            "USDC",
            "USDC",
            "1000",
            1,  # Ethereum
            2   # XRPL
        )
        
        assert quote is not None
        assert "quoteId" in quote
        assert "estimatedTime" in quote
        assert "fee" in quote
        assert "route" in quote
        assert quote["route"]["fromChain"] == 1
        assert quote["route"]["toChain"] == 2
    
    @pytest.mark.asyncio
    async def test_bridge_transaction(self, bridge_client):
        """Test bridge transaction submission."""
        # First get a quote
        quote = await bridge_client.get_bridge_quote(
            "USDC",
            "USDC",
            "1000",
            1,
            2
        )
        
        # Submit transaction
        result = await bridge_client.submit_bridge_transaction(
            quote["quoteId"],
            "0x123"  # Mock transaction hash
        )
        
        assert result is not None
        assert "status" in result
        assert "txHash" in result
        assert result["status"] in ["pending", "completed"]
    
    @pytest.mark.asyncio
    async def test_bridge_status(self, bridge_client):
        """Test bridge status checking."""
        status = await bridge_client.get_bridge_status("0x123")
        
        assert status is not None
        assert "status" in status
        assert "fromChain" in status
        assert "toChain" in status
        assert status["fromChain"]["confirmations"] >= 0
