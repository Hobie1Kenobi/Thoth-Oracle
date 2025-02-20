"""
Test script for the Market Data Oracle system
"""

import asyncio
import logging
from xrpl.clients import JsonRpcClient
from market_data_oracle import MarketDataOracle
from amm_monitor import AMMPoolMonitor
from currency_tracker import CurrencyPairTracker
from dashboard import launch_dashboard
import streamlit as st

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize XRPL client (using testnet for testing)
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    # Initialize Market Data Oracle
    oracle = MarketDataOracle(client)
    await oracle.initialize()
    
    # Add some test currency pairs to track
    await oracle.track_currency_pair("XRP", "USD")
    await oracle.track_currency_pair("XRP", "EUR")
    await oracle.track_currency_pair("XRP", "BTC")
    
    # Start the oracle
    logger.info("Starting Market Data Oracle...")
    
    try:
        # Run the oracle for a few cycles to collect some data
        for _ in range(5):
            await oracle.update_amm_pools()
            await asyncio.sleep(10)  # Wait 10 seconds between updates
            
            # Get and display some analytics
            dashboard_data = oracle.get_dashboard_data()
            logger.info(f"Current AMM Pools: {len(dashboard_data['amm_pools'])}")
            logger.info(f"Tracked Currency Pairs: {len(dashboard_data['currency_pairs'])}")
            
            # Display some sample metrics
            for pair_id, pair_data in dashboard_data['currency_pairs'].items():
                logger.info(f"\nMetrics for {pair_id}:")
                logger.info(f"Price: {pair_data.get('price', 'N/A')}")
                logger.info(f"24h Volume: {pair_data.get('volume_24h', 'N/A')}")
                logger.info(f"Price Change 24h: {pair_data.get('price_change_24h', 'N/A')}")
    
    except Exception as e:
        logger.error(f"Error during oracle test: {e}")
    
    finally:
        logger.info("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())
