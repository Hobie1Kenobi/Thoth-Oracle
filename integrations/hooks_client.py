"""XRPL Hooks Integration Client."""

from typing import Dict, Optional, List
from xrpl.clients import JsonRpcClient
from xrpl.models import Transaction
from xrpl.wallet import Wallet

class XRPLHooksClient:
    """Client for interacting with XRPL Hooks."""
    
    def __init__(
        self,
        client: JsonRpcClient,
        wallet: Wallet,
        hook_account: str
    ):
        """Initialize XRPL Hooks client."""
        self.client = client
        self.wallet = wallet
        self.hook_account = hook_account
        
    async def deploy_hook(
        self,
        hook_binary: bytes,
        hook_params: Dict
    ) -> Optional[Dict]:
        """Deploy a hook to XRPL."""
        try:
            # Create SetHook transaction
            tx = {
                "TransactionType": "SetHook",
                "Account": self.hook_account,
                "Hooks": [{
                    "Hook": {
                        "CreateCode": hook_binary,
                        "HookOn": hook_params.get("HookOn", "0000000000000000"),
                        "HookNamespace": hook_params.get(
                            "HookNamespace",
                            "0000000000000000"
                        ),
                        "HookParameters": hook_params.get("HookParameters", [])
                    }
                }]
            }
            
            # Sign and submit transaction
            signed_tx = await self.wallet.sign_transaction(tx)
            result = await self.client.submit(signed_tx)
            return result
            
        except Exception as e:
            print(f"Error deploying hook: {e}")
            return None
            
    async def get_hook_state(
        self,
        hook_namespace: str,
        key: str
    ) -> Optional[bytes]:
        """Get hook state data."""
        try:
            # Query hook state
            result = await self.client.request({
                "command": "hook_state",
                "hook_account": self.hook_account,
                "namespace": hook_namespace,
                "key": key
            })
            
            if "node" in result and "HookState" in result["node"]:
                return result["node"]["HookState"]
            return None
            
        except Exception as e:
            print(f"Error getting hook state: {e}")
            return None
            
    async def execute_hook_transaction(
        self,
        tx_type: str,
        params: Dict
    ) -> Optional[Dict]:
        """Execute a transaction that triggers a hook."""
        try:
            # Create transaction that will trigger hook
            tx = {
                "TransactionType": tx_type,
                "Account": self.wallet.classic_address,
                **params
            }
            
            # Sign and submit transaction
            signed_tx = await self.wallet.sign_transaction(tx)
            result = await self.client.submit(signed_tx)
            return result
            
        except Exception as e:
            print(f"Error executing hook transaction: {e}")
            return None
            
    async def get_hook_definitions(self) -> Optional[List[Dict]]:
        """Get hook definitions for account."""
        try:
            result = await self.client.request({
                "command": "account_info",
                "account": self.hook_account,
                "ledger_index": "validated"
            })
            
            if "account_data" in result and "Hooks" in result["account_data"]:
                return result["account_data"]["Hooks"]
            return []
            
        except Exception as e:
            print(f"Error getting hook definitions: {e}")
            return None
