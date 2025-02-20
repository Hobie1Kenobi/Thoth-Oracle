"""Configuration settings for Thoth Oracle."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Network configurations
NETWORKS = {
    'ethereum': {
        'rpc_url': os.getenv('ETH_RPC_URL', 'https://mainnet.infura.io/v3/your-project-id'),
        'chain_id': 1,
        'flash_loan_providers': {
            'aave': os.getenv('AAVE_LENDING_POOL_ADDRESS'),
            'dydx': os.getenv('DYDX_SOLO_ADDRESS')
        }
    },
    'xrpl': {
        'mainnet': 'wss://xrplcluster.com',
        'testnet': 'wss://s.altnet.rippletest.net:51233',
        'devnet': 'wss://s.devnet.rippletest.net:51233'
    }
}

# Bridge configuration
BRIDGE_CONFIG = {
    'across': {
        'api_url': 'https://across-v2.api.across.to',
        'supported_tokens': ['USDC', 'USDT', 'ETH', 'WBTC'],
        'min_confirmation_blocks': 5
    }
}

# Hook configuration
HOOK_CONFIG = {
    'amm': {
        'namespace': '0000000000000000',
        'hook_on': 'Payment'
    }
}

# Quantum settings
QUANTUM_CONFIG = {
    'ibm_qiskit': {
        'backend': 'ibmq_qasm_simulator',
        'shots': 1000
    },
    'dwave': {
        'solver': 'Advantage_system4.1',
        'chain_strength': 1.0
    }
}

# Agent settings
AGENT_CONFIG = {
    'flash_loan': {
        'min_profit_threshold': 0.5,  # Minimum profit percentage
        'max_slippage': 1.0,  # Maximum slippage percentage
        'gas_buffer': 1.2,  # Gas price buffer multiplier
    },
    'risk_management': {
        'max_exposure': 1000000,  # Maximum USD exposure
        'reserve_ratio': 0.1,  # Required reserve ratio
    }
}

# Security settings
SECURITY_CONFIG = {
    'quantum_resistant': True,
    'min_signature_height': 10,  # XMSS signature tree height
    'encryption_scheme': 'lattice_based'
}

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        }
    }
}
