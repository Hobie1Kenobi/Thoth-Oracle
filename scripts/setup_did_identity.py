"""
Thoth Oracle - DID Identity & On-Ledger Documentation Setup

Creates W3C-compliant Decentralized Identifiers (DIDs) on the XRPL testnet
that document the entire Thoth Oracle project:
- Project identity and capabilities
- Links between trading wallets, issuer, and owner account
- Trust line registry
- Transaction history references

The DID documents are visible on Bithomp and any XRPL explorer.

Usage:
    python scripts/setup_did_identity.py                    # Set up project DIDs
    python scripts/setup_did_identity.py --owner-seed SEED  # Also set up owner DID
"""

import asyncio
import json
import logging
import os
import sys
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import DIDSet, Payment, TrustSet, Memo
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, AccountLines, AccountObjects, AccountTx
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, str_to_hex

from config.test_wallets import TESTNET_URL, SPOT_TRADER_WALLET, FLASH_LOAN_WALLET

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

OWNER_ACCOUNT = "rHTHaQ9EtuKkSSAoh9R1ViGt69J2ZMHQWq"

ISSUER_CONFIG_PATH = "config/testnet_issuer.json"


def build_project_did_document(wallet_address, role, owner_account, issuer_address=None):
    """Build a W3C DID document for a Thoth Oracle wallet."""
    did_doc = {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1"
        ],
        "id": f"did:xrpl:testnet:{wallet_address}",
        "controller": f"did:xrpl:testnet:{owner_account}",
        "service": [
            {
                "id": f"did:xrpl:testnet:{wallet_address}#thoth-oracle",
                "type": "ThothOracleAgent",
                "serviceEndpoint": {
                    "project": "Thoth Oracle System",
                    "role": role,
                    "network": "XRPL Testnet",
                    "owner": owner_account,
                    "repository": "https://github.com/Hobie1Kenobi/Thoth-Oracle",
                    "capabilities": _get_capabilities(role),
                    "created": datetime.now(timezone.utc).isoformat(),
                }
            }
        ]
    }

    if issuer_address:
        did_doc["service"].append({
            "id": f"did:xrpl:testnet:{wallet_address}#token-issuer",
            "type": "TokenIssuer",
            "serviceEndpoint": {
                "issuer": issuer_address,
                "tokens": ["USD", "EUR", "BTC"],
                "network": "XRPL Testnet"
            }
        })

    return did_doc


def _get_capabilities(role):
    caps = {
        "spot_trader": [
            "arbitrage_detection", "spot_trading", "risk_assessment",
            "order_book_scanning", "quantum_prediction"
        ],
        "flash_loan": [
            "flash_loan_execution", "path_finding", "cross_currency_trading",
            "arbitrage_execution", "quantum_optimization"
        ],
        "issuer": [
            "token_issuance", "liquidity_provision", "market_making",
            "amm_pool_management"
        ],
        "owner": [
            "project_governance", "agent_coordination", "identity_management",
            "quantum_computing_ibm", "strategy_oversight"
        ]
    }
    return caps.get(role, [])


