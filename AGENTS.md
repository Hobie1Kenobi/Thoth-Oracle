# Agents

## Cursor Cloud specific instructions

### Project overview

Thoth Oracle is a Python-based cryptocurrency arbitrage and trading system for the XRPL DEX. See `README.md` for full feature list and architecture.

### Virtual environment

A `.venv` virtual environment exists at the project root. Always activate it before running commands:

```
source /workspace/.venv/bin/activate
```

The checked-in `venv/` directory (Windows-built) is **not usable** on Linux — ignore it.

### Dependency version constraints

- **Qiskit**: Must use `qiskit==0.46.3` (not 1.x or 2.x). The codebase uses deprecated APIs (`from qiskit import execute, Aer`) that were removed in Qiskit 1.0+. If `qiskit` is accidentally upgraded, clean reinstall is required: uninstall qiskit/qiskit-terra/qiskit-aer, delete residual `site-packages/qiskit/` directory, then reinstall `qiskit==0.46.3 qiskit-aer==0.13.3`.
- **pytest**: Must use `pytest<9` to avoid async fixture breakage with `pytest-asyncio`.
- **xrpl-py**: Version 2.4.0 is installed. One test file (`test_security_and_robustness.py`) imports `XRPLRequestFailureException` which does not exist — this is a pre-existing repo issue.
- **dashboard/requirements.txt**: Pins older versions that conflict with root `requirements.txt`. Install root requirements last to maintain correct versions for tests.

### Running tests

```
source /workspace/.venv/bin/activate
python -m pytest tests/ --timeout=60 -o "addopts=--verbose --cov=. --cov-report=term-missing --cov-branch --durations=5" --ignore=tests/test_security_and_robustness.py
```

- Override `addopts` to drop `--strict-markers` (several test files use unregistered markers like `comprehensive`, `core`, `monitoring`, `benchmark`, etc.).
- Ignore `test_security_and_robustness.py` (broken import).
- Many tests have pre-existing failures (async fixture issues, assertion mismatches). The passing subset (`test_init.py`, `test_monitoring.py`, and a few quantum tests) confirms the environment is functional.

### Running the Streamlit dashboard

```
source /workspace/.venv/bin/activate
streamlit run dashboard.py --server.port 8501 --server.headless true --server.address 0.0.0.0
```

The dashboard reads from `logs/arbitrage_opportunities.log`. Create the `logs/` directory if it doesn't exist.

### Linting

No linter is configured in the repo. `ruff` is installed in the venv and can be run with:

```
ruff check --select E,F --ignore E501 --exclude venv,.venv
```

### Network configuration

The system is configured for **XRPL Testnet** at `https://s.altnet.rippletest.net:51234`.

### Wallet setup

Three test wallets exist, all funded on XRPL testnet:

| Wallet | Seed source | Address | Balance |
|--------|------------|---------|---------|
| Spot Trader | `config/test_wallets.py` | `rG4mzN4LdjQUXgAvLbB2DQxD5aAq6jtZGx` | 100 XRP |
| Flash Loan | `config/test_wallets.py` | `rL721eQQexPb9EREChEjnoGCoetP7GzzKV` | 100 XRP |
| Live Arb Test | `examples/live_arbitrage_test.py` (hardcoded) | `rLJmghXLb3Wvrc4oVqzXcNNPZ7WPjpvyJY` | ~1.2 XRP |

To create fresh funded wallets: `python scripts/create_test_wallets.py`

### Agent architecture and handoff flow

```
                    ┌─────────────────────────┐
                    │   ArbitrageTrader        │  (examples/live_arbitrage_test.py)
                    │   - orchestrates all     │
                    └──────┬──────┬───────┬────┘
                           │      │       │
              ┌────────────┘      │       └───────────┐
              ▼                   ▼                    ▼
    ┌──────────────────┐ ┌────────────────┐  ┌────────────────────┐
    │  XRPLAMMAgent    │ │ FlashLoanAgent │  │ RiskManagementAgent│
    │  - order books   │ │ - loan avail   │  │ - assess risk      │
    │  - path finding  │ │ - fees         │  │ - position tracking│
    │  - execute trade │ │ - execute loan │  │ - daily P&L        │
    │  - pool rates    │ └────────────────┘  └────────────────────┘
    └──────────────────┘
              │                                        │
              ▼                                        ▼
    ┌──────────────────┐                    ┌────────────────────┐
    │ MonitoringAgent  │                    │ SpotTradingAgent   │
    │ - trade logging  │                    │ - risk scoring     │
    │ - health checks  │                    │ - opportunity eval │
    │ - metrics export │                    └────────────────────┘
    └──────────────────┘
              │
              ▼
    ┌──────────────────┐
    │ FlashLoanTrader  │  (reads logs/arbitrage_opportunities.log)
    │ - orchestrates   │
    │   flash loan +   │
    │   AMM trade      │
    └──────────────────┘
```

**Quantum agents** (separate flow, requires PennyLane + D-Wave):
- `QuantumArbitrageAgent` → uses `HybridQuantumPredictor` (PennyLane) + `QuantumPathOptimizer` (D-Wave)
- `QuantumPredictor` / `QuantumOptimizer` (Qiskit stubs in `quantum_tools/`)

**Stub agents** (not yet implemented): `BridgeAgent`, `PredictionAgent`

### Trading strategies

1. **Direct arbitrage**: Compare XRP/currency rates across issuers (Bitstamp vs Gatehub); buy low, sell high
2. **Triangular arbitrage**: Multi-leg paths (e.g. XRP→USD→EUR→XRP) with slippage tolerance
3. **Flash loan arbitrage**: Borrow → trade → repay in single flow via `FlashLoanTradingAgent`
4. **Quantum-enhanced**: Price prediction via variational circuits; path optimization via QAOA/D-Wave annealing

### Running the live arbitrage scanner

```
source /workspace/.venv/bin/activate
python examples/live_arbitrage_test.py
```

This connects to XRPL testnet, scans order books every 1s, and detects direct + triangular arbitrage.

### Key caveats

- `main.py` is a placeholder — use `examples/live_arbitrage_test.py` for the actual orchestration flow.
- All agent methods are **async** — must be called with `await` inside `asyncio.run()`.
- `SpotTradingAgent` has a pre-existing import bug: uses `xrpl.utils.get_issuer_address` (doesn't exist); should use `config.exchange_issuers.get_issuer_address`.
- `pennylane-qiskit` forces qiskit 2.x which breaks the codebase. Install `pennylane` without `pennylane-qiskit` to keep qiskit 0.46.3 working.
- D-Wave optimizer requires `DWAVE_API_TOKEN` env var for real quantum annealing. Use `dimod.SimulatedAnnealingSampler()` as a local substitute.
- `examples/quantum_prediction.py` uses `circuit.u3()` which was removed in qiskit 0.46.x. Patch with `QuantumCircuit.u3 = QuantumCircuit.u` before importing.
- IBM Quantum cloud requires both a CRN (instance identifier) **and** an API token. Set `IBM_QUANTUM_CRN` and `IBMQ_API_TOKEN` in `.env`. Note: `qiskit-ibm-runtime` requires qiskit >= 1.0 which conflicts with this codebase; cloud backends are not usable with qiskit 0.46.3 without significant refactoring.
- The Dash dashboard (`dashboard/run_dashboard.py`) requires a live XRPL testnet connection.
- No Docker, Makefile, or devcontainer configs exist — setup is purely pip-based.
