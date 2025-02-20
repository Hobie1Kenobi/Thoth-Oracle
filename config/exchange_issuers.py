"""
XRPL Exchange Issuer Addresses Configuration
"""

EXCHANGE_ISSUERS = {
    "Bitstamp": {
        "address": "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B",
        "currencies": ["USD", "BTC", "ETH"],
        "retry_attempts": 3,
        "retry_delay": 1.0  # seconds
    },
    "Gatehub": {
        "address": "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq",
        "currencies": ["USD", "EUR", "BTC", "ETH"],
        "retry_attempts": 3,
        "retry_delay": 1.0
    }
}

# Path finding configuration
PATH_FINDING = {
    "max_paths": 4,
    "max_path_length": 6,
    "timeout": 5.0  # seconds
}

# Transaction monitoring configuration
TRANSACTION_MONITORING = {
    "max_ledger_offset": 5,
    "confirmation_threshold": 1,
    "monitoring_interval": 1.0  # seconds
}

# Retry configuration
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay": 1.0,  # seconds
    "max_delay": 5.0,   # seconds
    "exponential_base": 2
}

def get_issuer_address(exchange_name: str) -> str:
    """Get the issuer address for an exchange."""
    exchange = EXCHANGE_ISSUERS.get(exchange_name)
    if not exchange:
        raise ValueError(f"Unknown exchange: {exchange_name}")
    return exchange["address"]

def get_exchange_currencies(exchange_name: str) -> list:
    """Get supported currencies for an exchange."""
    exchange = EXCHANGE_ISSUERS.get(exchange_name)
    if not exchange:
        raise ValueError(f"Unknown exchange: {exchange_name}")
    return exchange["currencies"]
