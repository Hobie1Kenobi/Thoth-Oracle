"""
Thoth Oracle — Pro Dashboard
Real-time multi-chain trading intelligence platform.
Showcases agents, quantum predictions, price feeds, and autotrading.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import os
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Thoth Oracle",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Theme ────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    .stApp { background: #0a0a0f; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    .block-container { padding-top: 1rem; }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d0d15 0%, #111120 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }
    
    .glass-card {
        background: rgba(17, 17, 32, 0.8);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 16px;
        padding: 20px;
        margin: 8px 0;
        backdrop-filter: blur(20px);
    }
    
    .metric-value { font-size: 1.8em; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
    .metric-label { font-size: 0.75em; text-transform: uppercase; letter-spacing: 1.5px; color: #8888aa; margin-top: 4px; }
    
    .status-online { color: #22c55e; }
    .status-offline { color: #ef4444; }
    .profit { color: #22c55e; }
    .loss { color: #ef4444; }
    .neutral { color: #6366f1; }
    
    .agent-card {
        background: rgba(17, 17, 32, 0.6);
        border: 1px solid rgba(99, 102, 241, 0.1);
        border-radius: 12px;
        padding: 16px;
        margin: 6px 0;
    }
    
    .agent-name { font-weight: 600; font-size: 0.95em; }
    .agent-status { font-size: 0.8em; }
    
    h1, h2, h3 { color: #e0e0f0 !important; }
    
    .header-bar {
        background: linear-gradient(90deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1));
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 16px 24px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .signal-buy { background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 8px; padding: 8px 16px; color: #22c55e; font-weight: 600; }
    .signal-sell { background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 8px 16px; color: #ef4444; font-weight: 600; }
    .signal-hold { background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; padding: 8px 16px; color: #6366f1; font-weight: 600; }
    
    div[data-testid="stMetric"] { background: rgba(17,17,32,0.6); border: 1px solid rgba(99,102,241,0.1); border-radius: 12px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Data Loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def load_trading_session():
    try:
        with open("logs/trading_session.json") as f:
            return json.load(f)
    except:
        return None

@st.cache_data(ttl=5)
def load_opportunities():
    opps = []
    try:
        with open("logs/arbitrage_opportunities.log") as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    d["timestamp"] = datetime.fromisoformat(d["timestamp"])
                    opps.append(d)
                except:
                    continue
    except:
        pass
    return opps

@st.cache_data(ttl=10)
def load_evm_config():
    try:
        with open("config/evm_dex_config.json") as f:
            return json.load(f)
    except:
        return None

@st.cache_data(ttl=10)
def load_crosschain_config():
    try:
        with open("config/crosschain_config.json") as f:
            return json.load(f)
    except:
        return None

def load_issuer_config():
    try:
        with open("config/testnet_issuer.json") as f:
            return json.load(f)
    except:
        return None


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚛️ Thoth Oracle")
    st.markdown("*Quantum-Enhanced XRPL Trading*")
    st.markdown("---")
    
    st.markdown("### Networks")
    st.markdown('<span class="status-online">● </span> XRPL Testnet', unsafe_allow_html=True)
    st.markdown('<span class="status-online">● </span> XRPL EVM (1449000)', unsafe_allow_html=True)
    st.markdown('<span class="status-online">● </span> Ethereum Sepolia', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Agents")
    agents = [
        ("Spot Trader", "rG4mzN4L..."),
        ("Flash Loan", "rL721eQQ..."),
        ("Token Issuer", "rLAPnYJV..."),
        ("Risk Manager", "Active"),
        ("Monitoring", "Active"),
        ("Quantum Predictor", "IBM ibm_fez"),
    ]
    for name, status in agents:
        st.markdown(f"""<div class="agent-card">
            <div class="agent-name">{name}</div>
            <div class="agent-status status-online">● {status}</div>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"*Updated: {datetime.now().strftime('%H:%M:%S')}*")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── Header ───────────────────────────────────────────────────────────────────

st.markdown("""<div class="header-bar">
    <div>
        <span style="font-size: 1.5em; font-weight: 700;">⚛️ Thoth Oracle</span>
        <span style="margin-left: 16px; color: #8888aa;">Quantum-Enhanced Multi-Chain Trading Intelligence</span>
    </div>
    <div style="font-family: 'JetBrains Mono'; color: #6366f1; font-size: 0.9em;">
        XRPL • EVM • IBM Quantum
    </div>
</div>""", unsafe_allow_html=True)


# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_overview, tab_trading, tab_quantum, tab_crosschain, tab_agents = st.tabs([
    "📊 Overview", "💹 Trading", "🔮 Quantum", "🌐 Cross-Chain", "🤖 Agents"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