def build_owner_did_document(owner_address, spot_address, flash_address, issuer_address):
    """Build the master DID document for the project owner."""
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1"
        ],
        "id": f"did:xrpl:testnet:{owner_address}",
        "controller": f"did:xrpl:testnet:{owner_address}",
        "verificationMethod": [
            {
                "id": f"did:xrpl:testnet:{owner_address}#master",
                "type": "Ed25519VerificationKey2020",
                "controller": f"did:xrpl:testnet:{owner_address}"
            }
        ],
        "service": [
            {
                "id": f"did:xrpl:testnet:{owner_address}#thoth-oracle-project",
                "type": "ThothOracleProject",
                "serviceEndpoint": {
                    "project": "Thoth Oracle System",
                    "description": "Quantum-enhanced cryptocurrency arbitrage and trading system for XRPL DEX",
                    "version": "0.1.0",
                    "repository": "https://github.com/Hobie1Kenobi/Thoth-Oracle",
                    "network": "XRPL Testnet",
                    "created": datetime.now(timezone.utc).isoformat(),
                    "agents": {
                        "spot_trader": {
                            "did": f"did:xrpl:testnet:{spot_address}",
                            "address": spot_address,
                            "role": "Spot trading and arbitrage detection"
                        },
                        "flash_loan": {
                            "did": f"did:xrpl:testnet:{flash_address}",
                            "address": flash_address,
                            "role": "Flash loan execution and cross-currency trading"
                        },
                        "issuer": {
                            "did": f"did:xrpl:testnet:{issuer_address}",
                            "address": issuer_address,
                            "role": "Token issuance and market making"
                        }
                    },
                    "quantum": {
                        "provider": "IBM Quantum",
                        "backends": ["ibm_fez (156q)", "ibm_marrakesh (156q)", "ibm_torino (133q)"],
                        "strategies": [
                            "Quantum price prediction (variational circuits)",
                            "Quantum arbitrage detection (Grover search)",
                            "Quantum hedging optimization",
                            "Quantum portfolio optimization (simulated annealing)"
                        ]
                    },
                    "trading": {
                        "strategies": ["Direct arbitrage", "Triangular arbitrage", "Flash loan arbitrage"],
                        "issuers_configured": 6,
                        "trust_lines_per_wallet": 14,
                        "tokens_issued": ["USD", "EUR", "BTC"]
                    }
                }
            },
            {
                "id": f"did:xrpl:testnet:{owner_address}#bithomp",
                "type": "LinkedAccount",
                "serviceEndpoint": f"https://test.bithomp.com/en/account/{owner_address}"
            }
        ]
    }


async def submit_tx(client, wallet, tx):
    response = await submit_and_wait(transaction=tx, client=client, wallet=wallet)
    result = response.result.get("meta", {}).get("TransactionResult", "unknown")
    tx_hash = response.result.get("hash", "")
    return result, tx_hash


async def set_did(client, wallet, did_document, data_summary, uri=None):
    """Set DID on a wallet. Stores compact doc on-chain, full doc as data reference."""
    max_bytes = 128
    compact_doc = json.dumps({
        "id": did_document.get("id", "")[:60],
        "svc": did_document.get("service", [{}])[0].get("type", "")[:20]
    }, separators=(',', ':'))[:max_bytes]
    doc_hex = str_to_hex(compact_doc)

    data_summary = data_summary[:max_bytes]
    data_hex = str_to_hex(data_summary)

    if uri:
        uri = uri[:max_bytes]
    uri_hex = str_to_hex(uri) if uri else None

    tx = DIDSet(
        account=wallet.address,
        did_document=doc_hex,
        data=data_hex,
        uri=uri_hex
    )

    result, tx_hash = await submit_tx(client, wallet, tx)

    full_doc_path = f"config/did_{wallet.address[:8]}.json"
    os.makedirs("config", exist_ok=True)
    with open(full_doc_path, "w") as f:
        json.dump(did_document, f, indent=2)

    return result, tx_hash


async def send_linking_payment(client, from_wallet, to_address, memo_text):
    """Send a small payment with a memo to create a visible link on Bithomp."""
    memo = Memo(
        memo_type=str_to_hex("text/plain"),
        memo_data=str_to_hex(memo_text)
    )

    payment = Payment(
        account=from_wallet.address,
        destination=to_address,
        amount=xrp_to_drops(1),
        memos=[memo]
    )

    result, tx_hash = await submit_tx(client, from_wallet, payment)
    return result, tx_hash


