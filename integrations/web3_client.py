"""
Web3 client for Ethereum integration
"""

from web3 import Web3
from eth_account import Account
import os

class Web3Client:
    """Client for interacting with Ethereum networks"""
    
    def __init__(self, network_url: str = None):
        """Initialize Web3 client with network URL"""
        self.network_url = network_url or os.getenv('ETH_NETWORK_URL', 'http://localhost:8545')
        self.w3 = Web3(Web3.HTTPProvider(self.network_url))
        
    def create_account(self) -> Account:
        """Create a new Ethereum account"""
        account = Account.create()
        return account
    
    async def get_balance(self, address: str) -> int:
        """Get balance of an address"""
        return self.w3.eth.get_balance(address)
    
    async def send_transaction(self, transaction: dict) -> str:
        """Send a transaction"""
        signed_txn = self.w3.eth.account.sign_transaction(transaction)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return tx_hash.hex()
    
    async def get_transaction(self, tx_hash: str) -> dict:
        """Get transaction details"""
        return self.w3.eth.get_transaction(tx_hash)
