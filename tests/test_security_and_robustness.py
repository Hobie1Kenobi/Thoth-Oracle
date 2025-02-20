"""Security and robustness tests for the Thoth Oracle system."""

import pytest
import asyncio
import json
import secrets
from decimal import Decimal
from unittest.mock import Mock, patch
from web3.exceptions import InvalidTransaction, TimeExhausted
from xrpl.models.exceptions import XRPLRequestFailureException
from agents.flash_loan_agent.flash_loan_agent import FlashLoanAgent
from examples.quantum_prediction import QuantumPricePredictor
from examples.risk_management import QuantumRiskManager
from integrations.hooks_client import XRPLHooksClient
from integrations.across_bridge import AcrossBridgeClient

@pytest.mark.security
class TestSecurityAndRobustness:
    """Security and robustness test suite."""
    
    @pytest.fixture
    async def system_components(self):
        """Initialize all system components."""
        mock_web3 = Mock()
        mock_xrpl = Mock()
        mock_http = Mock()
        
        flash_loan_agent = FlashLoanAgent(
            web3_client=mock_web3,
            bridge_client=mock_http,
            hooks_client=mock_xrpl
        )
        
        price_predictor = QuantumPricePredictor(n_qubits=3, n_layers=2)
        risk_manager = QuantumRiskManager(n_assets=3)
        hooks_client = XRPLHooksClient(
            client=mock_xrpl,
            wallet=None,
            hook_account="rHookAccount"
        )
        bridge_client = AcrossBridgeClient(http_client=mock_http)
        
        return {
            "flash_loan_agent": flash_loan_agent,
            "price_predictor": price_predictor,
            "risk_manager": risk_manager,
            "hooks_client": hooks_client,
            "bridge_client": bridge_client
        }
    
    @pytest.mark.asyncio
    async def test_input_validation_and_sanitization(self, system_components):
        """Test input validation and sanitization across all components."""
        flash_loan_agent = system_components["flash_loan_agent"]
        hooks_client = system_components["hooks_client"]
        bridge_client = system_components["bridge_client"]
        
        # Test malicious inputs
        malicious_inputs = [
            "'; DROP TABLE users; --",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
            "../../../etc/passwd",  # Path traversal
            "0x" + "F" * 1000,  # Buffer overflow attempt
            json.dumps({"__proto__": {"polluted": True}}),  # Prototype pollution
            "0x0000000000000000000000000000000000000000"  # Zero address
        ]
        
        # Test flash loan input validation
        for bad_input in malicious_inputs:
            with pytest.raises((ValueError, InvalidTransaction)):
                await flash_loan_agent.execute_flash_loan(
                    token_address=bad_input,
                    amount=Decimal("1000"),
                    target_chain=1
                )
        
        # Test hook input validation
        for bad_input in malicious_inputs:
            with pytest.raises(ValueError):
                await hooks_client.execute_hook(
                    "amm",
                    bad_input,
                    {"param": bad_input}
                )
        
        # Test bridge input validation
        for bad_input in malicious_inputs:
            with pytest.raises(ValueError):
                await bridge_client.get_bridge_quote(
                    bad_input,
                    "USDC",
                    "1000",
                    1,
                    2
                )
    
    @pytest.mark.asyncio
    async def test_transaction_replay_protection(self, system_components):
        """Test protection against transaction replay attacks."""
        flash_loan_agent = system_components["flash_loan_agent"]
        hooks_client = system_components["hooks_client"]
        
        # Execute original transaction
        tx_result = await flash_loan_agent.execute_flash_loan(
            token_address="0xtoken",
            amount=Decimal("1000"),
            target_chain=1
        )
        
        # Attempt to replay the same transaction
        with pytest.raises(InvalidTransaction, match="Nonce too low"):
            await flash_loan_agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=1,
                override_nonce=tx_result["nonce"]
            )
        
        # Test hook transaction replay
        hook_result = await hooks_client.execute_hook(
            "amm",
            "swap",
            {"amount": "1000"}
        )
        
        # Attempt to replay hook transaction
        with pytest.raises(XRPLRequestFailureException):
            await hooks_client.execute_hook(
                "amm",
                "swap",
                {"amount": "1000"},
                sequence=hook_result["sequence"]
            )
    
    @pytest.mark.asyncio
    async def test_rate_limiting_and_throttling(self, system_components):
        """Test rate limiting and request throttling."""
        bridge_client = system_components["bridge_client"]
        hooks_client = system_components["hooks_client"]
        
        # Test rapid requests to bridge
        requests = []
        for _ in range(100):
            requests.append(
                bridge_client.get_bridge_quote(
                    "USDC",
                    "USDC",
                    "1000",
                    1,
                    2
                )
            )
        
        # Execute requests and check rate limiting
        results = await asyncio.gather(*requests, return_exceptions=True)
        rate_limit_errors = sum(
            1 for r in results
            if isinstance(r, Exception) and "rate limit" in str(r).lower()
        )
        
        assert rate_limit_errors > 0, "Rate limiting not enforced"
        
        # Test hook rate limiting
        hook_requests = []
        for _ in range(100):
            hook_requests.append(
                hooks_client.execute_hook(
                    "amm",
                    "swap",
                    {"amount": "1000"}
                )
            )
        
        hook_results = await asyncio.gather(*hook_requests, return_exceptions=True)
        hook_rate_limits = sum(
            1 for r in hook_results
            if isinstance(r, Exception) and "rate limit" in str(r).lower()
        )
        
        assert hook_rate_limits > 0, "Hook rate limiting not enforced"
    
    @pytest.mark.asyncio
    async def test_secure_random_number_generation(self, system_components):
        """Test secure random number generation."""
        risk_manager = system_components["risk_manager"]
        
        # Generate multiple random seeds
        seeds = [
            risk_manager.generate_secure_seed()
            for _ in range(1000)
        ]
        
        # Test uniqueness
        assert len(set(seeds)) == len(seeds), "Duplicate seeds generated"
        
        # Test entropy
        bit_counts = [bin(seed).count('1') for seed in seeds]
        avg_bits = sum(bit_counts) / len(bit_counts)
        assert 45 < avg_bits < 55, "Poor entropy in random generation"
        
        # Test using secrets module
        secure_random = secrets.SystemRandom()
        secure_seeds = [secure_random.randint(0, 2**256) for _ in range(1000)]
        
        # Compare distributions
        from scipy import stats
        _, p_value = stats.ks_2samp(seeds, secure_seeds)
        assert p_value > 0.05, "Random generation may not be secure"
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, system_components):
        """Test error handling and system recovery."""
        flash_loan_agent = system_components["flash_loan_agent"]
        bridge_client = system_components["bridge_client"]
        
        # Test network errors
        with patch.object(flash_loan_agent.web3_client, 'submit_transaction') as mock_submit:
            mock_submit.side_effect = TimeExhausted()
            
            # Should retry and eventually succeed
            mock_submit.side_effect = [TimeExhausted(), TimeExhausted(), {"status": "success"}]
            result = await flash_loan_agent.execute_flash_loan_with_retry(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=1,
                max_retries=3
            )
            assert result["status"] == "success"
        
        # Test bridge errors
        with patch.object(bridge_client.http_client, 'post') as mock_post:
            # Test temporary failure
            mock_post.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                {"status": "success"}
            ]
            
            result = await bridge_client.submit_bridge_transaction_with_retry(
                "quote_123",
                "0xtx_hash",
                max_retries=3
            )
            assert result["status"] == "success"
            
            # Test permanent failure
            mock_post.side_effect = Exception("Permanent error")
            with pytest.raises(Exception):
                await bridge_client.submit_bridge_transaction_with_retry(
                    "quote_123",
                    "0xtx_hash",
                    max_retries=3
                )
    
    @pytest.mark.asyncio
    async def test_transaction_signing_security(self, system_components):
        """Test transaction signing security."""
        flash_loan_agent = system_components["flash_loan_agent"]
        hooks_client = system_components["hooks_client"]
        
        # Test unauthorized signing attempts
        with pytest.raises(ValueError, match="Unauthorized signer"):
            await flash_loan_agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=1,
                signer="unauthorized_key"
            )
        
        # Test signature manipulation
        original_sig = "0x" + "1" * 130
        manipulated_sig = "0x" + "2" * 130
        
        with pytest.raises(InvalidTransaction):
            await flash_loan_agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=1,
                signature=manipulated_sig
            )
        
        # Test hook signing security
        with pytest.raises(XRPLRequestFailureException):
            await hooks_client.execute_hook(
                "amm",
                "swap",
                {"amount": "1000"},
                signature=manipulated_sig
            )
    
    @pytest.mark.asyncio
    async def test_quantum_circuit_security(self, system_components):
        """Test quantum circuit security and integrity."""
        price_predictor = system_components["price_predictor"]
        
        # Test circuit parameter tampering
        original_params = price_predictor.parameters.copy()
        tampered_params = [p + 0.1 for p in original_params]
        
        # Should detect parameter tampering
        with pytest.raises(ValueError, match="Invalid circuit parameters"):
            await price_predictor.predict_with_params(tampered_params)
        
        # Test circuit execution integrity
        results = []
        for _ in range(100):
            prediction = await price_predictor.predict_price(window_size=5)
            results.append(prediction)
        
        # Check for result manipulation
        assert 0 <= min(results) <= 1, "Results outside valid range"
        assert max(results) - min(results) < 1, "Suspicious result spread"
    
    @pytest.mark.asyncio
    async def test_system_state_consistency(self, system_components):
        """Test system state consistency under concurrent operations."""
        flash_loan_agent = system_components["flash_loan_agent"]
        risk_manager = system_components["risk_manager"]
        
        # Initialize system state
        initial_state = {
            "liquidity": Decimal("1000000"),
            "active_loans": [],
            "risk_score": Decimal("0.5")
        }
        
        # Execute concurrent operations
        async def concurrent_operation(i):
            # Modify state
            await flash_loan_agent.execute_flash_loan(
                token_address="0xtoken",
                amount=Decimal("1000"),
                target_chain=1
            )
            
            # Read state
            return await risk_manager.get_system_state()
        
        # Run concurrent operations
        tasks = [concurrent_operation(i) for i in range(10)]
        states = await asyncio.gather(*tasks)
        
        # Verify state consistency
        for state in states:
            assert state["liquidity"] >= Decimal("0")
            assert len(state["active_loans"]) <= 100
            assert Decimal("0") <= state["risk_score"] <= Decimal("1")
    
    @pytest.mark.asyncio
    async def test_denial_of_service_protection(self, system_components):
        """Test protection against DoS attacks."""
        bridge_client = system_components["bridge_client"]
        hooks_client = system_components["hooks_client"]
        
        # Test large payload handling
        large_payload = "A" * 1024 * 1024  # 1MB payload
        with pytest.raises(ValueError, match="Payload too large"):
            await bridge_client.submit_bridge_transaction(
                "quote_123",
                large_payload
            )
        
        # Test connection flooding
        connections = []
        for _ in range(1000):
            try:
                conn = await hooks_client.create_connection()
                connections.append(conn)
            except Exception as e:
                assert "Too many connections" in str(e)
                break
        
        # Test computational DoS protection
        complex_params = {
            "nested": {
                "array": list(range(10000)),
                "deep": {"a": {"b": {"c": list(range(10000))}}}
            }
        }
        
        with pytest.raises(ValueError, match="Computation too complex"):
            await hooks_client.execute_hook(
                "amm",
                "swap",
                complex_params
            )
