"""
XRPL Price Oracle Publisher
Publishes quantum prediction signals and market data as on-chain price feeds
using the XRPL OracleSet transaction (XLS-47).

Other traders can consume these predictions via the get_aggregate_price RPC.
"""

import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional

from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import OracleSet, OracleDelete
from xrpl.models.requests import GenericRequest
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import str_to_hex

logger = logging.getLogger(__name__)

PROVIDER_NAME = "ThothOracle"
ASSET_CLASS = "currency"


async def _submit(client, wallet, tx) -> Dict:
    try:
        response = await submit_and_wait(transaction=tx, client=client, wallet=wallet)
        meta = response.result.get("meta", {})
        result_code = meta.get("TransactionResult", "unknown")
        return {
            "success": result_code == "tesSUCCESS",
            "hash": response.result.get("hash", ""),
            "result": result_code,
        }
    except Exception as e:
        logger.error(f"Oracle transaction failed: {e}")
        return {"success": False, "error": str(e)}


class OraclePublisher:
    """Publish and manage XRPL price oracles."""

    def __init__(self, client: AsyncJsonRpcClient, wallet: Wallet,
                 oracle_document_id: int = 1):
        self.client = client
        self.wallet = wallet
        self.oracle_document_id = oracle_document_id
        self.provider = PROVIDER_NAME
        self.publish_count = 0

    async def publish_prices(self, prices: List[Dict]) -> Dict:
        """Publish price data to the oracle.

        Args:
            prices: List of dicts with keys:
                - base_asset: e.g. "XRP"
                - quote_asset: e.g. "USD"
                - price: Decimal or float
                - scale: int (decimal places, e.g. 6)

        Example:
            await publisher.publish_prices([
                {"base_asset": "XRP", "quote_asset": "USD", "price": 0.55, "scale": 4},
                {"base_asset": "XRP", "quote_asset": "EUR", "price": 0.51, "scale": 4},
            ])
        """
        from xrpl.models.transactions.oracle_set import PriceData

        price_data_series = []
        for p in prices:
            entry = PriceData(
                base_asset=p["base_asset"],
                quote_asset=p["quote_asset"],
                asset_price=int(Decimal(str(p["price"])) * (10 ** p.get("scale", 4))),
                scale=p.get("scale", 4),
            )
            price_data_series.append(entry)

        tx = OracleSet(
            account=self.wallet.address,
            oracle_document_id=self.oracle_document_id,
            provider=str_to_hex(self.provider),
            asset_class=str_to_hex(ASSET_CLASS),
            last_update_time=int(time.time()),
            price_data_series=price_data_series,
        )

        result = await _submit(self.client, self.wallet, tx)
        if result["success"]:
            self.publish_count += 1
            result["publish_count"] = self.publish_count
        return result

    async def publish_quantum_signal(
        self,
        pair: str,
        prediction: float,
        confidence: float,
        signal: str,
    ) -> Dict:
        """Publish a quantum prediction signal as oracle data.

        Encodes:
            - Prediction value as price (0-1 range, scaled to 10000)
            - Confidence as a second price entry
        """
        base, quote = pair.split("/") if "/" in pair else (pair, "USD")

        prices = [
            {
                "base_asset": base,
                "quote_asset": quote,
                "price": prediction,
                "scale": 4,
            },
        ]
        return await self.publish_prices(prices)

    async def publish_market_data(self, rates: Dict[str, float]) -> Dict:
        """Publish multiple market rates from DEX scanning.

        Args:
            rates: Dict like {"XRP/USD@Bitstamp": 0.55, "XRP/EUR@Gatehub": 0.51}
        """
        prices = []
        for pair_key, rate in rates.items():
            parts = pair_key.split("@")[0].split("/")
            if len(parts) == 2 and rate > 0:
                prices.append({
                    "base_asset": parts[0],
                    "quote_asset": parts[1],
                    "price": rate,
                    "scale": 10,
                })

        if not prices:
            return {"success": False, "error": "No valid prices to publish"}

        return await self.publish_prices(prices[:10])

    async def delete_oracle(self) -> Dict:
        """Delete the oracle from the ledger."""
        tx = OracleDelete(
            account=self.wallet.address,
            oracle_document_id=self.oracle_document_id,
        )
        return await _submit(self.client, self.wallet, tx)

    async def get_oracle_info(self) -> Optional[Dict]:
        """Query the oracle's current state from the ledger."""
        try:
            resp = await self.client.request(GenericRequest(
                command="ledger_entry",
                oracle={
                    "account": self.wallet.address,
                    "oracle_document_id": self.oracle_document_id,
                }
            ))
            if resp.is_successful():
                node = resp.result.get("node", {})
                return {
                    "owner": node.get("Owner"),
                    "provider": node.get("Provider"),
                    "price_data_series": node.get("PriceDataSeries", []),
                    "last_update_time": node.get("LastUpdateTime"),
                    "asset_class": node.get("AssetClass"),
                }
            return None
        except Exception as e:
            logger.error(f"Oracle query error: {e}")
            return None
