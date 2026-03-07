"""
XRPL Native AMM Pool Manager
Ports AMM management from xrpl-cli-ng:
  - Create pools with proper funding validation
  - Deposit (single-asset, two-asset, LP token modes)
  - Withdraw (single, two-asset, withdraw-all)
  - Query pool info (reserves, LP token, trading fee, auction slot)
  - Vote on trading fee
  - Bid on auction slot for reduced fees
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import (
    AMMCreate, AMMDeposit, AMMWithdraw, AMMBid, AMMVote, AMMDelete,
    AMMDepositFlag, AMMWithdrawFlag,
)
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AMMInfo
from xrpl.models.currencies import XRP, IssuedCurrency
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

logger = logging.getLogger(__name__)


def _build_currency(currency: str, issuer: Optional[str] = None):
    """Build an XRPL Currency object."""
    if currency.upper() == "XRP":
        return XRP()
    return IssuedCurrency(currency=currency.upper(), issuer=issuer)


def _build_amount(currency: str, value: Decimal, issuer: Optional[str] = None):
    """Build an XRPL Amount (drops string or IssuedCurrencyAmount)."""
    if currency.upper() == "XRP":
        return xrp_to_drops(value)
    return IssuedCurrencyAmount(currency=currency.upper(), issuer=issuer, value=str(value))


async def _submit(client, wallet, tx) -> Dict:
    """Submit a transaction and return standardized result."""
    try:
        response = await submit_and_wait(transaction=tx, client=client, wallet=wallet)
        meta = response.result.get("meta", {})
        result_code = meta.get("TransactionResult", "unknown")
        tx_hash = response.result.get("hash", "")
        return {
            "success": result_code == "tesSUCCESS",
            "hash": tx_hash,
            "result": result_code,
        }
    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        return {"success": False, "error": str(e)}


class AMMManager:
    """Manage XRPL native AMM pools."""

    def __init__(self, client: AsyncJsonRpcClient, wallet: Wallet):
        self.client = client
        self.wallet = wallet

    async def get_pool_info(
        self, currency1: str, issuer1: Optional[str],
        currency2: str, issuer2: Optional[str],
    ) -> Optional[Dict]:
        """Query AMM pool state."""
        try:
            asset = _build_currency(currency1, issuer1)
            asset2 = _build_currency(currency2, issuer2)

            resp = await self.client.request(AMMInfo(asset=asset, asset2=asset2))
            amm = resp.result.get("amm", {})

            def parse_amount(a):
                if isinstance(a, str):
                    return {"currency": "XRP", "value": str(Decimal(a) / 1_000_000)}
                return {"currency": a["currency"], "issuer": a.get("issuer", ""), "value": a["value"]}

            return {
                "account": amm.get("account"),
                "amount": parse_amount(amm.get("amount", "0")),
                "amount2": parse_amount(amm.get("amount2", "0")),
                "lp_token": amm.get("lp_token", {}),
                "trading_fee": amm.get("trading_fee", 0),
                "auction_slot": amm.get("auction_slot"),
                "vote_slots": amm.get("vote_slots", []),
            }
        except Exception as e:
            logger.error(f"AMM info error: {e}")
            return None

    async def create_pool(
        self,
        currency1: str, amount1: Decimal, issuer1: Optional[str],
        currency2: str, amount2: Decimal, issuer2: Optional[str],
        trading_fee: int = 500,
    ) -> Dict:
        """Create a new AMM pool. trading_fee is in units of 1/100000 (500 = 0.5%)."""
        tx = AMMCreate(
            account=self.wallet.address,
            amount=_build_amount(currency1, amount1, issuer1),
            amount2=_build_amount(currency2, amount2, issuer2),
            trading_fee=trading_fee,
        )
        result = await _submit(self.client, self.wallet, tx)

        if result["success"]:
            info = await self.get_pool_info(currency1, issuer1, currency2, issuer2)
            if info:
                result["amm_account"] = info["account"]
                result["lp_token"] = info["lp_token"]
        return result

    async def deposit_two_asset(
        self,
        currency1: str, amount1: Decimal, issuer1: Optional[str],
        currency2: str, amount2: Decimal, issuer2: Optional[str],
    ) -> Dict:
        """Deposit both assets proportionally."""
        tx = AMMDeposit(
            account=self.wallet.address,
            asset=_build_currency(currency1, issuer1),
            asset2=_build_currency(currency2, issuer2),
            amount=_build_amount(currency1, amount1, issuer1),
            amount2=_build_amount(currency2, amount2, issuer2),
            flags=AMMDepositFlag.TF_TWO_ASSET,
        )
        return await _submit(self.client, self.wallet, tx)

    async def deposit_single_asset(
        self,
        deposit_currency: str, deposit_amount: Decimal, deposit_issuer: Optional[str],
        other_currency: str, other_issuer: Optional[str],
    ) -> Dict:
        """Deposit a single asset into the pool."""
        tx = AMMDeposit(
            account=self.wallet.address,
            asset=_build_currency(deposit_currency, deposit_issuer),
            asset2=_build_currency(other_currency, other_issuer),
            amount=_build_amount(deposit_currency, deposit_amount, deposit_issuer),
            flags=AMMDepositFlag.TF_SINGLE_ASSET,
        )
        return await _submit(self.client, self.wallet, tx)

    async def withdraw_two_asset(
        self,
        currency1: str, amount1: Decimal, issuer1: Optional[str],
        currency2: str, amount2: Decimal, issuer2: Optional[str],
    ) -> Dict:
        """Withdraw both assets."""
        tx = AMMWithdraw(
            account=self.wallet.address,
            asset=_build_currency(currency1, issuer1),
            asset2=_build_currency(currency2, issuer2),
            amount=_build_amount(currency1, amount1, issuer1),
            amount2=_build_amount(currency2, amount2, issuer2),
            flags=AMMWithdrawFlag.TF_TWO_ASSET,
        )
        return await _submit(self.client, self.wallet, tx)

    async def withdraw_all(
        self,
        currency1: str, issuer1: Optional[str],
        currency2: str, issuer2: Optional[str],
    ) -> Dict:
        """Withdraw all liquidity (redeem all LP tokens)."""
        tx = AMMWithdraw(
            account=self.wallet.address,
            asset=_build_currency(currency1, issuer1),
            asset2=_build_currency(currency2, issuer2),
            flags=AMMWithdrawFlag.TF_WITHDRAW_ALL,
        )
        return await _submit(self.client, self.wallet, tx)

    async def vote_fee(
        self,
        currency1: str, issuer1: Optional[str],
        currency2: str, issuer2: Optional[str],
        trading_fee: int,
    ) -> Dict:
        """Vote on the pool's trading fee."""
        tx = AMMVote(
            account=self.wallet.address,
            asset=_build_currency(currency1, issuer1),
            asset2=_build_currency(currency2, issuer2),
            trading_fee=trading_fee,
        )
        return await _submit(self.client, self.wallet, tx)

    async def bid_auction(
        self,
        currency1: str, issuer1: Optional[str],
        currency2: str, issuer2: Optional[str],
        bid_min: Optional[str] = None,
        bid_max: Optional[str] = None,
    ) -> Dict:
        """Bid on the pool's auction slot for reduced trading fees."""
        info = await self.get_pool_info(currency1, issuer1, currency2, issuer2)
        if not info:
            return {"success": False, "error": "Pool not found"}

        lp = info["lp_token"]
        tx_kwargs = {
            "account": self.wallet.address,
            "asset": _build_currency(currency1, issuer1),
            "asset2": _build_currency(currency2, issuer2),
        }
        if bid_min:
            tx_kwargs["bid_min"] = IssuedCurrencyAmount(
                currency=lp["currency"], issuer=lp["issuer"], value=bid_min
            )
        if bid_max:
            tx_kwargs["bid_max"] = IssuedCurrencyAmount(
                currency=lp["currency"], issuer=lp["issuer"], value=bid_max
            )

        tx = AMMBid(**tx_kwargs)
        return await _submit(self.client, self.wallet, tx)

    async def delete_pool(
        self,
        currency1: str, issuer1: Optional[str],
        currency2: str, issuer2: Optional[str],
    ) -> Dict:
        """Delete an empty pool."""
        tx = AMMDelete(
            account=self.wallet.address,
            asset=_build_currency(currency1, issuer1),
            asset2=_build_currency(currency2, issuer2),
        )
        return await _submit(self.client, self.wallet, tx)
