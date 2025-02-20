"""
Interactive demo of the Market Data Oracle dashboard with real XRPL data
"""

import asyncio
import streamlit as st
from datetime import datetime
from xrpl.clients import JsonRpcClient
from dashboard import launch_dashboard
from xrpl_connector import XRPLConnector
import pandas as pd
import time

async def fetch_market_data(connector: XRPLConnector) -> dict:
    """Fetch real market data from XRPL"""
    # Fetch AMM pools
    pools = await connector.get_top_amm_pools(limit=10)
    
    # Fetch currency pairs
    pairs = await connector.get_currency_pairs(limit=25)
    
    # Detect arbitrage opportunities
    opportunities = await connector.detect_arbitrage(min_profit_pct=0.5)
    
    # Calculate correlation matrix
    correlation_matrix = connector.calculate_correlation_matrix(pairs)
    
    # Calculate overview metrics
    total_volume = sum(pool.get('volume_24h', 0) for pool in pools)
    total_liquidity = sum(pool.get('liquidity', 0) for pool in pools)
    
    overview_metrics = {
        'total_volume_24h': total_volume,
        'volume_change_24h': 0,  # TODO: Implement 24h change calculation
        'active_pools': len(pools),
        'total_liquidity': total_liquidity,
        'liquidity_change_24h': 0,  # TODO: Implement 24h change calculation
        'tracked_pairs': len(pairs)
    }
    
    return {
        'amm_pools': {pool['pool_id']: pool for pool in pools},
        'currency_pairs': {pair['pair_id']: pair for pair in pairs},
        'overview_metrics': overview_metrics,
        'arbitrage_opportunities': opportunities,
        'correlation_matrix': pd.DataFrame(correlation_matrix)
    }

def main():
    """Launch the demo dashboard with real XRPL data"""
    # Initialize session state for data caching
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    if 'market_data' not in st.session_state:
        st.session_state.market_data = None
    if 'network' not in st.session_state:
        st.session_state.network = "Testnet"
    if 'update_interval' not in st.session_state:
        st.session_state.update_interval = 10
    if 'min_profit' not in st.session_state:
        st.session_state.min_profit = 0.5

    # Add network selection in sidebar
    network = st.sidebar.selectbox(
        "Select Network",
        ["Mainnet", "Testnet"],
        index=1,
        key='network_select'
    )
    
    # Update client based on network selection
    if network == "Mainnet":
        client = JsonRpcClient("https://xrplcluster.com")
    else:
        client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    connector = XRPLConnector(client)
    
    # Add controls in sidebar
    st.sidebar.title("Settings")
    update_interval = st.sidebar.slider(
        "Update Interval (seconds)",
        min_value=5,
        max_value=60,
        value=st.session_state.update_interval,
        key='interval_slider'
    )
    
    min_profit = st.sidebar.slider(
        "Min. Arbitrage Profit (%)",
        min_value=0.1,
        max_value=5.0,
        value=st.session_state.min_profit,
        step=0.1,
        key='profit_slider'
    )

    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.session_state.last_update = None

    # Launch dashboard
    dashboard = launch_dashboard()
    
    # Check if we need to update data
    current_time = datetime.now()
    should_update = (
        st.session_state.last_update is None or
        (current_time - st.session_state.last_update).total_seconds() >= update_interval
    )

    try:
        if should_update:
            # Fetch and update market data
            market_data = asyncio.run(fetch_market_data(connector))
            st.session_state.market_data = market_data
            st.session_state.last_update = current_time
            
        # Update the dashboard with cached data
        if st.session_state.market_data:
            dashboard.update_dashboard(st.session_state.market_data)
            
        # Show last update time
        st.sidebar.write(
            f"Last Updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}"
        )
            
    except Exception as e:
        st.error(f"Error updating dashboard: {e}")

    # Add auto-refresh using Streamlit's rerun
    time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    st.rerun()

if __name__ == "__main__":
    main()
