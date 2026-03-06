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

### Key caveats

- `main.py` requires XRPL client/wallet parameters — agents cannot be instantiated without them. Use `JsonRpcClient('https://s.altnet.rippletest.net:51234')` and `Wallet.create()` for testnet usage.
- The Dash dashboard (`dashboard/run_dashboard.py`) requires a live XRPL testnet connection.
- No Docker, Makefile, or devcontainer configs exist — setup is purely pip-based.
