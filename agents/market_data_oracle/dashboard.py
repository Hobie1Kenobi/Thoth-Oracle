"""
Real-time Dashboard Integration Module
Provides real-time market data visualization and analytics interface
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List

# Set page config at the module level
st.set_page_config(
    page_title="XRPL Market Data Oracle",
    page_icon="📊",
    layout="wide"
)

class MarketDataDashboard:
    def __init__(self):
        self.last_update = None
        self.arbitrage_opportunities = []

    def initialize_dashboard(self):
        """Initialize the Streamlit dashboard layout."""
        st.title("XRPL Market Data Oracle Dashboard")

    def display_arbitrage_alerts(self, opportunities: List[dict]):
        """Display arbitrage opportunities alerts."""
        st.header("🔔 Arbitrage Opportunities")
        
        if not opportunities:
            st.info("No arbitrage opportunities detected")
            return
            
        for opp in opportunities:
            with st.expander(
                f"💰 {opp['type'].title()} Arbitrage - {opp['profit_pct']:.2f}% Profit Potential",
                expanded=True
            ):
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Pool 1", opp['pool1'])
                with cols[1]:
                    st.metric("Pool 2", opp['pool2'])
                with cols[2]:
                    st.metric("Potential Profit", f"{opp['profit_pct']:.2f}%")
                
                # Add timestamp
                st.caption(f"Detected at: {opp['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        
    def display_overview_metrics(self, metrics: dict):
        """Display overview metrics in the dashboard."""
        st.header("Market Overview")
        cols = st.columns(4)
        
        with cols[0]:
            st.metric(
                "Total Trading Volume (24h)",
                f"${metrics.get('total_volume_24h', 0):,.2f}",
                delta=f"{metrics.get('volume_change_24h', 0):+.2f}%"
            )
        with cols[1]:
            st.metric(
                "Active AMM Pools",
                metrics.get('active_pools', 0)
            )
        with cols[2]:
            st.metric(
                "Total Liquidity",
                f"${metrics.get('total_liquidity', 0):,.2f}",
                delta=f"{metrics.get('liquidity_change_24h', 0):+.2f}%"
            )
        with cols[3]:
            st.metric(
                "Tracked Pairs",
                metrics.get('tracked_pairs', 0)
            )

    def plot_price_chart(self, price_history: List[dict], pair_id: str):
        """Create and display a price chart for a currency pair."""
        if not price_history:
            st.warning(f"No price data available for {pair_id}")
            return

        df = pd.DataFrame(price_history)
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ))

        # Add volume bars
        fig.add_trace(go.Bar(
            x=df['timestamp'],
            y=df['volume'],
            name='Volume',
            yaxis='y2',
            opacity=0.3
        ))

        fig.update_layout(
            title=f"{pair_id} Price Chart",
            xaxis_title="Time",
            yaxis_title="Price",
            yaxis2=dict(
                title="Volume",
                overlaying="y",
                side="right"
            ),
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)

    def display_amm_pools(self, pools_data: Dict[str, dict]):
        """Display AMM pools information and metrics."""
        st.header("AMM Pools Overview")
        
        # Convert pools data to DataFrame for display
        pools_df = pd.DataFrame.from_dict(pools_data, orient='index')
        
        if not pools_df.empty:
            # Create metrics table
            st.dataframe(
                pools_df[[
                    'token_a', 'token_b', 'liquidity', 
                    'volume_24h', 'price', 'trading_fee',
                    'last_updated'
                ]],
                use_container_width=True
            )
            
            # Create liquidity distribution pie chart
            fig = px.pie(
                pools_df,
                values='liquidity',
                names=pools_df.index,
                title='Liquidity Distribution Across Pools'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Add pool utilization chart
            fig = px.bar(
                pools_df,
                x=pools_df.index,
                y='volume_24h',
                title='24h Trading Volume by Pool'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No AMM pools data available")

    def display_currency_pairs(self, pairs_data: Dict[str, dict]):
        """Display currency pairs tracking information."""
        st.header("Currency Pairs Analytics")
        
        # Convert pairs data to DataFrame
        pairs_df = pd.DataFrame.from_dict(pairs_data, orient='index')
        
        if not pairs_df.empty:
            # Create sortable table
            st.dataframe(
                pairs_df[[
                    'price', 'bid', 'ask', 'spread',
                    'volume_24h', 'last_updated'
                ]],
                use_container_width=True
            )
            
            # Create price change heatmap
            fig = px.imshow(
                pairs_df['spread'].values.reshape(-1, 1),
                labels=dict(x="", y="Pair", color="Spread"),
                y=pairs_df.index,
                color_continuous_scale="RdYlGn_r"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Add volume comparison chart
            fig = px.bar(
                pairs_df,
                x=pairs_df.index,
                y='volume_24h',
                title='24h Trading Volume by Pair'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No currency pairs data available")

    def display_correlation_matrix(self, correlation_matrix: pd.DataFrame):
        """Display correlation matrix between currency pairs."""
        st.header("Currency Pair Correlations")
        
        if not correlation_matrix.empty:
            fig = px.imshow(
                correlation_matrix,
                labels=dict(x="Pair", y="Pair", color="Correlation"),
                color_continuous_scale="RdBu"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No correlation data available")

    def update_dashboard(self, market_data: dict):
        """Update the dashboard with new market data."""
        self.last_update = datetime.now()
        
        # Display last update time
        st.sidebar.write(f"Last Updated: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Display arbitrage alerts first
        self.display_arbitrage_alerts(market_data.get('arbitrage_opportunities', []))
        
        # Display overview metrics
        self.display_overview_metrics(market_data.get('overview_metrics', {}))
        
        # Create tabs for different sections
        tabs = st.tabs(["AMM Pools", "Currency Pairs", "Correlations"])
        
        with tabs[0]:
            self.display_amm_pools(market_data.get('amm_pools', {}))
            
        with tabs[1]:
            self.display_currency_pairs(market_data.get('currency_pairs', {}))
            
        with tabs[2]:
            self.display_correlation_matrix(
                pd.DataFrame(market_data.get('correlation_matrix', {}))
            )

def launch_dashboard():
    """Launch the Streamlit dashboard."""
    dashboard = MarketDataDashboard()
    dashboard.initialize_dashboard()
    return dashboard

# Example usage:
# if __name__ == "__main__":
#     dashboard = launch_dashboard()
#     while True:
#         market_data = fetch_market_data()  # Implement this function
#         dashboard.update_dashboard(market_data)
#         time.sleep(60)  # Update every minute
