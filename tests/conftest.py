"""Pytest configuration and fixtures."""

import os
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from web3 import Web3
from aiohttp import ClientSession

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def web3_provider() -> Web3:
    """Create a Web3 provider for testing."""
    return Web3(Web3.HTTPProvider("http://localhost:8545"))

@pytest.fixture(scope="session")
def xrpl_client() -> JsonRpcClient:
    """Create an XRPL client for testing."""
    return JsonRpcClient("http://localhost:51234")

@pytest.fixture(scope="session")
def test_wallet() -> Wallet:
    """Create a test wallet."""
    return Wallet.create()

@pytest.fixture
async def http_client() -> AsyncGenerator[ClientSession, None]:
    """Create an HTTP client session."""
    async with ClientSession() as session:
        yield session

@pytest.fixture(scope="session")
def test_config() -> dict:
    """Test configuration values."""
    return {
        "networks": {
            "ethereum": {
                "chain_id": 1,
                "contracts": {
                    "aave_lending_pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
                    "uniswap_router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
                }
            },
            "xrpl": {
                "hook_account": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
                "amm_account": "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe"
            }
        },
        "quantum": {
            "backend": "ibmq_qasm_simulator",
            "shots": 1000,
            "optimization_level": 1
        }
    }

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables for testing."""
    monkeypatch.setenv("INFURA_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("XRPL_SEED", "test-seed")
    monkeypatch.setenv("HOOK_ACCOUNT", "test-hook-account")
    monkeypatch.setenv("IBMQ_API_TOKEN", "test-ibm-token")
    monkeypatch.setenv("DWAVE_API_TOKEN", "test-dwave-token")

def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "quantum: mark test as using quantum features")
    config.addinivalue_line("markers", "slow: mark test as slow to execute")
    config.addinivalue_line("markers", "flash_loan: mark test as flash loan related")
    config.addinivalue_line("markers", "amm: mark test as AMM related")
    config.addinivalue_line("markers", "hooks: mark test as XRPL hooks related")
    config.addinivalue_line("markers", "bridge: mark test as cross-chain bridge related")

@pytest.fixture
def mock_quantum_circuit(mocker: pytest.FixtureRequest) -> None:
    """Mock quantum circuit execution."""
    mocker.patch("qiskit.execute", return_value=mocker.Mock(
        result=lambda: mocker.Mock(
            get_counts=lambda: {"00": 500, "11": 500}
        )
    ))

@pytest.fixture
def mock_dwave_sampler(mocker: pytest.FixtureRequest) -> None:
    """Mock D-Wave sampler."""
    mocker.patch("dwave.system.DWaveSampler", return_value=mocker.Mock(
        sample=lambda bqm, **kwargs: mocker.Mock(
            first=mocker.Mock(
                sample={f"x_{i}": 1 for i in range(5)}
            )
        )
    ))

def pytest_collection_modifyitems(items: list) -> None:
    """Modify test items to add markers based on path."""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "quantum" in item.nodeid:
            item.add_marker(pytest.mark.quantum)
        if "flash_loan" in item.nodeid:
            item.add_marker(pytest.mark.flash_loan)
        if "amm" in item.nodeid:
            item.add_marker(pytest.mark.amm)
        if "hooks" in item.nodeid:
            item.add_marker(pytest.mark.hooks)
        if "bridge" in item.nodeid:
            item.add_marker(pytest.mark.bridge)
