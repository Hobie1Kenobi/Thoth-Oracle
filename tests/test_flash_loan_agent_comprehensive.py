"""Comprehensive tests for flash loan agent."""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, patch
from web3.exceptions import ContractLogicError
from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent

@pytest.mark.comprehensive
class TestFlashLoanAgentComprehensive:
    """Comprehensive test suite for flash loan agent."""
    
    @pytest.fixture
    async def mock_web3_client(self):
        """Create mock Web3 client."""
        client = Mock()
        client.get_token_balance.return_value = Decimal("1000")
        client.get_pool_liquidity.return_value = Decimal("10000")
        client.submit_transaction.return_value = "0xtx_hash"
        return client
    
    @pytest.fixture
    async def mock_bridge_client(self):
        """Create mock bridge client."""
        client = Mock()
        client.get_bridge_quote.return_value = {
            "quoteId": "quote_123",
            "fee": "0.1",
            "estimatedTime": 300
        }
        client.submit_bridge_transaction.return_value = {
            "txHash": "0xbridge_tx",
            "status": "pending"
        }
        return client
    
    @pytest.fixture
    async def mock_hooks_client(self):
        """Create mock hooks client."""
        client = Mock()
        client.execute_hook.return_value = {
            "tx_hash": "0xhook_tx",
            "status": "tesSUCCESS"
        }
        return client
    
    @pytest.fixture
    async def agent(self, mock_web3_client, mock_bridge_client, mock_hooks_client):
        """Create flash loan agent with mock clients."""
        return FlashLoanAgent(
            web3_client=mock_web3_client,
            bridge_client=mock_bridge_client,
            hooks_client=mock_hooks_client
        )

    @pytest.mark.asyncio
    async def test_initialization(self, agent):
        """Test agent initialization."""
        assert agent.web3_client is not None
        assert agent.bridge_client is not None
        assert agent.hooks_client is not None
        assert agent.min_profit_threshold == Decimal("0.01")
        assert agent.max_slippage == Decimal("0.03")

    @pytest.mark.asyncio
    async def test_opportunity_detection_full(self, agent):
        """Test complete opportunity detection flow."""
        # Setup mock market data
        agent.web3_client.get_market_prices.return_value = {
            "ETH/USD": Decimal("2000"),
            "ETH/EUR": Decimal("1700"),
            "EUR/USD": Decimal("1.25")
        }
        
        opportunities = await agent.find_opportunities(
            token_address="0xtoken",
            min_profit=Decimal("0.1"),
            max_slippage=Decimal("0.01")
        )
        
        assert isinstance(opportunities, list)
        assert len(opportunities) > 0
        for opp in opportunities:
            assert "profit" in opp
            assert "route" in opp
            assert "amount" in opp
            assert opp["profit"] >= Decimal("0.1")

    @pytest.mark.asyncio
    async def test_flash_loan_execution_full(self, agent):
        """Test complete flash loan execution flow."""
        result = await agent.execute_flash_loan(
            token_address="0xtoken",
            amount=Decimal("1000"),
            target_chain=2
        )
        
        assert result is not None
        assert "flash_loan_tx" in result
        assert "bridge_tx" in result
        assert "hook_tx" in result
        assert "return_tx" in result
        assert "profit" in result

    @pytest.mark.asyncio
    async def test_profit_calculation_detailed(self, agent):
        """Test detailed profit calculation."""
        test_cases = [
            {
                "input_amount": Decimal("1000"),
                "output_amount": Decimal("1050"),
                "fees": Decimal("10"),
                "expected_profit": Decimal("40")
            },
            {
                "input_amount": Decimal("1000"),
                "output_amount": Decimal("990"),
                "fees": Decimal("10"),
                "expected_profit": Decimal("-20")
            }
        ]
        
        for case in test_cases:
            profit = await agent.calculate_profit(
                case["input_amount"],
                case["output_amount"],
                case["fees"]
            )
            assert profit == case["expected_profit"]

    @pytest.mark.asyncio
    async def test_slippage_calculation(self, agent):
        """Test slippage calculation."""
        test_cases = [
            {
                "expected_amount": Decimal("1000"),
                "actual_amount": Decimal("990"),
                "expected_slippage": Decimal("0.01")
            },
            {
                "expected_amount": Decimal("1000"),
                "actual_amount": Decimal("950"),
                "expected_slippage": Decimal("0.05")
            }
        ]
        
        for case in test_cases:
            slippage = await agent.calculate_slippage(
                case["expected_amount"],
                case["actual_amount"]
            )
            assert slippage == case["expected_slippage"]

    @pytest.mark.asyncio
    async def test_gas_estimation(self, agent):
        """Test gas estimation."""
        # Setup mock gas prices
        agent.web3_client.get_gas_price.return_value = Decimal("50")  # 50 gwei
        agent.web3_client.estimate_gas.return_value = Decimal("200000")
        
        gas_cost = await agent.estimate_gas_cost(
            token_address="0xtoken",
            amount=Decimal("1000")
        )
        
        assert gas_cost > 0
        assert isinstance(gas_cost, Decimal)

    @pytest.mark.asyncio
    async def test_error_handling_comprehensive(self, agent):
        """Test comprehensive error handling."""
        # Test insufficient liquidity
        agent.web3_client.get_pool_liquidity.return_value = Decimal("100")
        with pytest.raises(ValueError, match="Insufficient liquidity"):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=2
            )
        
        # Test failed transaction
        agent.web3_client.submit_transaction.side_effect = ContractLogicError("Execution reverted")
        with pytest.raises(ContractLogicError):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("100"),
                target_chain=2
            )
        
        # Test bridge timeout
        agent.bridge_client.submit_bridge_transaction.side_effect = asyncio.TimeoutError()
        with pytest.raises(asyncio.TimeoutError):
            await agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("100"),
                target_chain=2
            )

    @pytest.mark.asyncio
    async def test_transaction_validation(self, agent):
        """Test transaction validation."""
        # Valid transaction
        valid_tx = {
            "to": "0xvalid",
            "value": 0,
            "data": "0xdata"
        }
        assert await agent.validate_transaction(valid_tx) is True
        
        # Invalid transactions
        invalid_cases = [
            {},  # Empty transaction
            {"to": None, "value": 0},  # Missing address
            {"to": "0xvalid", "value": -1},  # Negative value
            {"to": "invalid_address", "value": 0}  # Invalid address format
        ]
        
        for tx in invalid_cases:
            assert await agent.validate_transaction(tx) is False

    @pytest.mark.asyncio
    async def test_market_data_validation(self, agent):
        """Test market data validation."""
        # Valid market data
        valid_data = {
            "ETH/USD": Decimal("2000"),
            "ETH/EUR": Decimal("1700"),
            "EUR/USD": Decimal("1.25")
        }
        assert await agent.validate_market_data(valid_data) is True
        
        # Invalid market data
        invalid_cases = [
            {},  # Empty data
            {"ETH/USD": -2000},  # Negative price
            {"ETH/USD": "invalid"},  # Invalid price format
            {"INVALID_PAIR": 2000}  # Invalid pair format
        ]
        
        for data in invalid_cases:
            assert await agent.validate_market_data(data) is False

    @pytest.mark.asyncio
    async def test_bridge_quote_validation(self, agent):
        """Test bridge quote validation."""
        # Valid quote
        valid_quote = {
            "quoteId": "quote_123",
            "fee": "0.1",
            "estimatedTime": 300,
            "route": {
                "fromChain": 1,
                "toChain": 2
            }
        }
        assert await agent.validate_bridge_quote(valid_quote) is True
        
        # Invalid quotes
        invalid_cases = [
            {},  # Empty quote
            {"quoteId": None},  # Missing required fields
            {
                "quoteId": "quote_123",
                "fee": "-0.1"  # Negative fee
            },
            {
                "quoteId": "quote_123",
                "fee": "0.1",
                "estimatedTime": "invalid"  # Invalid time format
            }
        ]
        
        for quote in invalid_cases:
            assert await agent.validate_bridge_quote(quote) is False
