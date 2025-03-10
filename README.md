# Thoth Oracle System

A sophisticated arbitrage and trading system for the XRPL DEX, featuring flash loans, automated market making, and risk management.

## Features

### Core Components

1. **Flash Loan Agent**
   - Execute flash loans on XRPL
   - Manage loan lifecycle and repayment
   - Calculate optimal loan sizes and profits

2. **XRPL AMM Agent**
   - Monitor liquidity pools
   - Calculate exchange rates
   - Find arbitrage paths
   - Execute optimal trades

3. **Risk Management Agent**
   - Assess trade risks
   - Track positions and P&L
   - Calculate risk metrics
   - Monitor market conditions

4. **Monitoring Agent**
   - Track system health
   - Log performance metrics
   - Monitor errors and issues
   - Export system metrics

### Key Features

- Real-time DEX monitoring
- Direct and triangular arbitrage detection
- Flash loan integration
- Risk assessment and management
- Performance tracking and reporting
- Comprehensive error handling
- Extensive logging

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Hobie1Kenobi/Thoth-Oracle.git
cd Thoth-Oracle
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -e .
```

## Configuration

1. Set up your XRPL testnet wallet:
   - Replace `TEST_WALLET_SEED` in `examples/live_arbitrage_test.py`
   - Ensure your wallet has sufficient XRP for testing

2. Configure trading pairs:
   - Edit `TRADING_PAIRS` in `examples/live_arbitrage_test.py`
   - Add or remove pairs based on your strategy

3. Adjust risk parameters:
   - Modify thresholds in `agents/risk_management_agent/risk_management_agent.py`
   - Set position limits and profit targets

## Usage

### Live Testing

Run the live arbitrage test script:
```bash
python examples/live_arbitrage_test.py
```

This will:
1. Initialize all agents
2. Monitor specified trading pairs
3. Detect arbitrage opportunities
4. Execute trades when profitable
5. Log performance and results

### Monitoring

The system provides extensive monitoring through:
- Real-time logging
- Performance metrics
- Health checks
- Error tracking

Logs are stored in the `logs` directory.

## Architecture

### Agent System

The system uses a multi-agent architecture:
1. Each agent handles specific functionality
2. Agents communicate asynchronously
3. Central coordination through the ArbitrageTrader

### Risk Management

Multiple layers of risk control:
1. Pre-trade risk assessment
2. Position monitoring
3. P&L tracking
4. System health checks

### Performance Optimization

- Asynchronous operations
- Efficient path finding
- Smart order routing
- Optimal trade sizing

## Development

### Testing

Run the test suite:
```bash
pytest tests/
```

### Adding New Features

1. Create new agent in `agents/` directory
2. Update main trading loop in `examples/live_arbitrage_test.py`
3. Add tests in `tests/` directory

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## Support

Open an issue for:
- Bug reports
- Feature requests
- Documentation improvements
