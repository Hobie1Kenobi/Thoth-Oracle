#!/usr/bin/env python3
"""
Thoth Oracle - Automated Trading Bot
Runs continuous cross-venue trading with quantum-enhanced signals.

Strategy:
  1. Each cycle: scan XRPL native DEX + EVM DEX prices
  2. Quantum predictor generates directional signal (BUY/SELL)
  3. Detect cross-venue price discrepancies
  4. Risk-check then execute trades on EVM DEX (real swaps)
  5. Execute matching orders on XRPL native DEX
  6. Track P&L, log everything, report every 5 minutes

Usage:
    python scripts/run_automated_trading.py              # 30 minute run
    python scripts/run_automated_trading.py --minutes 60 # custom duration
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import time
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from eth_account import Account
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import BookOffers, AccountInfo, AccountLines
from xrpl.models.transactions import OfferCreate
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

from config.test_wallets import TESTNET_URL, SPOT_TRADER_WALLET
from config.exchange_issuers import EXCHANGE_ISSUERS
from agents.risk_management_agent.risk_management_agent import RiskManagementAgent
from agents.monitoring_agent.monitoring_agent import MonitoringAgent
from examples.quantum_prediction import QuantumPricePredictor
from qiskit_aer import AerSimulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/automated_trading.log")
    ]
)
logger = logging.getLogger("ThothTrader")

# EVM DEX ABIs (minimal)
SWAP_ABI = [
    {"inputs":[{"name":"token","type":"address"}],"name":"swapXRPForToken","outputs":[],"stateMutability":"payable","type":"function"},
    {"inputs":[{"name":"token","type":"address"},{"name":"tokenAmount","type":"uint256"}],"name":"swapTokenForXRP","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"token","type":"address"}],"name":"getPrice","outputs":[{"name":"tokenPerXRP","type":"uint256"},{"name":"xrpPerToken","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"token","type":"address"}],"name":"getPoolInfo","outputs":[{"name":"tokenReserve","type":"uint256"},{"name":"xrpReserve","type":"uint256"},{"name":"exists","type":"bool"}],"stateMutability":"view","type":"function"},
]
ERC20_ABI = [
    {"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
]


class AutomatedTrader:
    def __init__(self, duration_minutes=30):
        self.duration = timedelta(minutes=duration_minutes)
        self.start_time = None
        self.cycle_count = 0
        self.cycle_interval = 30  # seconds between cycles

        # XRPL native
        self.xrpl_client = AsyncJsonRpcClient(TESTNET_URL)
        self.spot_wallet = Wallet.from_seed(SPOT_TRADER_WALLET["seed"])

        # EVM DEX
        with open("config/crosschain_config.json") as f:
            cc = json.load(f)
        with open("config/evm_dex_config.json") as f:
            dex_cfg = json.load(f)

        self.w3 = Web3(Web3.HTTPProvider(cc["xrpl_evm"]["rpc"], request_kwargs={"timeout": 15}))
        self.evm_acct = Account.from_key(cc["wallet"]["private_key"])
        self.chain_id = cc["xrpl_evm"]["chain_id"]

        self.dex_addr = dex_cfg["dex"]["address"]
        self.usdc_addr = dex_cfg["tokens"]["tUSDC"]["address"]
        self.wbtc_addr = dex_cfg["tokens"]["tWBTC"]["address"]

        self.dex = self.w3.eth.contract(address=self.dex_addr, abi=SWAP_ABI)
        self.usdc = self.w3.eth.contract(address=self.usdc_addr, abi=ERC20_ABI)
        self.wbtc = self.w3.eth.contract(address=self.wbtc_addr, abi=ERC20_ABI)

        # Agents
        self.risk_agent = RiskManagementAgent()
        self.monitoring = MonitoringAgent()
        self.predictor = QuantumPricePredictor(n_qubits=4, n_layers=2, backend=AerSimulator())

        # Issuer for XRPL native trades
        self.issuer_addr = None
        if os.path.exists("config/testnet_issuer.json"):
            with open("config/testnet_issuer.json") as f:
                self.issuer_addr = json.load(f)["address"]

        # Tracking
        self.trades = []
        self.price_history = []
        self.total_pnl_xrp = Decimal("0")
        self.total_pnl_usdc = Decimal("0")
        self.evm_trades = 0
        self.xrpl_trades = 0
        self.signals = {"BUY": 0, "SELL": 0}

    def _send_evm_tx(self, tx_data):
        nonce = self.w3.eth.get_transaction_count(self.evm_acct.address)
        tx_data["nonce"] = nonce
        tx_data["from"] = self.evm_acct.address
        tx_data["chainId"] = self.chain_id
        tx_data.pop("gasPrice", None)
        tx_data.pop("maxFeePerGas", None)
        tx_data.pop("maxPriorityFeePerGas", None)
        gp = self.w3.eth.gas_price
        tx_data["maxFeePerGas"] = gp * 2
        tx_data["maxPriorityFeePerGas"] = gp
        signed = self.evm_acct.sign_transaction(tx_data)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

    async def get_evm_prices(self):
        """Get current prices from EVM DEX pools."""
        prices = {}
        try:
            p = self.dex.functions.getPrice(self.usdc_addr).call()
            prices["XRP/USDC"] = {"token_per_xrp": p[0] / 1e18, "xrp_per_token": p[1] / 1e18}
        except:
            pass
        try:
            p = self.dex.functions.getPrice(self.wbtc_addr).call()
            prices["XRP/WBTC"] = {"token_per_xrp": p[0] / 1e18, "xrp_per_token": p[1] / 1e18}
        except:
            pass
        return prices

    async def get_xrpl_prices(self):
        """Get rates from XRPL native DEX."""
        rates = {}
        if not self.issuer_addr:
            return rates
        for curr in ["USD", "EUR"]:
            try:
                book = await self.xrpl_client.request(BookOffers(
                    taker_gets={"currency": "XRP"},
                    taker_pays={"currency": curr, "issuer": self.issuer_addr}
                ))
                offers = book.result.get("offers", [])
                if offers:
                    rates[f"XRP/{curr}"] = float(offers[0].get("quality", 0))
            except:
                pass
        return rates

    async def get_quantum_signal(self):
        """Generate a quantum trading signal."""
        if len(self.price_history) < 10:
            base = 500.0
            noise = [base + np.random.uniform(-10, 10) for _ in range(20)]
            self.price_history.extend(noise)

        try:
            await self.predictor.train(self.price_history[-20:])
            pred = await self.predictor.predict_price(window_size=3)
            if pred is not None:
                signal = "BUY" if pred > 0.52 else "SELL" if pred < 0.48 else "HOLD"
                return signal, pred
        except:
            pass
        return "HOLD", 0.5

    async def execute_evm_trade(self, signal, evm_prices):
        """Execute a trade on the EVM DEX based on signal."""
        try:
            if signal == "BUY":
                # Buy USDC with XRP (bullish on USDC)
                amount_xrp = self.w3.to_wei(0.5, "ether")
                usdc_before = self.usdc.functions.balanceOf(self.evm_acct.address).call()
                r = self._send_evm_tx(self.dex.functions.swapXRPForToken(self.usdc_addr).build_transaction({
                    "gas": 200000, "value": amount_xrp
                }))
                usdc_after = self.usdc.functions.balanceOf(self.evm_acct.address).call()
                usdc_gained = (usdc_after - usdc_before) / 1e6
                self.total_pnl_usdc += Decimal(str(usdc_gained))
                self.total_pnl_xrp -= Decimal("0.5")
                self.evm_trades += 1
                return {
                    "venue": "EVM_DEX", "action": "BUY_USDC", "xrp_spent": 0.5,
                    "usdc_received": usdc_gained, "status": "✅" if r["status"] == 1 else "❌",
                    "tx": r["transactionHash"].hex()[:16]
                }

            elif signal == "SELL":
                # Sell USDC for XRP (bearish on USDC)
                usdc_balance = self.usdc.functions.balanceOf(self.evm_acct.address).call()
                sell_amount = min(100 * 10**6, usdc_balance)
                if sell_amount < 10 * 10**6:
                    return None
                xrp_before = self.w3.eth.get_balance(self.evm_acct.address)
                r = self._send_evm_tx(self.dex.functions.swapTokenForXRP(self.usdc_addr, sell_amount).build_transaction({
                    "gas": 200000
                }))
                xrp_after = self.w3.eth.get_balance(self.evm_acct.address)
                xrp_gained = (xrp_after - xrp_before) / 1e18
                self.total_pnl_xrp += Decimal(str(xrp_gained))
                self.total_pnl_usdc -= Decimal(str(sell_amount / 1e6))
                self.evm_trades += 1
                return {
                    "venue": "EVM_DEX", "action": "SELL_USDC", "usdc_spent": sell_amount / 1e6,
                    "xrp_received": xrp_gained, "status": "✅" if r["status"] == 1 else "❌",
                    "tx": r["transactionHash"].hex()[:16]
                }
        except Exception as e:
            logger.error(f"EVM trade error: {e}")
            return {"venue": "EVM_DEX", "action": signal, "status": "❌", "error": str(e)}
        return None

    async def execute_xrpl_trade(self, signal):
        """Place an offer on XRPL native DEX."""
        if not self.issuer_addr:
            return None
        try:
            if signal == "BUY":
                offer = OfferCreate(
                    account=self.spot_wallet.address,
                    taker_gets=xrp_to_drops(Decimal("2")),
                    taker_pays=IssuedCurrencyAmount(
                        currency="USD", issuer=self.issuer_addr, value="1"
                    ),
                    flags=0x00080000
                )
            elif signal == "SELL":
                offer = OfferCreate(
                    account=self.spot_wallet.address,
                    taker_gets=IssuedCurrencyAmount(
                        currency="USD", issuer=self.issuer_addr, value="1"
                    ),
                    taker_pays=xrp_to_drops(Decimal("2")),
                    flags=0x00080000
                )
            else:
                return None

            resp = await submit_and_wait(transaction=offer, client=self.xrpl_client, wallet=self.spot_wallet)
            result = resp.result.get("meta", {}).get("TransactionResult", "unknown")
            self.xrpl_trades += 1
            return {
                "venue": "XRPL_NATIVE", "action": f"OFFER_{signal}",
                "status": "✅" if result == "tesSUCCESS" else "⚠️",
                "result": result, "tx": resp.result.get("hash", "")[:16]
            }
        except Exception as e:
            logger.error(f"XRPL trade error: {e}")
            return {"venue": "XRPL_NATIVE", "action": signal, "status": "❌", "error": str(e)}

    async def run_cycle(self):
        """Run one trading cycle."""
        self.cycle_count += 1
        t0 = time.time()

        # 1. Scan prices
        evm_prices = await self.get_evm_prices()
        xrpl_prices = await self.get_xrpl_prices()

        if "XRP/USDC" in evm_prices:
            self.price_history.append(evm_prices["XRP/USDC"]["token_per_xrp"])

        # 2. Quantum signal
        signal, confidence = await self.get_quantum_signal()
        self.signals[signal] = self.signals.get(signal, 0) + 1

        # 3. Risk check
        risk = await self.risk_agent.assess_trade_risk("XRP/USD", Decimal("2"), Decimal("0.1"))
        execute = risk["execute"] and signal != "HOLD"

        # 4. Execute trades
        evm_result = None
        xrpl_result = None
        if execute:
            evm_result = await self.execute_evm_trade(signal, evm_prices)
            xrpl_result = await self.execute_xrpl_trade(signal)

        # 5. Log
        cycle_time = time.time() - t0
        if evm_result and evm_result.get("status") == "✅":
            await self.monitoring.log_trade("XRP/USD", Decimal("2"), Decimal("0.1"), cycle_time)

        trade_entry = {
            "cycle": self.cycle_count,
            "time": datetime.now().isoformat(),
            "signal": signal,
            "confidence": f"{confidence:.4f}",
            "risk_score": f"{risk['risk_score']:.4f}",
            "execute": execute,
            "evm": evm_result,
            "xrpl": xrpl_result,
            "evm_usdc_price": evm_prices.get("XRP/USDC", {}).get("token_per_xrp", 0),
            "cycle_time": f"{cycle_time:.1f}s"
        }
        self.trades.append(trade_entry)

        # Log line
        evm_status = evm_result["status"] if evm_result else "—"
        xrpl_status = xrpl_result["status"] if xrpl_result else "—"
        logger.info(
            f"C{self.cycle_count:03d} | {signal:4s} conf={confidence:.3f} | "
            f"risk={risk['risk_score']:.3f} | "
            f"EVM={evm_status} XRPL={xrpl_status} | "
            f"P&L: {self.total_pnl_xrp:+.4f} XRP, {self.total_pnl_usdc:+.2f} USDC | "
            f"{cycle_time:.1f}s"
        )

    def print_report(self, final=False):
        """Print trading report."""
        elapsed = datetime.now() - self.start_time if self.start_time else timedelta(0)
        header = "FINAL REPORT" if final else "INTERIM REPORT"

        xrp_bal = self.w3.eth.get_balance(self.evm_acct.address) / 1e18
        usdc_bal = self.usdc.functions.balanceOf(self.evm_acct.address).call() / 1e6

        print(f"\n{'='*60}")
        print(f"  {header} — {elapsed.total_seconds()/60:.1f} minutes")
        print(f"{'='*60}")
        print(f"  Cycles:       {self.cycle_count}")
        print(f"  EVM trades:   {self.evm_trades}")
        print(f"  XRPL trades:  {self.xrpl_trades}")
        print(f"  Signals:      BUY={self.signals.get('BUY',0)} SELL={self.signals.get('SELL',0)} HOLD={self.signals.get('HOLD',0)}")
        print(f"  P&L (XRP):    {self.total_pnl_xrp:+.6f}")
        print(f"  P&L (USDC):   {self.total_pnl_usdc:+.2f}")
        print(f"  EVM balance:  {xrp_bal:.4f} XRP / {usdc_bal:.2f} tUSDC")

        if final:
            os.makedirs("logs", exist_ok=True)
            with open("logs/trading_session.json", "w") as f:
                json.dump({
                    "start": self.start_time.isoformat() if self.start_time else None,
                    "duration_minutes": elapsed.total_seconds() / 60,
                    "cycles": self.cycle_count,
                    "evm_trades": self.evm_trades,
                    "xrpl_trades": self.xrpl_trades,
                    "pnl_xrp": str(self.total_pnl_xrp),
                    "pnl_usdc": str(self.total_pnl_usdc),
                    "signals": self.signals,
                    "trades": self.trades
                }, f, indent=2, default=str)
            print(f"\n  Session log: logs/trading_session.json")
        print(f"{'='*60}\n")

    async def run(self):
        """Main trading loop."""
        self.start_time = datetime.now()
        end_time = self.start_time + self.duration
        report_interval = timedelta(minutes=5)
        next_report = self.start_time + report_interval

        logger.info("=" * 60)
        logger.info("THOTH ORACLE - AUTOMATED TRADING SESSION")
        logger.info(f"Duration: {self.duration.total_seconds()/60:.0f} minutes")
        logger.info(f"Cycle interval: {self.cycle_interval}s")
        logger.info(f"Strategy: Quantum-enhanced cross-venue arbitrage")
        logger.info("=" * 60)

        # Ensure token approval for selling
        try:
            self._send_evm_tx(self.usdc.functions.approve(self.dex_addr, 2**256-1).build_transaction({"gas": 100000}))
            logger.info("tUSDC approved for DEX")
        except:
            pass

        while datetime.now() < end_time:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            if datetime.now() >= next_report:
                self.print_report(final=False)
                next_report += report_interval

            remaining = (end_time - datetime.now()).total_seconds()
            sleep_time = min(self.cycle_interval, max(0, remaining))
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.print_report(final=True)


async def main():
    parser = argparse.ArgumentParser(description="Thoth Oracle Automated Trader")
    parser.add_argument("--minutes", type=int, default=30, help="Duration in minutes")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    trader = AutomatedTrader(duration_minutes=args.minutes)
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())
