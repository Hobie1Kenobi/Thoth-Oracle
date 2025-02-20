"""Example script demonstrating flash loan execution across chains."""

import asyncio
from decimal import Decimal
from typing import Dict, Optional

from integrations.web3_client import Web3Client
from integrations.across_bridge import AcrossBridgeClient
from integrations.hooks_client import XRPLHooksClient
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from web3 import Web3

async def execute_cross_chain_flash_loan(
    amount: Decimal,
    token_address: str,
    source_chain: int,
    target_chain: int
) -> Optional[Dict]:
    """Execute a cross-chain flash loan with arbitrage.
    
    Args:
        amount: Amount to borrow in base units
        token_address: Address of the token to borrow
        source_chain: Chain ID where flash loan originates
        target_chain: Chain ID for arbitrage opportunity
    
    Returns:
        Dict containing transaction details and profit/loss
    """
    # Initialize clients
    web3_client = Web3Client(
        f"https://mainnet.infura.io/v3/{os.getenv('INFURA_PROJECT_ID')}"
    )
    
    bridge_client = AcrossBridgeClient()
    
    xrpl_client = JsonRpcClient("wss://s1.ripple.com")
    xrpl_wallet = Wallet.from_seed(os.getenv("XRPL_SEED"))
    hooks_client = XRPLHooksClient(
        xrpl_client,
        xrpl_wallet,
        os.getenv("HOOK_ACCOUNT")
    )

    try:
        # 1. Execute flash loan on source chain
        flash_loan_tx = await web3_client.execute_flash_loan(
            os.getenv("AAVE_LENDING_POOL"),
            amount,
            Web3.to_checksum_address(token_address),
            {"onBehalfOf": os.getenv("BORROWER_ADDRESS")}
        )
        
        # 2. Bridge tokens to target chain
        bridge_quote = await bridge_client.get_bridge_quote(
            token_address,
            token_address,
            str(amount),
            source_chain,
            target_chain
        )
        
        bridge_tx = await bridge_client.submit_bridge_transaction(
            bridge_quote["quoteId"],
            flash_loan_tx["hash"]
        )
        
        # 3. Execute arbitrage on XRPL
        hook_tx = await hooks_client.execute_hook_transaction(
            "Payment",
            {
                "Amount": str(amount),
                "Destination": os.getenv("AMM_ADDRESS")
            }
        )
        
        # 4. Bridge back and repay
        return_quote = await bridge_client.get_bridge_quote(
            token_address,
            token_address,
            str(amount),
            target_chain,
            source_chain
        )
        
        return_tx = await bridge_client.submit_bridge_transaction(
            return_quote["quoteId"],
            hook_tx["tx_json"]["hash"]
        )
        
        # Wait for completion
        while True:
            status = await bridge_client.get_bridge_status(return_tx["txHash"])
            if status["status"] == "completed":
                break
            await asyncio.sleep(5)
        
        return {
            "flash_loan_tx": flash_loan_tx["hash"],
            "bridge_tx": bridge_tx["txHash"],
            "hook_tx": hook_tx["tx_json"]["hash"],
            "return_tx": return_tx["txHash"],
            "profit": calculate_profit(
                amount,
                hook_tx["tx_json"]["Amount"],
                bridge_quote["fee"],
                return_quote["fee"]
            )
        }
        
    except Exception as e:
        print(f"Error executing flash loan: {str(e)}")
        return None

def calculate_profit(
    borrowed_amount: Decimal,
    final_amount: Decimal,
    outbound_fee: Decimal,
    inbound_fee: Decimal
) -> Decimal:
    """Calculate profit/loss from the operation."""
    return final_amount - borrowed_amount - outbound_fee - inbound_fee

async def main():
    """Main execution function."""
    # Example usage
    result = await execute_cross_chain_flash_loan(
        Decimal("1000000000000000000"),  # 1 ETH
        "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        1,  # Ethereum
        2  # XRPL
    )
    
    if result:
        print("Flash loan executed successfully!")
        print(f"Profit: {result['profit']} ETH")
        print("Transaction hashes:")
        print(f"Flash Loan: {result['flash_loan_tx']}")
        print(f"Bridge: {result['bridge_tx']}")
        print(f"Hook: {result['hook_tx']}")
        print(f"Return: {result['return_tx']}")
    else:
        print("Flash loan execution failed")

if __name__ == "__main__":
    asyncio.run(main())
