"""Web3 Integration for EVM Chain Interactions."""

from typing import Dict, Optional
from web3 import Web3
from eth_typing import Address
from web3.middleware import geth_poa_middleware

class Web3Client:
    """Client for interacting with EVM-based chains."""
    
    def __init__(self, rpc_url: str):
        """Initialize Web3 client with RPC URL."""
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        # Add middleware for POA chains like BSC
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
    async def get_flash_loan_contract(self, address: str) -> Optional[Dict]:
        """Get flash loan contract interface."""
        try:
            # ABI for common flash loan providers (e.g., Aave)
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(address),
                abi=self.load_flash_loan_abi()
            )
            return contract
        except Exception as e:
            print(f"Error getting flash loan contract: {e}")
            return None
            
    async def execute_flash_loan(
        self, 
        contract_address: str,
        amount: int,
        asset: Address,
        params: Dict
    ) -> Dict:
        """Execute flash loan transaction."""
        contract = await self.get_flash_loan_contract(contract_address)
        if not contract:
            raise Exception("Failed to get flash loan contract")
            
        # Build flash loan transaction
        tx = await contract.functions.flashLoan(
            asset,
            amount,
            params.get('onBehalfOf', self.w3.eth.default_account),
            params.get('params', b'')
        ).build_transaction({
            'from': self.w3.eth.default_account,
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(
                self.w3.eth.default_account
            )
        })
        
        return tx
        
    def load_flash_loan_abi(self) -> Dict:
        """Load ABI for flash loan contract."""
        # TODO: Load from JSON file
        return {
            # Basic flash loan ABI structure
            "name": "flashLoan",
            "type": "function",
            "inputs": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "uint256"},
                {"name": "onBehalfOf", "type": "address"},
                {"name": "params", "type": "bytes"}
            ],
            "outputs": []
        }
