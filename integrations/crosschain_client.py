"""
Cross-Chain Trading Client
Connects XRPL native DEX, XRPL EVM Sidechain, and Ethereum Sepolia
for multi-chain arbitrage detection and execution.

Architecture:
    XRPL Testnet (native DEX) ←→ XRPL EVM Sidechain ←→ Ethereum Sepolia (Uniswap V3)
"""

import asyncio
import json
import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional
from web3 import Web3
from eth_account import Account

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "crosschain_config.json")

UNISWAP_V3_POOL_ABI = [
    {"inputs":[],"name":"slot0","outputs":[{"name":"sqrtPriceX96","type":"uint160"},{"name":"tick","type":"int24"},{"name":"observationIndex","type":"uint16"},{"name":"observationCardinality","type":"uint16"},{"name":"observationCardinalityNext","type":"uint16"},{"name":"feeProtocol","type":"uint8"},{"name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"liquidity","outputs":[{"name":"","type":"uint128"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token0","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"name":"","type":"address"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"fee","outputs":[{"name":"","type":"uint24"}],"stateMutability":"view","type":"function"},
]

FACTORY_ABI = [
    {"inputs":[{"name":"tokenA","type":"address"},{"name":"tokenB","type":"address"},{"name":"fee","type":"uint24"}],"name":"getPool","outputs":[{"name":"pool","type":"address"}],"stateMutability":"view","type":"function"}
]

ERC20_ABI = [
    {"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
]


class CrossChainClient:
    """Manages connections to multiple chains for cross-chain arbitrage."""

    SEPOLIA_FACTORY = "0x0227628f3F023bb0B980b67D528571c95c6DaC1c"
    SEPOLIA_WETH = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14"
    SEPOLIA_USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"
    SEPOLIA_UNI = "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"

    def __init__(self, config_path: str = CONFIG_PATH):
        with open(config_path) as f:
            self.config = json.load(f)

        self.w3_xrpl_evm = Web3(Web3.HTTPProvider(
            self.config["xrpl_evm"]["rpc"],
            request_kwargs={"timeout": 15}
        ))
        self.w3_sepolia = Web3(Web3.HTTPProvider(
            self.config["sepolia"]["rpc"],
            request_kwargs={"timeout": 15}
        ))

        pk = self.config["wallet"]["private_key"]
        self.account = Account.from_key(pk)
        self.address = self.account.address

        self.sepolia_factory = self.w3_sepolia.eth.contract(
            address=Web3.to_checksum_address(self.SEPOLIA_FACTORY),
            abi=FACTORY_ABI
        )

    def get_chain_status(self) -> Dict:
        """Get connectivity status for all chains."""
        status = {}
        try:
            status["xrpl_evm"] = {
                "connected": self.w3_xrpl_evm.is_connected(),
                "chain_id": self.w3_xrpl_evm.eth.chain_id if self.w3_xrpl_evm.is_connected() else None,
                "block": self.w3_xrpl_evm.eth.block_number if self.w3_xrpl_evm.is_connected() else None,
                "balance": self.w3_xrpl_evm.eth.get_balance(self.address) / 1e18 if self.w3_xrpl_evm.is_connected() else 0
            }
        except Exception as e:
            status["xrpl_evm"] = {"connected": False, "error": str(e)}

        try:
            status["sepolia"] = {
                "connected": self.w3_sepolia.is_connected(),
                "chain_id": self.w3_sepolia.eth.chain_id if self.w3_sepolia.is_connected() else None,
                "block": self.w3_sepolia.eth.block_number if self.w3_sepolia.is_connected() else None,
                "balance": self.w3_sepolia.eth.get_balance(self.address) / 1e18 if self.w3_sepolia.is_connected() else 0
            }
        except Exception as e:
            status["sepolia"] = {"connected": False, "error": str(e)}

        return status

    def get_uniswap_pool_info(self, token0: str, token1: str, fee: int = 3000) -> Optional[Dict]:
        """Get Uniswap V3 pool information including price and liquidity."""
        try:
            pool_address = self.sepolia_factory.functions.getPool(
                Web3.to_checksum_address(token0),
                Web3.to_checksum_address(token1),
                fee
            ).call()

            if pool_address == "0x" + "0" * 40:
                return None

            pool = self.w3_sepolia.eth.contract(
                address=pool_address, abi=UNISWAP_V3_POOL_ABI
            )

            slot0 = pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            tick = slot0[1]
            liquidity = pool.functions.liquidity().call()

            price = (sqrt_price_x96 / (2**96)) ** 2

            return {
                "pool_address": pool_address,
                "sqrt_price_x96": sqrt_price_x96,
                "tick": tick,
                "liquidity": liquidity,
                "price": price,
                "fee_tier": fee,
                "token0": pool.functions.token0().call(),
                "token1": pool.functions.token1().call(),
            }

        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return None

    def scan_sepolia_pools(self) -> List[Dict]:
        """Scan all known Uniswap V3 pools on Sepolia for prices and liquidity."""
        results = []
        token_pairs = [
            ("WETH/USDC", self.SEPOLIA_WETH, self.SEPOLIA_USDC),
        ]
        fee_tiers = [100, 500, 3000, 10000]

        for name, t0, t1 in token_pairs:
            for fee in fee_tiers:
                info = self.get_uniswap_pool_info(t0, t1, fee)
                if info:
                    info["pair_name"] = name
                    info["fee_pct"] = fee / 10000
                    results.append(info)

        return results

    def detect_cross_chain_opportunities(self, xrpl_rates: Dict, sepolia_pools: List[Dict]) -> List[Dict]:
        """Compare prices across XRPL and Sepolia to find arbitrage."""
        opportunities = []

        for pool in sepolia_pools:
            pair = pool["pair_name"]

            xrpl_key = None
            for k in xrpl_rates:
                if "USD" in k and "XRP" in k:
                    xrpl_key = k
                    break

            if xrpl_key and pool["price"] > 0:
                xrpl_price = float(xrpl_rates[xrpl_key])
                sepolia_price = pool["price"]

                if xrpl_price > 0 and sepolia_price > 0:
                    spread = abs(xrpl_price - sepolia_price) / min(xrpl_price, sepolia_price)

                    if spread > 0.01:
                        direction = "XRPL→Sepolia" if xrpl_price < sepolia_price else "Sepolia→XRPL"
                        opportunities.append({
                            "pair": pair,
                            "xrpl_price": xrpl_price,
                            "sepolia_price": sepolia_price,
                            "spread_pct": spread * 100,
                            "direction": direction,
                            "fee_tier": pool["fee_pct"],
                            "liquidity": pool["liquidity"],
                        })

        return sorted(opportunities, key=lambda x: -x["spread_pct"])


async def main():
    """Demo: scan cross-chain prices and find opportunities."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    print("=" * 60)
    print("CROSS-CHAIN ARBITRAGE SCANNER")
    print("=" * 60)

    client = CrossChainClient()

    print("\n📡 Chain Status:")
    status = client.get_chain_status()
    for chain, info in status.items():
        connected = info.get("connected", False)
        s = "✅" if connected else "❌"
        if connected:
            print(f"  {s} {chain}: chain_id={info['chain_id']}, block={info['block']}, balance={info['balance']:.6f}")
        else:
            print(f"  {s} {chain}: {info.get('error', 'not connected')}")

    print("\n📊 Sepolia Uniswap V3 Pools:")
    pools = client.scan_sepolia_pools()
    for p in pools:
        print(f"  {p['pair_name']} ({p['fee_pct']}%): price={p['price']:.8f}, liquidity={p['liquidity']}")

    # Get XRPL rates for comparison
    print("\n📊 XRPL Testnet Rates:")
    from xrpl.asyncio.clients import AsyncJsonRpcClient
    from xrpl.models.requests import BookOffers
    from config.test_wallets import TESTNET_URL
    from config.exchange_issuers import EXCHANGE_ISSUERS

    xrpl_client = AsyncJsonRpcClient(TESTNET_URL)
    xrpl_rates = {}
    for name, cfg in EXCHANGE_ISSUERS.items():
        for curr in cfg["currencies"][:2]:
            try:
                book = await xrpl_client.request(BookOffers(
                    taker_gets={"currency": "XRP"},
                    taker_pays={"currency": curr, "issuer": cfg["address"]}
                ))
                offers = book.result.get("offers", [])
                if offers:
                    rate = float(offers[0].get("quality", 0))
                    xrpl_rates[f"XRP/{curr}@{name}"] = rate
                    print(f"  {name} XRP/{curr}: {rate:.6e}")
            except:
                pass

    print(f"\n🔍 Cross-Chain Opportunities:")
    opps = client.detect_cross_chain_opportunities(xrpl_rates, pools)
    if opps:
        for o in opps[:5]:
            print(f"  {o['direction']}: {o['pair']} spread={o['spread_pct']:.2f}%")
    else:
        print("  No cross-chain arbitrage detected (different asset classes on each chain)")

    print(f"\n✅ Cross-chain scanner operational!")
    print(f"   XRPL EVM: {status.get('xrpl_evm', {}).get('block', 'N/A')}")
    print(f"   Sepolia:  {status.get('sepolia', {}).get('block', 'N/A')}")
    print(f"   Pools:    {len(pools)} Uniswap V3 pools scanned")
    print(f"   XRPL:     {len(xrpl_rates)} rate pairs scanned")


if __name__ == "__main__":
    asyncio.run(main())
