"""
Create test wallets for Thoth Oracle agents
"""
from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet
from xrpl.models import AccountInfo
import json
import os

def create_test_wallets():
    """Create test wallets and fund them with the faucet."""
    client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
    
    # Create spot trading wallet
    print("Creating spot trading wallet...")
    spot_wallet = generate_faucet_wallet(client, debug=True)
    
    # Create flash loan wallet
    print("Creating flash loan wallet...")
    flash_wallet = generate_faucet_wallet(client, debug=True)
    
    # Save wallet info
    wallets = {
        "spot_trading": {
            "seed": spot_wallet.seed,
            "public_key": spot_wallet.public_key,
            "private_key": spot_wallet.private_key,
            "classic_address": spot_wallet.classic_address
        },
        "flash_loan": {
            "seed": flash_wallet.seed,
            "public_key": flash_wallet.public_key,
            "private_key": flash_wallet.private_key,
            "classic_address": flash_wallet.classic_address
        }
    }
    
    # Create config directory if it doesn't exist
    os.makedirs("config", exist_ok=True)
    
    # Save wallet info
    with open("config/test_wallet_info.json", "w") as f:
        json.dump(wallets, f, indent=4)
    
    print("\nWallet information saved to config/test_wallet_info.json")
    print("\nUpdate the seeds in config/test_wallets.py with:")
    print(f"SPOT_TRADER_WALLET['seed'] = '{spot_wallet.seed}'")
    print(f"FLASH_LOAN_WALLET['seed'] = '{flash_wallet.seed}'")

if __name__ == "__main__":
    create_test_wallets()
