"""
Flash Loan Agent Module
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional
import logging
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment
from xrpl.asyncio.transaction import submit_and_wait
from xrpl.asyncio.clients import AsyncJsonRpcClient

logger = logging.getLogger(__name__)

class FlashLoanAgent:
    def __init__(self, client: JsonRpcClient, wallet: Optional[Wallet] = None):
        """Initialize the Flash Loan Agent."""
        self.sync_client = client
        self.client = AsyncJsonRpcClient(client.url)
        self.wallet = wallet
    
    async def check_loan_availability(self, currency: str, amount: Decimal) -> Dict:
        """Check if a flash loan is available for the given currency and amount."""
        try:
            # Check if we have a wallet
            if not self.wallet:
                return {
                    "available": False,
                    "reason": "No wallet configured"
                }
            
            # Check account info
            account_info = await self.client.request(
                AccountInfo(
                    account=self.wallet.classic_address
                )
            )
            
            # Simple check - ensure account has enough XRP for fees
            if Decimal(account_info.result["account_data"]["Balance"]) < Decimal("50"):
                return {
                    "available": False,
                    "reason": "Insufficient XRP for fees"
                }
            
            return {
                "available": True,
                "max_amount": amount
            }
            
        except Exception as e:
            logger.error(f"Error checking loan availability: {e}")
            return {
                "available": False,
                "reason": str(e)
            }
    
    async def calculate_loan_fee(self, currency: str, amount: Decimal) -> Decimal:
        """Calculate the fee for a flash loan."""
        # Simple implementation - 0.1% fee
        return amount * Decimal("0.001")
    
    async def execute_flash_loan(self, base_currency: str, quote_currency: str, issuer: str, amount: Decimal, target_rate: Decimal) -> Dict:
        """Execute a flash loan trade."""
        try:
            if not self.wallet:
                raise ValueError("Wallet required for flash loans")
            
            # Validate issuer address
            if not issuer or len(issuer) < 25:  # Basic address length check
                logger.error(f"Invalid issuer address: {issuer}")
                return {
                    "success": False,
                    "error": "Invalid issuer address"
                }
            
            # Calculate fee
            fee = await self.calculate_loan_fee(base_currency, amount)
            
            # Handle XRP special case
            if base_currency.upper() == "XRP":
                loan_amount = str(int(amount * Decimal("1000000")))  # Convert to drops
                repay_amount = str(int((amount + fee) * Decimal("1000000")))  # Convert to drops
            else:
                loan_amount = {
                    "currency": base_currency.upper(),  # Ensure uppercase for currency code
                    "value": str(amount),
                    "issuer": issuer
                }
                repay_amount = {
                    "currency": base_currency.upper(),  # Ensure uppercase for currency code
                    "value": str(amount + fee),
                    "issuer": issuer
                }
            
            # Calculate send_max values (1% slippage tolerance)
            if quote_currency.upper() == "XRP":
                loan_send_max = str(int(amount * Decimal("1.01") * Decimal("1000000")))
                repay_send_max = str(int((amount + fee) * Decimal("1.01") * Decimal("1000000")))
            else:
                loan_send_max = {
                    "currency": quote_currency.upper(),  # Ensure uppercase for currency code
                    "value": str(amount * Decimal("1.01")),
                    "issuer": issuer
                }
                repay_send_max = {
                    "currency": quote_currency.upper(),  # Ensure uppercase for currency code
                    "value": str((amount + fee) * Decimal("1.01")),
                    "issuer": issuer
                }
            
            # Create flash loan payment with path finding
            loan_payment = Payment(
                account=self.wallet.classic_address,
                destination=self.wallet.classic_address,  # Send to self
                amount=loan_amount,
                send_max=loan_send_max,
                flags=131072  # tfNoDirectRipple flag
            )
            
            logger.info(f"Submitting loan payment: {loan_payment.to_dict()}")
            
            # Submit flash loan
            loan_response = await submit_and_wait(
                transaction=loan_payment,
                client=self.client,
                wallet=self.wallet
            )
            
            if not loan_response.result.get("validated", False):
                logger.error(f"Flash loan failed: {loan_response.result}")
                return {
                    "success": False,
                    "error": f"Flash loan failed: {loan_response.result}"
                }
            
            logger.info(f"Flash loan successful: {loan_response.result['hash']}")
            
            # Execute the trade at target rate with path finding
            repayment = Payment(
                account=self.wallet.classic_address,
                destination=self.wallet.classic_address,  # Send to self
                amount=repay_amount,
                send_max=repay_send_max,
                flags=131072  # tfNoDirectRipple flag
            )
            
            logger.info(f"Submitting repayment: {repayment.to_dict()}")
            
            # Submit repayment
            repay_response = await submit_and_wait(
                transaction=repayment,
                client=self.client,
                wallet=self.wallet
            )
            
            if repay_response.result.get("validated", False):
                profit = (amount * target_rate) - (amount + fee)
                logger.info(f"Flash loan repaid successfully: {repay_response.result['hash']}")
                return {
                    "success": True,
                    "loan_hash": loan_response.result["hash"],
                    "repay_hash": repay_response.result["hash"],
                    "profit": str(profit)
                }
            else:
                logger.error(f"Repayment failed: {repay_response.result}")
                return {
                    "success": False,
                    "error": f"Repayment failed: {repay_response.result}"
                }
                
        except Exception as e:
            logger.error(f"Error executing flash loan: {e}")
            return {
                "success": False,
                "error": str(e)
            }