async def main():
    parser = argparse.ArgumentParser(description="Thoth Oracle DID Setup")
    parser.add_argument("--owner-seed", help="Owner wallet seed for DID on owner account")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("THOTH ORACLE - DID IDENTITY SETUP")
    logger.info("=" * 60)

    client = AsyncJsonRpcClient(TESTNET_URL)

    spot_wallet = Wallet.from_seed(SPOT_TRADER_WALLET["seed"])
    flash_wallet = Wallet.from_seed(FLASH_LOAN_WALLET["seed"])

    issuer_address = None
    issuer_wallet = None
    if os.path.exists(ISSUER_CONFIG_PATH):
        with open(ISSUER_CONFIG_PATH) as f:
            cfg = json.load(f)
            issuer_address = cfg["address"]
            if "seed" in cfg:
                issuer_wallet = Wallet.from_seed(cfg["seed"])

    # Step 1: Fund owner account
    logger.info("\n📤 Step 1: Funding owner account")
    info = await client.request(AccountInfo(account=OWNER_ACCOUNT))
    owner_balance = int(info.result["account_data"]["Balance"]) / 1e6
    logger.info(f"  Owner balance: {owner_balance} XRP")

    if owner_balance < 20:
        amount_to_send = 20
        result, tx_hash = await send_linking_payment(
            client, spot_wallet, OWNER_ACCOUNT,
            "Thoth Oracle: Funding owner account for DID setup"
        )
        logger.info(f"  Sent {amount_to_send} XRP: {result} ({tx_hash[:16]})")

        payment2 = Payment(
            account=spot_wallet.address,
            destination=OWNER_ACCOUNT,
            amount=xrp_to_drops(19),
            memos=[Memo(
                memo_type=str_to_hex("text/plain"),
                memo_data=str_to_hex("Thoth Oracle: Additional funding for DID and trust lines")
            )]
        )
        r2, h2 = await submit_tx(client, spot_wallet, payment2)
        logger.info(f"  Sent 19 XRP: {r2} ({h2[:16]})")

    # Step 2: Create DID on Spot Trader wallet
    logger.info("\n🔑 Step 2: DID on Spot Trader")
    spot_did_doc = build_project_did_document(
        spot_wallet.address, "spot_trader", OWNER_ACCOUNT, issuer_address
    )
    result, tx_hash = await set_did(
        client, spot_wallet, spot_did_doc,
        "Thoth Oracle Spot Trading Agent",
        f"https://github.com/Hobie1Kenobi/Thoth-Oracle"
    )
    logger.info(f"  DIDSet: {result} ({tx_hash[:16]})")
    logger.info(f"  DID: did:xrpl:testnet:{spot_wallet.address}")

    # Step 3: Create DID on Flash Loan wallet
    logger.info("\n🔑 Step 3: DID on Flash Loan")
    flash_did_doc = build_project_did_document(
        flash_wallet.address, "flash_loan", OWNER_ACCOUNT, issuer_address
    )
    result, tx_hash = await set_did(
        client, flash_wallet, flash_did_doc,
        "Thoth Oracle Flash Loan Agent",
        f"https://github.com/Hobie1Kenobi/Thoth-Oracle"
    )
    logger.info(f"  DIDSet: {result} ({tx_hash[:16]})")
    logger.info(f"  DID: did:xrpl:testnet:{flash_wallet.address}")

    # Step 4: Create DID on Issuer wallet
    if issuer_wallet:
        logger.info("\n🔑 Step 4: DID on Issuer")
        issuer_did_doc = build_project_did_document(
            issuer_wallet.address, "issuer", OWNER_ACCOUNT, issuer_address
        )
        result, tx_hash = await set_did(
            client, issuer_wallet, issuer_did_doc,
            "Thoth Oracle Token Issuer",
            f"https://github.com/Hobie1Kenobi/Thoth-Oracle"
        )
        logger.info(f"  DIDSet: {result} ({tx_hash[:16]})")
        logger.info(f"  DID: did:xrpl:testnet:{issuer_wallet.address}")

    # Step 5: Send linking transactions to owner (visible on Bithomp)
    logger.info("\n🔗 Step 5: Linking transactions to owner")
    links = [
        (spot_wallet, "Thoth Oracle: Spot Trader Agent linked to owner"),
        (flash_wallet, "Thoth Oracle: Flash Loan Agent linked to owner"),
    ]
    if issuer_wallet:
        links.append((issuer_wallet, "Thoth Oracle: Token Issuer linked to owner"))

    for wallet, memo in links:
        result, tx_hash = await send_linking_payment(client, wallet, OWNER_ACCOUNT, memo)
        logger.info(f"  {wallet.address[:15]}... -> owner: {result} ({tx_hash[:16]})")

    # Step 6: Set up owner DID (if seed provided)
    if args.owner_seed:
        logger.info("\n🔑 Step 6: DID on Owner Account")
        owner_wallet = Wallet.from_seed(args.owner_seed)
        if owner_wallet.address != OWNER_ACCOUNT:
            logger.error(f"  Seed doesn't match owner account! Got {owner_wallet.address}")
        else:
            owner_did_doc = build_owner_did_document(
                OWNER_ACCOUNT, spot_wallet.address, flash_wallet.address,
                issuer_address or "not_set"
            )
            result, tx_hash = await set_did(
                client, owner_wallet, owner_did_doc,
                "Thoth Oracle Project - Owner Identity",
                "https://github.com/Hobie1Kenobi/Thoth-Oracle"
            )
            logger.info(f"  DIDSet: {result} ({tx_hash[:16]})")
            logger.info(f"  DID: did:xrpl:testnet:{OWNER_ACCOUNT}")

            # Set up trust lines from owner to Thoth issuer
            if issuer_address:
                logger.info("\n  Setting up trust lines from owner to Thoth issuer...")
                for currency in ["USD", "EUR", "BTC"]:
                    trust = TrustSet(
                        account=owner_wallet.address,
                        limit_amount=IssuedCurrencyAmount(
                            currency=currency, issuer=issuer_address, value="1000000000"
                        )
                    )
                    r, h = await submit_tx(client, owner_wallet, trust)
                    logger.info(f"    TrustSet {currency}: {r} ({h[:16]})")

                # Send some tokens to owner
                logger.info("  Sending tokens to owner...")
                for currency, amount in [("USD", "1000"), ("EUR", "1000"), ("BTC", "0.1")]:
                    if issuer_wallet:
                        pay = Payment(
                            account=issuer_wallet.address,
                            destination=OWNER_ACCOUNT,
                            amount=IssuedCurrencyAmount(
                                currency=currency, issuer=issuer_address, value=amount
                            )
                        )
                        r, h = await submit_tx(client, issuer_wallet, pay)
                        logger.info(f"    Sent {amount} {currency}: {r} ({h[:16]})")
    else:
        logger.info("\n📝 Step 6: Owner DID (skipped - no --owner-seed provided)")
        logger.info(f"  To set up DID on your account, run:")
        logger.info(f"  python scripts/setup_did_identity.py --owner-seed YOUR_SEED")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("DID IDENTITY SETUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"\nProject DIDs:")
    logger.info(f"  Spot Trader: did:xrpl:testnet:{spot_wallet.address}")
    logger.info(f"  Flash Loan:  did:xrpl:testnet:{flash_wallet.address}")
    if issuer_wallet:
        logger.info(f"  Issuer:      did:xrpl:testnet:{issuer_wallet.address}")
    logger.info(f"\nOwner account: {OWNER_ACCOUNT}")
    logger.info(f"  Bithomp: https://test.bithomp.com/en/account/{OWNER_ACCOUNT}")
    logger.info(f"\nAll wallets are linked to the owner via on-ledger transactions.")
    logger.info(f"View on Bithomp to see trust lines, transactions, and DID documents.")


if __name__ == "__main__":
    asyncio.run(main())
