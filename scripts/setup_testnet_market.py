"""
XRPL Testnet Market Setup
Creates a complete trading environment with:
1. Token issuer wallet (acts as our own gateway)
2. Issued tokens (USD, EUR, BTC)
3. Trust lines from trading wallets to issuer
4. Token distribution to trading wallets
5. AMM liquidity pools (XRP/USD, XRP/EUR, XRP/BTC)
6. DEX order book offers for spread trading

Usage: python scripts/setup_testnet_market.py
"""

import asyncio
import json
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet, generate_faucet_wallet
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import (
    AccountSet, TrustSet, Payment, OfferCreate, AMMCreate
)
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, AccountLines, AMMInfo
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

from config.test_wallets import TESTNET_URL, SPOT_TRADER_WALLET, FLASH_LOAN_WALLET

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

TOKENS = {
    "USD": {"initial_supply": "100000", "xrp_pool": "5000", "token_pool": "2500"},
    "EUR": {"initial_supply": "100000", "xrp_pool": "5000", "token_pool": "2300"},
    "BTC": {"initial_supply": "100",    "xrp_pool": "5000", "token_pool": "0.05"},
}

ISSUER_CONFIG_PATH = "config/testnet_issuer.json"


async def submit_tx(client, wallet, tx):
    """Submit a transaction and return the result."""
    response = await submit_and_wait(transaction=tx, client=client, wallet=wallet)
    result = response.result.get("meta", {}).get("TransactionResult", "unknown")
    tx_hash = response.result.get("hash", "")[:16]
    return result, tx_hash


async def create_issuer(sync_client):
    """Create and fund a token issuer wallet."""
    from xrpl.asyncio.wallet import generate_faucet_wallet as async_generate_faucet
    from xrpl.asyncio.clients import AsyncJsonRpcClient as AsyncClient

    logger.info("Creating issuer wallet via faucet...")
    async_client = AsyncClient(sync_client.url)
    issuer = await async_generate_faucet(async_client, debug=True)
    logger.info(f"  Issuer address: {issuer.address}")
    logger.info(f"  Issuer seed: {issuer.seed}")
    return issuer


async def enable_rippling(client, issuer):
    """Enable Default Ripple on issuer account so tokens can be traded."""
    logger.info("Enabling Default Ripple on issuer...")
    tx = AccountSet(
        account=issuer.address,
        set_flag=8  # asfDefaultRipple
    )
    result, tx_hash = await submit_tx(client, issuer, tx)
    logger.info(f"  Default Ripple: {result} ({tx_hash})")
    return result == "tesSUCCESS"


async def setup_trust_and_fund(client, issuer, recipient_wallet, recipient_name, tokens):
    """Set up trust lines from recipient to issuer and fund with tokens."""
    logger.info(f"\nFunding {recipient_name}: {recipient_wallet.address}")

    for currency, config in tokens.items():
        amount = config["initial_supply"]

        trust = TrustSet(
            account=recipient_wallet.address,
            limit_amount=IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer.address,
                value="1000000000"
            )
        )
        result, tx_hash = await submit_tx(client, recipient_wallet, trust)
        logger.info(f"  TrustSet {currency}: {result} ({tx_hash})")

        payment = Payment(
            account=issuer.address,
            destination=recipient_wallet.address,
            amount=IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer.address,
                value=amount
            )
        )
        result, tx_hash = await submit_tx(client, issuer, payment)
        logger.info(f"  Send {amount} {currency}: {result} ({tx_hash})")


async def create_amm_pool(client, wallet, issuer_address, currency, token_amount, xrp_amount):
    """Create an AMM pool for XRP/token pair."""
    logger.info(f"\nCreating AMM pool: XRP/{currency}")
    logger.info(f"  Token: {token_amount} {currency}, XRP: {xrp_amount}")

    try:
        amm_create = AMMCreate(
            account=wallet.address,
            amount=IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer_address,
                value=token_amount
            ),
            amount2=xrp_to_drops(Decimal(xrp_amount)),
            trading_fee=500  # 0.5%
        )

        result, tx_hash = await submit_tx(client, wallet, amm_create)
        logger.info(f"  AMMCreate: {result} ({tx_hash})")
        return result == "tesSUCCESS"
    except Exception as e:
        logger.error(f"  AMMCreate failed: {e}")
        return False


