"""
Set up trust lines for all trading wallets on XRPL testnet.
Creates TrustSet transactions for every issuer/currency pair in exchange_issuers.py.

Usage:
    python scripts/setup_trust_lines.py
"""

import asyncio
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import TrustSet
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, AccountLines
from xrpl.asyncio.transaction import submit_and_wait

from config.exchange_issuers import EXCHANGE_ISSUERS
from config.test_wallets import TESTNET_URL, SPOT_TRADER_WALLET, FLASH_LOAN_WALLET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

TRUST_LIMIT = "1000000000"


async def get_existing_trust_lines(client, address):
    """Get set of existing trust lines as (issuer, currency) tuples."""
    resp = await client.request(AccountLines(account=address))
    lines = resp.result.get("lines", [])
    return {(l["account"], l["currency"]) for l in lines}


async def setup_trust_lines_for_wallet(client, wallet, wallet_name):
    """Set up all needed trust lines for a wallet."""
    logger.info(f"\nSetting up trust lines for {wallet_name}: {wallet.address}")

    info = await client.request(AccountInfo(account=wallet.address))
    balance = int(info.result["account_data"]["Balance"]) / 1_000_000
    logger.info(f"  Balance: {balance} XRP")

    existing = await get_existing_trust_lines(client, wallet.address)
    logger.info(f"  Existing trust lines: {len(existing)}")

    created = 0
    skipped = 0
    failed = 0

    for issuer_name, config in EXCHANGE_ISSUERS.items():
        issuer_address = config["address"]
        for currency in config["currencies"]:
            if (issuer_address, currency) in existing:
                logger.info(f"  SKIP {issuer_name} {currency} (already exists)")
                skipped += 1
                continue

            try:
                trust_set = TrustSet(
                    account=wallet.address,
                    limit_amount=IssuedCurrencyAmount(
                        currency=currency,
                        issuer=issuer_address,
                        value=TRUST_LIMIT
                    )
                )

                response = await submit_and_wait(
                    transaction=trust_set,
                    client=client,
                    wallet=wallet
                )

                if response.result.get("validated", False):
                    tx_hash = response.result.get("hash", "unknown")
                    logger.info(f"  OK   {issuer_name} {currency} -> {tx_hash[:16]}...")
                    created += 1
                else:
                    engine_result = response.result.get("engine_result", "unknown")
                    logger.warning(f"  WARN {issuer_name} {currency}: {engine_result}")
                    failed += 1

            except Exception as e:
                logger.error(f"  FAIL {issuer_name} {currency}: {e}")
                failed += 1

    logger.info(f"\n  {wallet_name} summary: {created} created, {skipped} skipped, {failed} failed")
    return created, skipped, failed


async def main():
    logger.info("=" * 60)
    logger.info("XRPL TESTNET TRUST LINE SETUP")
    logger.info("=" * 60)

    client = AsyncJsonRpcClient(TESTNET_URL)

    wallets = [
        (Wallet.from_seed(SPOT_TRADER_WALLET["seed"]), "Spot Trader"),
        (Wallet.from_seed(FLASH_LOAN_WALLET["seed"]), "Flash Loan"),
    ]

    total_created = 0
    total_skipped = 0
    total_failed = 0

    for wallet, name in wallets:
        c, s, f = await setup_trust_lines_for_wallet(client, wallet, name)
        total_created += c
        total_skipped += s
        total_failed += f

    logger.info("\n" + "=" * 60)
    logger.info(f"TOTAL: {total_created} created, {total_skipped} skipped, {total_failed} failed")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
