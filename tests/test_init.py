"""Test initialization and environment setup."""

import os
import pytest
from pathlib import Path

def test_project_structure():
    """Test that all required project directories exist."""
    root_dir = Path(__file__).parent.parent
    required_dirs = [
        "agents",
        "docs",
        "examples",
        "hooks",
        "integrations",
        "tests"
    ]
    
    for dir_name in required_dirs:
        assert (root_dir / dir_name).is_dir(), f"Missing directory: {dir_name}"

def test_config_files():
    """Test that all required configuration files exist."""
    root_dir = Path(__file__).parent.parent
    required_files = [
        "requirements.txt",
        "pytest.ini",
        ".env.example",
        "config.py"
    ]
    
    for file_name in required_files:
        assert (root_dir / file_name).is_file(), f"Missing file: {file_name}"

def test_environment_variables():
    """Test that required environment variables are set."""
    required_vars = [
        "INFURA_PROJECT_ID",
        "XRPL_SEED",
        "HOOK_ACCOUNT",
        "IBMQ_API_TOKEN",
        "DWAVE_API_TOKEN"
    ]
    
    for var in required_vars:
        assert os.getenv(var) is not None, f"Missing environment variable: {var}"

def test_quantum_imports():
    """Test that quantum libraries can be imported."""
    try:
        import qiskit
        import dwave.system
    except ImportError as e:
        pytest.fail(f"Failed to import quantum libraries: {str(e)}")

def test_blockchain_imports():
    """Test that blockchain libraries can be imported."""
    try:
        import web3
        import xrpl
    except ImportError as e:
        pytest.fail(f"Failed to import blockchain libraries: {str(e)}")

def test_async_imports():
    """Test that async libraries can be imported."""
    try:
        import aiohttp
        import asyncio
    except ImportError as e:
        pytest.fail(f"Failed to import async libraries: {str(e)}")

def test_hooks_directory():
    """Test that XRPL hook files exist."""
    root_dir = Path(__file__).parent.parent
    required_hooks = [
        "amm_hook.c",
        "flash_loan_hook.c"
    ]
    
    for hook_file in required_hooks:
        assert (root_dir / "hooks" / hook_file).is_file(), f"Missing hook file: {hook_file}"

def test_example_files():
    """Test that example files exist."""
    root_dir = Path(__file__).parent.parent
    required_examples = [
        "flash_loan_example.py",
        "amm_operations.py",
        "quantum_prediction.py",
        "risk_management.py"
    ]
    
    for example_file in required_examples:
        assert (root_dir / "examples" / example_file).is_file(), f"Missing example file: {example_file}"

def test_documentation():
    """Test that documentation files exist."""
    root_dir = Path(__file__).parent.parent
    required_docs = [
        "whitepaper.md",
        "quantum_implementation.md",
        "quantum_components.md"
    ]
    
    for doc_file in required_docs:
        assert (root_dir / "docs" / doc_file).is_file(), f"Missing documentation file: {doc_file}"
