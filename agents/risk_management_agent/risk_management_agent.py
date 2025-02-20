"""
Risk Management Agent Module
Handles risk assessment and position tracking.
"""

import logging
from decimal import Decimal
from typing import Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskManagementAgent:
    """Agent for managing trading risk and positions."""
    
    def __init__(self):
        """Initialize the risk management agent."""
        self.positions = {}
        self.risk_limits = {
            "max_position_size": Decimal("10000"),  # 10,000 XRP
            "max_daily_loss": Decimal("1000"),      # 1,000 XRP
            "min_profit_threshold": Decimal("0.01"), # 1%
            "max_slippage": Decimal("0.005")        # 0.5%
        }
        self.daily_stats = {
            "total_profit_loss": Decimal("0"),
            "trade_count": 0,
            "start_time": datetime.now()
        }
    
    async def assess_trade_risk(self, pair: str, size: Decimal, expected_profit: Decimal) -> Dict:
        """Assess the risk of a potential trade."""
        try:
            # Reset daily stats if needed
            self._reset_daily_stats_if_needed()
            
            # Check position limits
            current_position = self.positions.get(pair, Decimal("0"))
            if current_position + size > self.risk_limits["max_position_size"]:
                return {
                    "execute": False,
                    "reason": "Position size limit exceeded",
                    "risk_score": 1.0
                }
            
            # Check daily loss limit
            if self.daily_stats["total_profit_loss"] < -self.risk_limits["max_daily_loss"]:
                return {
                    "execute": False,
                    "reason": "Daily loss limit reached",
                    "risk_score": 1.0
                }
            
            # Check profit threshold
            profit_percentage = expected_profit / size
            if profit_percentage < self.risk_limits["min_profit_threshold"]:
                return {
                    "execute": False,
                    "reason": "Insufficient profit potential",
                    "risk_score": 0.8
                }
            
            # Calculate risk score (0 = lowest risk, 1 = highest risk)
            risk_score = self._calculate_risk_score(size, profit_percentage)
            
            return {
                "execute": risk_score < 0.7,  # Execute if risk score is acceptable
                "risk_score": risk_score,
                "expected_profit": str(expected_profit),
                "current_position": str(current_position),
                "daily_pl": str(self.daily_stats["total_profit_loss"])
            }
            
        except Exception as e:
            logger.error(f"Error assessing trade risk: {e}")
            return {
                "execute": False,
                "reason": f"Risk assessment error: {str(e)}",
                "risk_score": 1.0
            }
    
    async def update_position(self, pair: str, size: Decimal, profit_loss: Decimal) -> Dict:
        """Update position and profit/loss tracking."""
        try:
            # Update position
            current_position = self.positions.get(pair, Decimal("0"))
            self.positions[pair] = current_position + size
            
            # Update daily stats
            self.daily_stats["total_profit_loss"] += profit_loss
            self.daily_stats["trade_count"] += 1
            
            return {
                "success": True,
                "new_position": str(self.positions[pair]),
                "daily_pl": str(self.daily_stats["total_profit_loss"]),
                "trade_count": self.daily_stats["trade_count"]
            }
            
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _calculate_risk_score(self, size: Decimal, profit_percentage: Decimal) -> float:
        """Calculate a risk score for a trade."""
        # Factors that increase risk:
        # 1. Large position size relative to limit
        # 2. Low profit percentage
        # 3. Current daily losses
        
        position_risk = float(size / self.risk_limits["max_position_size"])
        profit_risk = float(
            self.risk_limits["min_profit_threshold"] / profit_percentage
            if profit_percentage > 0 else 1.0
        )
        daily_risk = float(
            abs(self.daily_stats["total_profit_loss"]) /
            self.risk_limits["max_daily_loss"]
        ) if self.daily_stats["total_profit_loss"] < 0 else 0.0
        
        # Weighted average of risk factors
        risk_score = (
            position_risk * 0.4 +    # 40% weight on position size
            profit_risk * 0.3 +      # 30% weight on profit potential
            daily_risk * 0.3         # 30% weight on daily performance
        )
        
        return min(max(risk_score, 0.0), 1.0)  # Ensure between 0 and 1
    
    def _reset_daily_stats_if_needed(self) -> None:
        """Reset daily stats if a new day has started."""
        now = datetime.now()
        if now - self.daily_stats["start_time"] > timedelta(days=1):
            self.daily_stats = {
                "total_profit_loss": Decimal("0"),
                "trade_count": 0,
                "start_time": now
            }
