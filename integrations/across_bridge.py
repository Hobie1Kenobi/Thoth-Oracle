"""Across Protocol Bridge Integration."""

import aiohttp
from typing import Dict, Optional
from datetime import datetime

class AcrossBridgeClient:
    """Client for interacting with Across Protocol bridge."""
    
    def __init__(self, api_url: str = "https://across-v2.api.across.to"):
        """Initialize Across bridge client."""
        self.api_url = api_url
        self.session = None
        
    async def __aenter__(self):
        """Create aiohttp session on enter."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session on exit."""
        if self.session:
            await self.session.close()
            
    async def get_bridge_quote(
        self,
        from_token: str,
        to_token: str,
        amount: str,
        from_chain: int,
        to_chain: int
    ) -> Optional[Dict]:
        """Get quote for bridging tokens."""
        try:
            params = {
                "fromToken": from_token,
                "toToken": to_token,
                "amount": amount,
                "fromChain": from_chain,
                "toChain": to_chain,
                "timestamp": int(datetime.now().timestamp())
            }
            
            async with self.session.get(
                f"{self.api_url}/quote",
                params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Error getting bridge quote: {response.status}")
                    return None
        except Exception as e:
            print(f"Error in get_bridge_quote: {e}")
            return None
            
    async def submit_bridge_transaction(
        self,
        quote_id: str,
        tx_hash: str
    ) -> Optional[Dict]:
        """Submit bridge transaction for monitoring."""
        try:
            data = {
                "quoteId": quote_id,
                "txHash": tx_hash
            }
            
            async with self.session.post(
                f"{self.api_url}/submit",
                json=data
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Error submitting bridge tx: {response.status}")
                    return None
        except Exception as e:
            print(f"Error in submit_bridge_transaction: {e}")
            return None
            
    async def get_bridge_status(self, tx_hash: str) -> Optional[Dict]:
        """Get status of bridge transaction."""
        try:
            async with self.session.get(
                f"{self.api_url}/status/{tx_hash}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Error getting bridge status: {response.status}")
                    return None
        except Exception as e:
            print(f"Error in get_bridge_status: {e}")
            return None