with tab_overview:
    session = load_trading_session()
    
    # Top metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    if session:
        trades = session.get("trades", [])
        c1.metric("Trades", session.get("cycles", 0))
        c2.metric("EVM Trades", session.get("evm_trades", 0))
        c3.metric("XRPL Trades", session.get("xrpl_trades", 0))
        
        pnl_xrp = float(session.get("pnl_xrp", 0))
        pnl_usdc = float(session.get("pnl_usdc", 0))
        c4.metric("P&L (XRP)", f"{pnl_xrp:+.4f}", delta=f"{pnl_xrp:+.4f}")
        c5.metric("P&L (USDC)", f"{pnl_usdc:+.2f}", delta=f"{pnl_usdc:+.2f}")
        
        signals = session.get("signals", {})
        buy_pct = signals.get("BUY", 0) / max(sum(signals.values()), 1) * 100
        c6.metric("BUY Ratio", f"{buy_pct:.0f}%")
    else:
        c1.metric("Trades", "—")
        c2.metric("EVM", "—")
        c3.metric("XRPL", "—")
        c4.metric("P&L (XRP)", "—")
        c5.metric("P&L (USDC)", "—")
        c6.metric("Signal", "—")
    
    st.markdown("---")
    
    # Charts
    if session and session.get("trades"):
        trades = session["trades"]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # P&L over time
            df_trades = pd.DataFrame(trades)
            if "evm" in df_trades.columns:
                evm_pnl = []
                cum = 0
                for _, row in df_trades.iterrows():
                    evm = row.get("evm")
                    if evm and isinstance(evm, dict):
                        if "usdc_received" in evm:
                            cum += float(evm["usdc_received"])
                        elif "xrp_received" in evm:
                            cum += float(evm["xrp_received"])
                    evm_pnl.append(cum)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    y=evm_pnl, mode='lines+markers',
                    name='Cumulative P&L',
                    line=dict(color='#6366f1', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(99, 102, 241, 0.1)',
                ))
                fig.update_layout(
                    title="Trading P&L Timeline",
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    xaxis_title="Cycle",
                    yaxis_title="Cumulative P&L",
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Signal distribution
            if session.get("signals"):
                sigs = session["signals"]
                fig = go.Figure(data=[go.Pie(
                    labels=list(sigs.keys()),
                    values=list(sigs.values()),
                    hole=0.6,
                    marker_colors=['#22c55e', '#ef4444', '#6366f1'],
                )])
                fig.update_layout(
                    title="Signal Distribution",
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    height=350,
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)

    # Opportunities
    opps = load_opportunities()
    if opps:
        st.markdown("### Recent Arbitrage Opportunities")
        recent = sorted(opps, key=lambda x: x["timestamp"], reverse=True)[:15]
        rows = []
        for o in recent:
            d = o.get("details", o)
            rows.append({
                "Time": o["timestamp"].strftime("%H:%M:%S"),
                "Type": o.get("type", "direct").upper(),
                "Pair": d.get("pair", "—"),
                "Profit %": f"{float(d.get('profit_percentage', 0)):.2f}%",
                "Buy": d.get("buy_exchange", "—"),
                "Sell": d.get("sell_exchange", "—"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: TRADING
# ══════════════════════════════════════════════════════════════════════════════

with tab_trading:
    session = load_trading_session()
    
    if session and session.get("trades"):
        trades = session["trades"]
        
        st.markdown("### Live Trade Feed")
        
        # Trade log table
        rows = []
        for t in reversed(trades[-30:]):
            evm = t.get("evm") or {}
            xrpl = t.get("xrpl") or {}
            signal = t.get("signal", "—")
            signal_class = "signal-buy" if signal == "BUY" else "signal-sell" if signal == "SELL" else "signal-hold"
            
            rows.append({
                "Cycle": t.get("cycle", 0),
                "Signal": signal,
                "Confidence": t.get("confidence", "—"),
                "Risk": t.get("risk_score", "—"),
                "EVM": evm.get("status", "—"),
                "XRPL": xrpl.get("status", "—"),
                "Action": evm.get("action", "—"),
                "Time": t.get("cycle_time", "—"),
            })
        
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)
        
        # Trade confidence histogram
        confidences = [float(t.get("confidence", 0.5)) for t in trades if t.get("confidence")]
        if confidences:
            fig = go.Figure(data=[go.Histogram(
                x=confidences, nbinsx=20,
                marker_color='#6366f1',
            )])
            fig.update_layout(
                title="Quantum Prediction Confidence Distribution",
                xaxis_title="Confidence",
                yaxis_title="Count",
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trading session data. Run `python scripts/run_automated_trading.py` to generate data.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: QUANTUM
# ══════════════════════════════════════════════════════════════════════════════

with tab_quantum:
    st.markdown("### IBM Quantum Hardware")
    
    c1, c2, c3 = st.columns(3)
    c1.markdown("""<div class="glass-card">
        <div class="metric-value neutral">ibm_fez</div>
        <div class="metric-label">156 Qubits • Heron R2</div>
    </div>""", unsafe_allow_html=True)
    c2.markdown("""<div class="glass-card">
        <div class="metric-value neutral">ibm_marrakesh</div>
        <div class="metric-label">156 Qubits • Heron R2</div>
    </div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="glass-card">
        <div class="metric-value neutral">ibm_torino</div>
        <div class="metric-label">133 Qubits • Heron R1</div>
    </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Quantum Strategies")
    
    strategies = [
        ("Variational Price Predictor", "4 qubits, 2 layers, 24 parameters", "Trains on price history, outputs BUY/SELL/HOLD signal with confidence score"),
        ("Grover Arbitrage Detector", "3 qubits, Grover diffusion", "Searches exchange rate matrices for profitable arbitrage paths"),
        ("QFT Value-at-Risk", "8 qubits, Quantum Fourier Transform", "Portfolio risk estimation using quantum amplitude encoding"),
        ("Quantum Hedging", "6 qubits, entangled selection", "Optimal hedging instrument selection under cost constraints"),
        ("Portfolio Optimization", "D-Wave simulated annealing", "QUBO formulation for optimal asset allocation"),
    ]
    
    for name, circuit, desc in strategies:
        st.markdown(f"""<div class="agent-card">
            <div class="agent-name">🔮 {name}</div>
            <div style="font-size: 0.8em; color: #6366f1; font-family: 'JetBrains Mono';">{circuit}</div>
            <div style="font-size: 0.85em; color: #aaa; margin-top: 4px;">{desc}</div>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Hardware Verification")
    st.markdown("""
    | Test | Backend | Result |
    |------|---------|--------|
    | Bell State Entanglement | ibm_fez | **94.5% fidelity** |
    | Price Prediction | ibm_fez | pred=0.657 → **BUY** (26s) |
    | Full Trading Pipeline | ibm_fez | Quantum signal → Risk → Execute → Monitor |
    """)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: CROSS-CHAIN
# ══════════════════════════════════════════════════════════════════════════════

with tab_crosschain:
    st.markdown("### Multi-Chain Architecture")
    
    cc = load_crosschain_config()
    evm = load_evm_config()
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""<div class="glass-card">
            <div class="metric-value" style="color: #22c55e;">XRPL Native</div>
            <div class="metric-label">Testnet • 6 Issuers • 28 Trust Lines</div>
            <div style="margin-top: 8px; font-size: 0.85em; color: #aaa;">
                Bitstamp, Gatehub, GateHub_Five, Ripple, RippleGateway, Bitso<br>
                USD, EUR, BTC, JPY, GBP, AUD, CHF, CNY, MXN
            </div>
        </div>""", unsafe_allow_html=True)
    
    with c2:
        evm_addr = evm.get("dex", {}).get("address", "—") if evm else "—"
        st.markdown(f"""<div class="glass-card">
            <div class="metric-value" style="color: #a855f7;">XRPL EVM</div>
            <div class="metric-label">Chain 1449000 • SimpleSwap DEX</div>
            <div style="margin-top: 8px; font-size: 0.85em; color: #aaa;">
                DEX: {evm_addr[:18]}...<br>
                Pools: XRP/tUSDC, XRP/tWBTC<br>
                3 contracts deployed
            </div>
        </div>""", unsafe_allow_html=True)
    
    with c3:
        st.markdown("""<div class="glass-card">
            <div class="metric-value" style="color: #3b82f6;">Sepolia</div>
            <div class="metric-label">Chain 11155111 • Uniswap V3</div>
            <div style="margin-top: 8px; font-size: 0.85em; color: #aaa;">
                4 WETH/USDC pools scanned<br>
                Fee tiers: 0.01%, 0.05%, 0.3%, 1%<br>
                Axelar bridge configured
            </div>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Bridge Infrastructure")
    bridges = [
        ("Axelar ITS", "XRPL ↔ XRPL EVM ↔ Sepolia", "0xB5FB4BE0..."),
        ("SquidRouter", "XRPL ↔ XRPL EVM", "app.squidrouter.com"),
        ("IBC", "XRPL EVM ↔ Cosmos Chains", "Native Cosmos SDK"),
        ("Wormhole", "XRPL EVM ↔ Multi-chain", "In Progress"),
    ]
    for name, route, addr in bridges:
        st.markdown(f"""<div class="agent-card">
            <span class="agent-name">{name}</span>
            <span style="float: right; color: #6366f1; font-family: 'JetBrains Mono'; font-size: 0.8em;">{addr}</span>
            <div style="font-size: 0.85em; color: #aaa;">{route}</div>
        </div>""", unsafe_allow_html=True)
    
    if evm:
        st.markdown("---")
        st.markdown("### EVM DEX Contracts")
        for name, info in evm.get("tokens", {}).items():
            st.code(f"{name}: {info['address']}", language=None)
        st.code(f"SimpleSwap: {evm.get('dex', {}).get('address', '—')}", language=None)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5: AGENTS
# ══════════════════════════════════════════════════════════════════════════════

with tab_agents:
    st.markdown("### Agent Registry")
    
    issuer = load_issuer_config()
    
    agent_data = [
        {
            "Agent": "🎯 Spot Trader",
            "Address": "rG4mzN4LdjQUXgAvLbB2DQxD5aAq6jtZGx",
            "DID": "did:xrpl:testnet:rG4mzN4LdjQ...",
            "Capabilities": "Arbitrage detection, spot execution, risk scoring",
            "Trust Lines": 14,
        },
        {
            "Agent": "⚡ Flash Loan",
            "Address": "rL721eQQexPb9EREChEjnoGCoetP7GzzKV",
            "DID": "did:xrpl:testnet:rL721eQQex...",
            "Capabilities": "Flash loan execution, path finding, cross-currency",
            "Trust Lines": 14,
        },
        {
            "Agent": "🏦 Token Issuer",
            "Address": issuer.get("address", "—") if issuer else "—",
            "DID": f"did:xrpl:testnet:{issuer.get('address', '—')[:12]}..." if issuer else "—",
            "Capabilities": "USD/EUR/BTC issuance, market making",
            "Trust Lines": 0,
        },
        {
            "Agent": "⚖️ Risk Manager",
            "Address": "In-memory",
            "DID": "—",
            "Capabilities": "Position limits, daily P&L, risk scoring (0-1)",
            "Trust Lines": "—",
        },
        {
            "Agent": "📊 Monitoring",
            "Address": "In-memory",
            "DID": "—",
            "Capabilities": "Trade logging, health checks, metrics export",
            "Trust Lines": "—",
        },
        {
            "Agent": "🔮 Quantum Predictor",
            "Address": "IBM ibm_fez",
            "DID": "—",
            "Capabilities": "Price prediction (4q), arbitrage detection (Grover), VaR (QFT)",
            "Trust Lines": "—",
        },
    ]
    
    st.dataframe(pd.DataFrame(agent_data), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("### Integration Modules")
    
    modules = [
        ("Advanced DEX", "integrations/advanced_dex.py", "IOC, FOK, passive offers, expiration, atomic replace"),
        ("AMM Manager", "integrations/amm_manager.py", "Create/deposit/withdraw pools, vote fee, bid auction"),
        ("Oracle Publisher", "integrations/oracle_publisher.py", "Publish quantum signals as on-chain price feeds (XLS-47)"),
        ("Encrypted Keystore", "integrations/keystore.py", "AES-256-GCM wallet encryption, PBKDF2 600K iterations"),
        ("Cross-Chain Client", "integrations/crosschain_client.py", "XRPL + EVM + Sepolia scanner, Uniswap V3 pool queries"),
        ("IBM Quantum Backend", "quantum_tools/ibm_backend.py", "SamplerV2 execution, auto-fallback to AerSimulator"),
    ]
    
    for name, path, desc in modules:
        st.markdown(f"""<div class="agent-card">
            <span class="agent-name">📦 {name}</span>
            <span style="float: right; font-family: 'JetBrains Mono'; font-size: 0.75em; color: #6366f1;">{path}</span>
            <div style="font-size: 0.85em; color: #aaa; margin-top: 4px;">{desc}</div>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Owner Identity")
    st.markdown("""
    | Field | Value |
    |-------|-------|
    | **Owner** | `rHTHaQ9EtuKkSSAoh9R1ViGt69J2ZMHQWq` |
    | **Bithomp** | [View on Testnet](https://test.bithomp.com/en/account/rHTHaQ9EtuKkSSAoh9R1ViGt69J2ZMHQWq) |
    | **DID URI** | `https://github.com/Hobie1Kenobi/Thoth-Oracle` |
    | **Network** | XRPL Testnet |
    """)