async def create_offers(client, wallet, issuer_address, currency, mid_rate):
    """Create buy and sell offers to populate the order book."""
    logger.info(f"\nCreating order book offers for XRP/{currency}")
    spreads = [
        (Decimal("0.98"), Decimal("50")),
        (Decimal("0.95"), Decimal("100")),
        (Decimal("0.90"), Decimal("200")),
    ]

    for spread_factor, size_xrp in spreads:
        rate = Decimal(str(mid_rate)) * spread_factor
        token_amount = str(size_xrp * rate)

        sell_offer = OfferCreate(
            account=wallet.address,
            taker_gets=xrp_to_drops(size_xrp),
            taker_pays=IssuedCurrencyAmount(
                currency=currency, issuer=issuer_address, value=token_amount
            ),
        )
        result, tx_hash = await submit_tx(client, wallet, sell_offer)
        logger.info(f"  Sell {size_xrp} XRP @ {rate}: {result} ({tx_hash})")

    for spread_factor, size_xrp in spreads:
        rate = Decimal(str(mid_rate)) / spread_factor
        token_amount = str(size_xrp * Decimal(str(mid_rate)))

        buy_offer = OfferCreate(
            account=wallet.address,
            taker_gets=IssuedCurrencyAmount(
                currency=currency, issuer=issuer_address, value=token_amount
            ),
            taker_pays=xrp_to_drops(size_xrp),
        )
        result, tx_hash = await submit_tx(client, wallet, buy_offer)
        logger.info(f"  Buy {size_xrp} XRP @ {rate}: {result} ({tx_hash})")


async def main():
    logger.info("=" * 60)
    logger.info("XRPL TESTNET MARKET SETUP")
    logger.info("=" * 60)

    sync_client = JsonRpcClient(TESTNET_URL)
    client = AsyncJsonRpcClient(TESTNET_URL)

    spot_wallet = Wallet.from_seed(SPOT_TRADER_WALLET["seed"])
    flash_wallet = Wallet.from_seed(FLASH_LOAN_WALLET["seed"])

    # Step 1: Create issuer
    issuer = await create_issuer(sync_client)

    # Step 2: Enable rippling
    await enable_rippling(client, issuer)

    # Step 3: Fund trading wallets with tokens
    await setup_trust_and_fund(client, issuer, spot_wallet, "Spot Trader", TOKENS)
    await setup_trust_and_fund(client, issuer, flash_wallet, "Flash Loan", TOKENS)

    # Step 4: Fund issuer with extra XRP for AMM pools
    logger.info("\nFunding issuer with extra XRP for AMM pools...")
    for w, name in [(spot_wallet, "Spot"), (flash_wallet, "Flash")]:
        payment = Payment(
            account=w.address,
            destination=issuer.address,
            amount=xrp_to_drops(Decimal("30"))
        )
        result, tx_hash = await submit_tx(client, w, payment)
        logger.info(f"  {name} -> Issuer 30 XRP: {result} ({tx_hash})")

    # Issuer also needs trust lines to itself? No - issuer IS the issuer.
    # But issuer needs tokens in their own account to create AMM.
    # Actually, the AMM creator needs to hold both assets.
    # Let's have spot_wallet create the AMM pools since it has tokens + XRP.

    # Step 5: Create AMM pools
    mid_rates = {"USD": "0.50", "EUR": "0.46", "BTC": "0.00001"}
    for currency, config in TOKENS.items():
        await create_amm_pool(
            client, spot_wallet, issuer.address,
            currency, config["token_pool"], config["xrp_pool"]
        )

    # Step 6: Create order book offers from flash wallet
    for currency, mid_rate in mid_rates.items():
        await create_offers(client, flash_wallet, issuer.address, currency, mid_rate)

    # Step 7: Save issuer config
    os.makedirs("config", exist_ok=True)
    issuer_config = {
        "address": issuer.address,
        "seed": issuer.seed,
        "public_key": issuer.public_key,
        "currencies": list(TOKENS.keys()),
        "note": "Thoth Oracle testnet issuer - DO NOT use on mainnet"
    }
    with open(ISSUER_CONFIG_PATH, "w") as f:
        json.dump(issuer_config, f, indent=2)
    logger.info(f"\nIssuer config saved to {ISSUER_CONFIG_PATH}")

    # Step 8: Verify final state
    logger.info("\n" + "=" * 60)
    logger.info("FINAL STATE")
    logger.info("=" * 60)

    for name, w in [("Issuer", issuer), ("Spot", spot_wallet), ("Flash", flash_wallet)]:
        info = await client.request(AccountInfo(account=w.address))
        bal = int(info.result["account_data"]["Balance"]) / 1e6
        lines = await client.request(AccountLines(account=w.address))
        logger.info(f"\n{name}: {w.address}")
        logger.info(f"  XRP: {bal:.6f}")
        for l in lines.result.get("lines", []):
            if l["account"] == issuer.address:
                logger.info(f"  {l['currency']}: {l['balance']}")

    logger.info("\n✅ Testnet market setup complete!")
    logger.info(f"   Issuer: {issuer.address}")
    logger.info(f"   Tokens: {list(TOKENS.keys())}")
    logger.info(f"   AMM pools: XRP/USD, XRP/EUR, XRP/BTC")
    logger.info(f"   Order book: 6 offers per pair (18 total)")


if __name__ == "__main__":
    asyncio.run(main())
