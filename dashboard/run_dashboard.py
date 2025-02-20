"""
Dashboard Runner
Starts both the Dash app and the data collector
"""

import asyncio
import threading
from app import app
from data_collector import DataCollector
from xrpl.clients import JsonRpcClient

def run_dash():
    """Run the Dash app in a separate thread."""
    app.run_server(debug=False, port=8050)

async def main():
    """Main entry point."""
    # Start Dash app in a separate thread
    dash_thread = threading.Thread(target=run_dash)
    dash_thread.daemon = True
    dash_thread.start()
    
    # Initialize XRPL client
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    # Create and start data collector
    collector = DataCollector(client, app.state)
    await collector.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
