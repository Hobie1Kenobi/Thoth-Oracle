"""
Thoth Oracle Dashboard - Real-time Arbitrage Opportunity Visualization
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from decimal import Decimal
from collections import defaultdict

# Set page config
st.set_page_config(
    page_title="Thoth Oracle Dashboard",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(to right, #1a1a1a, #2d2d2d);
        color: #ffffff;
    }
    .profit {
        color: #00ff00;
        font-weight: bold;
    }
    .loss {
        color: #ff0000;
        font-weight: bold;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.1);
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

def load_opportunities():
    """Load opportunities from the log file."""
    opportunities = []
    try:
        with open("logs/arbitrage_opportunities.log", "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    # Convert timestamp string to datetime
                    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
                    opportunities.append(data)
                except:
                    continue
    except FileNotFoundError:
        st.warning("No opportunity log file found. Start the arbitrage detection script first.")
    return opportunities

def create_metrics(opportunities):
    """Create summary metrics."""
    if not opportunities:
        return {
            "total_opportunities": 0,
            "direct_opportunities": 0,
            "triangular_opportunities": 0,
            "avg_profit_percentage": 0,
            "best_profit_percentage": 0,
            "total_potential_profit": 0
        }
    
    metrics = {
        "total_opportunities": len(opportunities),
        "direct_opportunities": len([o for o in opportunities if o["type"] == "direct"]),
        "triangular_opportunities": len([o for o in opportunities if o["type"] == "triangular"]),
        "avg_profit_percentage": sum(float(o["details"]["profit_percentage"]) for o in opportunities) / len(opportunities),
        "best_profit_percentage": max(float(o["details"]["profit_percentage"]) for o in opportunities),
        "total_potential_profit": sum(float(o["details"]["profit"]) for o in opportunities)
    }
    return metrics

def create_opportunity_timeline(opportunities):
    """Create timeline of opportunities."""
    if not opportunities:
        return go.Figure()
    
    df = pd.DataFrame([{
        "timestamp": o["timestamp"],
        "profit_percentage": float(o["details"]["profit_percentage"]),
        "type": o["type"],
        "profit": float(o["details"]["profit"])
    } for o in opportunities])
    
    fig = go.Figure()
    
    # Add traces for direct and triangular opportunities
    for opp_type in ["direct", "triangular"]:
        df_type = df[df["type"] == opp_type]
        fig.add_trace(go.Scatter(
            x=df_type["timestamp"],
            y=df_type["profit_percentage"],
            mode="markers+lines",
            name=f"{opp_type.capitalize()} Arbitrage",
            hovertemplate="<br>".join([
                "Time: %{x}",
                "Profit: %{y:.2f}%",
                "Type: " + opp_type.capitalize()
            ])
        ))
    
    fig.update_layout(
        title="Arbitrage Opportunities Timeline",
        xaxis_title="Time",
        yaxis_title="Profit Percentage (%)",
        template="plotly_dark",
        hovermode="x unified"
    )
    return fig

def create_profit_distribution(opportunities):
    """Create profit distribution chart."""
    if not opportunities:
        return go.Figure()
    
    profits = [float(o["details"]["profit_percentage"]) for o in opportunities]
    
    fig = go.Figure(data=[go.Histogram(
        x=profits,
        nbinsx=30,
        name="Profit Distribution"
    )])
    
    fig.update_layout(
        title="Profit Distribution",
        xaxis_title="Profit Percentage (%)",
        yaxis_title="Count",
        template="plotly_dark"
    )
    return fig

def create_exchange_heatmap(opportunities):
    """Create exchange pair heatmap."""
    if not opportunities:
        return go.Figure()
    
    # Collect exchange pairs and their average profits
    exchange_profits = defaultdict(list)
    for opp in opportunities:
        if opp["type"] == "direct":
            pair = (opp["details"]["buy_exchange"], opp["details"]["sell_exchange"])
            exchange_profits[pair].append(float(opp["details"]["profit_percentage"]))
    
    # Calculate average profits
    exchange_matrix = defaultdict(lambda: defaultdict(float))
    exchanges = set()
    for (buy, sell), profits in exchange_profits.items():
        exchanges.add(buy)
        exchanges.add(sell)
        exchange_matrix[buy][sell] = sum(profits) / len(profits)
    
    exchanges = sorted(list(exchanges))
    z_data = [[exchange_matrix[buy][sell] for sell in exchanges] for buy in exchanges]
    
    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=exchanges,
        y=exchanges,
        colorscale="RdYlGn",
        text=[[f"{val:.2f}%" if val else "" for val in row] for row in z_data],
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))
    
    fig.update_layout(
        title="Exchange Pair Profitability Heatmap",
        xaxis_title="Sell Exchange",
        yaxis_title="Buy Exchange",
        template="plotly_dark"
    )
    return fig

def main():
    st.title("🔮 Thoth Oracle Dashboard")
    st.markdown("Real-time monitoring of arbitrage opportunities across the XRPL network")
    
    # Load opportunities
    opportunities = load_opportunities()
    metrics = create_metrics(opportunities)
    
    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
            <div class="metric-card">
                <h3>Total Opportunities</h3>
                <h2>{}</h2>
            </div>
        """.format(metrics["total_opportunities"]), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
            <div class="metric-card">
                <h3>Best Profit</h3>
                <h2 class="profit">{:.2f}%</h2>
            </div>
        """.format(metrics["best_profit_percentage"]), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
            <div class="metric-card">
                <h3>Average Profit</h3>
                <h2>{:.2f}%</h2>
            </div>
        """.format(metrics["avg_profit_percentage"]), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
            <div class="metric-card">
                <h3>Total Potential Profit</h3>
                <h2 class="profit">${:.2f}</h2>
            </div>
        """.format(metrics["total_potential_profit"]), unsafe_allow_html=True)
    
    # Charts
    st.plotly_chart(create_opportunity_timeline(opportunities), use_container_width=True, key="timeline_chart")
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_profit_distribution(opportunities), use_container_width=True, key="profit_dist_chart")
    with col2:
        st.plotly_chart(create_exchange_heatmap(opportunities), use_container_width=True, key="heatmap_chart")
    
    # Recent Opportunities Table
    st.subheader("Recent Opportunities")
    if opportunities:
        recent = sorted(opportunities, key=lambda x: x["timestamp"], reverse=True)[:10]
        df = pd.DataFrame([{
            "Time": o["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "Type": o["type"].capitalize(),
            "Profit %": f"{float(o['details']['profit_percentage']):.2f}%",
            "Profit": f"${float(o['details']['profit']):.2f}",
            "Details": "Buy: {} @ {}, Sell: {} @ {}".format(
                o["details"].get("buy_exchange", "N/A"),
                o["details"].get("buy_rate", "N/A"),
                o["details"].get("sell_exchange", "N/A"),
                o["details"].get("sell_rate", "N/A")
            ) if o["type"] == "direct" else o["details"].get("path", "N/A")
        } for o in recent])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No recent opportunities found")

    # Auto-refresh
    st.empty()
    st.button("Refresh Data")

if __name__ == "__main__":
    main()
