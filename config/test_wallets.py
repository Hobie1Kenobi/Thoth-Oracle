"""
Test wallet configurations for Thoth Oracle agents
"""
from decimal import Decimal

# Test network settings
TESTNET_URL = "https://s.altnet.rippletest.net:51234"

# Agent wallets
SPOT_TRADER_WALLET = {
    "seed": "sEd7dKFyihsGJuCZKjqUJgedQiDHhy4",  # Funded test wallet
    "initial_balance": Decimal("1000"),
    "risk_threshold": Decimal("0.8"),  # Adjusted to match actual risk scores
    "max_position_size": Decimal("100"),  # Max 100 XRP per trade
    "min_profit_threshold": Decimal("0.003")  # 0.3% minimum profit
}

FLASH_LOAN_WALLET = {
    "seed": "sEdSPJwYsi26i2a1tiLyik49RMrgGYe",  # Funded test wallet
    "max_loan_size": Decimal("5000"),
    "min_profit_threshold": Decimal("0.008"),  # 0.8% minimum profit for flash loans
    "max_slippage": Decimal("0.002"),  # 0.2% maximum slippage
    "gas_buffer": Decimal("1.5")  # 50% buffer for gas costs
}
