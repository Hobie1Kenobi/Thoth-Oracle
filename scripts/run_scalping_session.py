#!/usr/bin/env python3
"""
Thoth Oracle — Quantum Scalping Bot
High-frequency spot scalping with dynamic position sizing and compounding.

Strategy:
  - Scalp XRP/USDC on EVM DEX with 15-second cycles
  - Quantum predictor determines direction + confidence
  - Position size scales with balance (2-8% based on confidence)
  - Profits compound immediately (geometric growth)
  - Risk: max 5% drawdown, cool-down after 3 consecutive losses

Usage:
    python scripts/run_scalping_session.py              # 1 hour default
    python scripts/run_scalping_session.py --minutes 30 # custom
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
from examples.quantum_prediction import QuantumPricePredictor
from qiskit_aer import AerSimulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scalping_session.log")
    ]
)
logger = logging.getLogger("Scalper")

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


class QuantumScalper:
    def __init__(self, duration_minutes=60):
        self.duration = timedelta(minutes=duration_minutes)
        self.cycle_interval = 15
        self.start_time = None
        self.cycle_count = 0

        with open("config/crosschain_config.json") as f:
            cc = json.load(f)
        with open("config/evm_dex_config.json") as f:
            dex_cfg = json.load(f)

        self.w3 = Web3(Web3.HTTPProvider(cc["xrpl_evm"]["rpc"], request_kwargs={"timeout": 15}))
        self.acct = Account.from_key(cc["wallet"]["private_key"])
        self.chain_id = cc["xrpl_evm"]["chain_id"]
        self.dex_addr = dex_cfg["dex"]["address"]
        self.usdc_addr = dex_cfg["tokens"]["tUSDC"]["address"]

        self.dex = self.w3.eth.contract(address=self.dex_addr, abi=SWAP_ABI)
        self.usdc = self.w3.eth.contract(address=self.usdc_addr, abi=ERC20_ABI)

        self.predictor = QuantumPricePredictor(n_qubits=4, n_layers=2, backend=AerSimulator())
        self.price_history = []

        # Tracking
        self.initial_xrp = 0
        self.initial_usdc = 0
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.consecutive_losses = 0
        self.max_drawdown_pct = 5.0
        self.cooldown_until = None
        self.peak_value = 0

    def _send_tx(self, tx_data):
        nonce = self.w3.eth.get_transaction_count(self.acct.address)
        tx_data["nonce"] = nonce
        tx_data["from"] = self.acct.address
        tx_data["chainId"] = self.chain_id
        for k in ["gasPrice", "maxFeePerGas", "maxPriorityFeePerGas"]:
            tx_data.pop(k, None)
        gp = self.w3.eth.gas_price
        tx_data["maxFeePerGas"] = gp * 2
        tx_data["maxPriorityFeePerGas"] = gp
        signed = self.acct.sign_transaction(tx_data)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

    def get_balances(self):
        xrp = self.w3.eth.get_balance(self.acct.address) / 1e18
        usdc = self.usdc.functions.balanceOf(self.acct.address).call() / 1e6
        return xrp, usdc

    def get_pool_price(self):
        try:
            p = self.dex.functions.getPrice(self.usdc_addr).call()
            return p[0] / 1e18, p[1] / 1e18
        except:
            return 0, 0

    def get_total_value_xrp(self, xrp, usdc):
        _, xrp_per_usdc = self.get_pool_price()
        return xrp + (usdc * xrp_per_usdc) if xrp_per_usdc > 0 else xrp

    def get_position_size(self, balance_xrp, confidence):
        """Dynamic position sizing based on confidence."""
        if confidence > 0.75:
            pct = 0.08
        elif confidence > 0.65:
            pct = 0.05
        elif confidence > 0.55:
            pct = 0.02
        else:
            pct = 0
        return balance_xrp * pct

    async def get_signal(self):
        if len(self.price_history) < 10:
            usdc_per_xrp, _ = self.get_pool_price()
            if usdc_per_xrp > 0:
                for _ in range(20):
                    noise = usdc_per_xrp * (1 + np.random.uniform(-0.01, 0.01))
                    self.price_history.append(noise)

        try:
            await self.predictor.train(self.price_history[-20:])
            pred = await self.predictor.predict_price(window_size=3)
            if pred is not None:
                if pred > 0.55:
                    return "BUY_USDC", pred
                elif pred < 0.45:
                    return "SELL_USDC", 1 - pred
                else:
                    return "HOLD", abs(pred - 0.5) * 2
        except:
            pass
        return "HOLD", 0.0

    def buy_usdc(self, xrp_amount):
        """Swap XRP → tUSDC on DEX."""
        wei = self.w3.to_wei(xrp_amount, "ether")
        usdc_before = self.usdc.functions.balanceOf(self.acct.address).call()
        r = self._send_tx(self.dex.functions.swapXRPForToken(self.usdc_addr).build_transaction({
            "gas": 200000, "value": wei
        }))
        usdc_after = self.usdc.functions.balanceOf(self.acct.address).call()
        usdc_got = (usdc_after - usdc_before) / 1e6
        return r["status"] == 1, usdc_got

    def sell_usdc(self, usdc_amount):
        """Swap tUSDC → XRP on DEX."""
        usdc_wei = int(usdc_amount * 1e6)
        xrp_before = self.w3.eth.get_balance(self.acct.address)
        r = self._send_tx(self.dex.functions.swapTokenForXRP(self.usdc_addr, usdc_wei).build_transaction({
            "gas": 200000
        }))
        xrp_after = self.w3.eth.get_balance(self.acct.address)
        xrp_got = (xrp_after - xrp_before) / 1e18
        return r["status"] == 1, xrp_got

    async def run_cycle(self):
        self.cycle_count += 1
        t0 = time.time()

        xrp_bal, usdc_bal = self.get_balances()
        total_value = self.get_total_value_xrp(xrp_bal, usdc_bal)
        usdc_per_xrp, _ = self.get_pool_price()

        if usdc_per_xrp > 0:
            self.price_history.append(usdc_per_xrp)

        self.peak_value = max(self.peak_value, total_value)
        drawdown = (self.peak_value - total_value) / self.peak_value * 100 if self.peak_value > 0 else 0

        if drawdown >= self.max_drawdown_pct:
            logger.warning(f"C{self.cycle_count:04d} | STOP: drawdown {drawdown:.1f}% >= {self.max_drawdown_pct}%")
            return "STOP"

        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).seconds
            logger.info(f"C{self.cycle_count:04d} | COOLDOWN {remaining}s | XRP={xrp_bal:.4f} USDC={usdc_bal:.2f} val={total_value:.4f}")
            return "COOLDOWN"

        signal, confidence = await self.get_signal()

        trade_result = None
        pnl = 0

        if signal == "BUY_USDC" and confidence > 0.55:
            size = self.get_position_size(xrp_bal, confidence)
            if size >= 0.1 and xrp_bal >= size + 0.5:
                ok, usdc_got = self.buy_usdc(size)
                expected_usdc = size * usdc_per_xrp if usdc_per_xrp > 0 else 0
                pnl = usdc_got - expected_usdc * 0.997
                trade_result = {"action": "BUY_USDC", "xrp_in": size, "usdc_out": usdc_got, "ok": ok}

        elif signal == "SELL_USDC" and confidence > 0.55:
            usdc_size = usdc_bal * (0.08 if confidence > 0.75 else 0.05 if confidence > 0.65 else 0.02)
            if usdc_size >= 10 and usdc_bal >= usdc_size:
                ok, xrp_got = self.sell_usdc(usdc_size)
                expected_xrp = usdc_size / usdc_per_xrp if usdc_per_xrp > 0 else 0
                pnl = xrp_got - expected_xrp * 0.997
                trade_result = {"action": "SELL_USDC", "usdc_in": usdc_size, "xrp_out": xrp_got, "ok": ok}

        if trade_result:
            if pnl >= 0:
                self.wins += 1
                self.consecutive_losses = 0
            else:
                self.losses += 1
                self.consecutive_losses += 1
                if self.consecutive_losses >= 3:
                    self.cooldown_until = datetime.now() + timedelta(seconds=60)
                    logger.warning(f"  3 consecutive losses → 60s cooldown")

        new_xrp, new_usdc = self.get_balances()
        new_value = self.get_total_value_xrp(new_xrp, new_usdc)
        gain_pct = (new_value - self.initial_xrp) / self.initial_xrp * 100 if self.initial_xrp > 0 else 0
        cycle_time = time.time() - t0

        trade_info = ""
        if trade_result:
            a = trade_result["action"]
            if "xrp_in" in trade_result:
                trade_info = f"{a} {trade_result['xrp_in']:.2f} XRP → {trade_result['usdc_out']:.2f} USDC"
            else:
                trade_info = f"{a} {trade_result['usdc_in']:.2f} USDC → {trade_result['xrp_out']:.4f} XRP"
        else:
            trade_info = f"{signal} (conf={confidence:.3f})"

        win_rate = self.wins / max(self.wins + self.losses, 1) * 100

        logger.info(
            f"C{self.cycle_count:04d} | "
            f"XRP={new_xrp:.4f} USDC={new_usdc:.2f} | "
            f"val={new_value:.4f} ({gain_pct:+.2f}%) | "
            f"W/L={self.wins}/{self.losses} ({win_rate:.0f}%) | "
            f"{trade_info} | "
            f"{cycle_time:.1f}s"
        )

        self.trades.append({
            "cycle": self.cycle_count,
            "time": datetime.now().isoformat(),
            "signal": signal,
            "confidence": confidence,
            "xrp": new_xrp,
            "usdc": new_usdc,
            "total_value_xrp": new_value,
            "gain_pct": gain_pct,
            "trade": trade_result,
            "cycle_time": cycle_time,
        })

        return signal

    def print_report(self):
        elapsed = datetime.now() - self.start_time if self.start_time else timedelta(0)
        xrp, usdc = self.get_balances()
        total = self.get_total_value_xrp(xrp, usdc)
        gain = total - self.initial_xrp
        gain_pct = gain / self.initial_xrp * 100 if self.initial_xrp > 0 else 0
        win_rate = self.wins / max(self.wins + self.losses, 1) * 100

        print(f"\n{'='*70}")
        print(f"  SCALPING SESSION REPORT — {elapsed.total_seconds()/60:.1f} minutes")
        print(f"{'='*70}")
        print(f"  Starting balance:  {self.initial_xrp:.4f} XRP equiv")
        print(f"  Current balance:   XRP={xrp:.4f}  USDC={usdc:.2f}")
        print(f"  Total value (XRP): {total:.4f}")
        print(f"  P&L:               {gain:+.4f} XRP ({gain_pct:+.2f}%)")
        print(f"  Peak value:        {self.peak_value:.4f} XRP")
        print(f"  Cycles:            {self.cycle_count}")
        print(f"  Trades executed:   {self.wins + self.losses}")
        print(f"  Win rate:          {win_rate:.1f}% ({self.wins}W / {self.losses}L)")
        print(f"  Avg cycle time:    {sum(t['cycle_time'] for t in self.trades) / max(len(self.trades),1):.1f}s")
        print(f"{'='*70}\n")

        os.makedirs("logs", exist_ok=True)
        with open("logs/scalping_session.json", "w") as f:
            json.dump({
                "start": self.start_time.isoformat() if self.start_time else None,
                "duration_minutes": elapsed.total_seconds() / 60,
                "initial_xrp": self.initial_xrp,
                "final_xrp": xrp,
                "final_usdc": usdc,
                "total_value_xrp": total,
                "gain_xrp": gain,
                "gain_pct": gain_pct,
                "peak_value": self.peak_value,
                "cycles": self.cycle_count,
                "wins": self.wins,
                "losses": self.losses,
                "win_rate": win_rate,
                "trades": self.trades,
            }, f, indent=2, default=str)

    async def run(self):
        self.start_time = datetime.now()
        end_time = self.start_time + self.duration

        xrp, usdc = self.get_balances()
        self.initial_xrp = self.get_total_value_xrp(xrp, usdc)
        self.peak_value = self.initial_xrp

        logger.info("=" * 70)
        logger.info("THOTH ORACLE — QUANTUM SCALPING SESSION")
        logger.info(f"Duration: {self.duration.total_seconds()/60:.0f} minutes | Interval: {self.cycle_interval}s")
        logger.info(f"Starting: {xrp:.4f} XRP + {usdc:.2f} USDC = {self.initial_xrp:.4f} XRP equiv")
        logger.info(f"Strategy: Quantum-guided scalping, 2-8% position sizing")
        logger.info(f"Risk: {self.max_drawdown_pct}% max drawdown, 3-loss cooldown")
        logger.info("=" * 70)

        # Ensure USDC approved
        try:
            self._send_tx(self.usdc.functions.approve(self.dex_addr, 2**256-1).build_transaction({"gas": 100000}))
        except:
            pass

        report_interval = timedelta(minutes=10)
        next_report = self.start_time + report_interval

        while datetime.now() < end_time:
            try:
                result = await self.run_cycle()
                if result == "STOP":
                    logger.warning("Session stopped: max drawdown hit")
                    break
            except Exception as e:
                logger.error(f"Cycle error: {e}")

            if datetime.now() >= next_report:
                self.print_report()
                next_report += report_interval

            remaining = (end_time - datetime.now()).total_seconds()
            sleep_time = min(self.cycle_interval, max(0, remaining))
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.print_report()


async def main():
    parser = argparse.ArgumentParser(description="Quantum Scalping Bot")
    parser.add_argument("--minutes", type=int, default=60, help="Session duration")
    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    scalper = QuantumScalper(duration_minutes=args.minutes)
    await scalper.run()


if __name__ == "__main__":
    asyncio.run(main())
