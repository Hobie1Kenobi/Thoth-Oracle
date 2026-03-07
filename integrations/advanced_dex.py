"""
Advanced DEX Trading Module
Ports advanced offer types from xrpl-cli-ng:
  - Immediate-or-Cancel (IOC): fill what's available, cancel rest
  - Fill-or-Kill (FOK): all-or-nothing execution
  - Passive offers: market-making without consuming
  - Expiration: time-limited offers
  - Atomic replace: cancel+create in one transaction
"""

import logging
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime, timezone

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import OfferCreate, OfferCancel, OfferCreateFlag
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time

logger = logging.getLogger(__name__)


def build_amount(currency: str, value: Decimal, issuer: Optional[str] = None):
    """Build an XRPL amount (drops for XRP, IssuedCurrencyAmount for IOUs)."""
    if currency.upper() == "XRP":
        return xrp_to_drops(value)
    if not issuer:
        raise ValueError(f"Issuer required for IOU currency {currency}")
    return IssuedCurrencyAmount(currency=currency.upper(), issuer=issuer, value=str(value))


class AdvancedDEX:
    """Advanced DEX trading with IOC, FOK, passive, expiration, and replace."""

    def __init__(self, client: AsyncJsonRpcClient, wallet: Wallet):
        self.client = client
        self.wallet = wallet

    async def create_offer(
        self,
        taker_pays_currency: str,
        taker_pays_amount: Decimal,
        taker_pays_issuer: Optional[str],
        taker_gets_currency: str,
        taker_gets_amount: Decimal,
        taker_gets_issuer: Optional[str],
        immediate_or_cancel: bool = False,
        fill_or_kill: bool = False,
        passive: bool = False,
        sell: bool = False,
        expiration: Optional[datetime] = None,
        replace_sequence: Optional[int] = None,
    ) -> Dict:
        """Create an offer with advanced flags.

        Args:
            taker_pays_*: What the taker pays us (what we receive)
            taker_gets_*: What the taker gets from us (what we provide)
            immediate_or_cancel: Fill available amount, cancel remainder
            fill_or_kill: Fill completely or cancel entire offer
            passive: Don't consume matching offers (market making)
            sell: Sell all taker_gets even if we receive more than taker_pays
            expiration: Auto-cancel after this time
            replace_sequence: Atomically replace this existing offer
        """
        try:
            taker_pays = build_amount(taker_pays_currency, taker_pays_amount, taker_pays_issuer)
            taker_gets = build_amount(taker_gets_currency, taker_gets_amount, taker_gets_issuer)

            flags = 0
            if immediate_or_cancel:
                flags |= OfferCreateFlag.TF_IMMEDIATE_OR_CANCEL
            if fill_or_kill:
                flags |= OfferCreateFlag.TF_FILL_OR_KILL
            if passive:
                flags |= OfferCreateFlag.TF_PASSIVE
            if sell:
                flags |= OfferCreateFlag.TF_SELL

            tx_kwargs = {
                "account": self.wallet.address,
                "taker_pays": taker_pays,
                "taker_gets": taker_gets,
            }
            if flags:
                tx_kwargs["flags"] = flags
            if expiration:
                tx_kwargs["expiration"] = datetime_to_ripple_time(expiration)
            if replace_sequence is not None:
                tx_kwargs["offer_sequence"] = replace_sequence

            offer = OfferCreate(**tx_kwargs)

            response = await submit_and_wait(
                transaction=offer, client=self.client, wallet=self.wallet
            )

            meta = response.result.get("meta", {})
            result_code = meta.get("TransactionResult", "unknown")
            tx_hash = response.result.get("hash", "")
            sequence = response.result.get("tx_json", {}).get("Sequence", 0)

            is_killed = result_code == "tecKILLED"
            success = result_code == "tesSUCCESS" or is_killed

            return {
                "success": success,
                "hash": tx_hash,
                "result": result_code,
                "sequence": sequence,
                "killed": is_killed,
                "flags": {
                    "ioc": immediate_or_cancel,
                    "fok": fill_or_kill,
                    "passive": passive,
                    "sell": sell,
                },
            }

        except Exception as e:
            logger.error(f"OfferCreate error: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_offer(self, offer_sequence: int) -> Dict:
        """Cancel an existing offer by sequence number."""
        try:
            tx = OfferCancel(
                account=self.wallet.address,
                offer_sequence=offer_sequence,
            )
            response = await submit_and_wait(
                transaction=tx, client=self.client, wallet=self.wallet
            )
            result_code = response.result.get("meta", {}).get("TransactionResult", "unknown")
            return {
                "success": result_code == "tesSUCCESS",
                "hash": response.result.get("hash", ""),
                "result": result_code,
            }
        except Exception as e:
            logger.error(f"OfferCancel error: {e}")
            return {"success": False, "error": str(e)}

    async def market_buy(
        self, currency: str, amount: Decimal, issuer: str, max_xrp: Decimal
    ) -> Dict:
        """IOC market buy: get as much of currency as possible for up to max_xrp."""
        return await self.create_offer(
            taker_pays_currency=currency,
            taker_pays_amount=amount,
            taker_pays_issuer=issuer,
            taker_gets_currency="XRP",
            taker_gets_amount=max_xrp,
            taker_gets_issuer=None,
            immediate_or_cancel=True,
            sell=True,
        )

    async def market_sell(
        self, currency: str, amount: Decimal, issuer: str, min_xrp: Decimal
    ) -> Dict:
        """IOC market sell: sell currency for as much XRP as possible."""
        return await self.create_offer(
            taker_pays_currency="XRP",
            taker_pays_amount=min_xrp,
            taker_pays_issuer=None,
            taker_gets_currency=currency,
            taker_gets_amount=amount,
            taker_gets_issuer=issuer,
            immediate_or_cancel=True,
            sell=True,
        )

    async def limit_order(
        self,
        side: str,
        currency: str,
        amount: Decimal,
        issuer: str,
        price_xrp: Decimal,
        expiration: Optional[datetime] = None,
    ) -> Dict:
        """Place a passive limit order (market making)."""
        if side == "buy":
            return await self.create_offer(
                taker_pays_currency=currency,
                taker_pays_amount=amount,
                taker_pays_issuer=issuer,
                taker_gets_currency="XRP",
                taker_gets_amount=price_xrp,
                taker_gets_issuer=None,
                passive=True,
                expiration=expiration,
            )
        else:
            return await self.create_offer(
                taker_pays_currency="XRP",
                taker_pays_amount=price_xrp,
                taker_pays_issuer=None,
                taker_gets_currency=currency,
                taker_gets_amount=amount,
                taker_gets_issuer=issuer,
                passive=True,
                expiration=expiration,
            )
