"""
Monitoring Agent Module
Handles system monitoring, logging, and metrics tracking.
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import json
import os

logger = logging.getLogger(__name__)

class MonitoringAgent:
    """Agent for monitoring system health and performance."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize the monitoring agent."""
        self.log_dir = log_dir
        self.trades = []
        self.errors = []
        self.metrics = {
            "total_trades": 0,
            "total_profit": Decimal("0"),
            "avg_latency": 0.0,
            "success_rate": 1.0
        }
        self.system_health = {
            "status": "healthy",
            "last_check": None,
            "errors": []
        }
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
    
    async def log_trade(
        self,
        pair: str,
        size: Decimal,
        profit: Decimal,
        latency: float
    ) -> None:
        """Log a completed trade."""
        try:
            trade = {
                "timestamp": datetime.now().isoformat(),
                "pair": pair,
                "size": str(size),
                "profit": str(profit),
                "latency": latency
            }
            
            self.trades.append(trade)
            
            # Update metrics
            self.metrics["total_trades"] += 1
            self.metrics["total_profit"] += profit
            self.metrics["avg_latency"] = (
                (self.metrics["avg_latency"] * (self.metrics["total_trades"] - 1) + latency) /
                self.metrics["total_trades"]
            )
            
            # Write to trade log file
            log_file = os.path.join(self.log_dir, "trades.log")
            with open(log_file, "a") as f:
                f.write(json.dumps(trade) + "\n")
                
            logger.info(f"Trade logged: {trade}")
            
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            await self.log_error("trade_logging", str(e))
    
    async def log_error(
        self,
        error_type: str,
        message: str,
        severity: str = "error"
    ) -> None:
        """Log an error."""
        try:
            error = {
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": message,
                "severity": severity
            }
            
            self.errors.append(error)
            
            # Update metrics
            if error_type == "trade_execution":
                total_attempts = self.metrics["total_trades"] + 1
                self.metrics["success_rate"] = (
                    self.metrics["total_trades"] / total_attempts
                    if total_attempts > 0 else 1.0
                )
            
            # Write to error log file
            log_file = os.path.join(self.log_dir, "errors.log")
            with open(log_file, "a") as f:
                f.write(json.dumps(error) + "\n")
                
            # Update system health if severe error
            if severity == "critical":
                self.system_health["status"] = "degraded"
                self.system_health["errors"].append(error)
                
            logger.error(f"Error logged: {error}")
            
        except Exception as e:
            logger.error(f"Error in error logging: {e}")
    
    async def log_health_check(self) -> None:
        """Log system health metrics."""
        try:
            health = {
                "total_trades": self.metrics["total_trades"],
                "total_profit": str(self.metrics["total_profit"]),
                "avg_latency": self.metrics["avg_latency"],
                "success_rate": self.metrics["success_rate"],
                "error_count": len(self.errors),
                "timestamp": datetime.now().isoformat()
            }
            
            # Write to health log file
            log_file = os.path.join(self.log_dir, "health.log")
            with open(log_file, "a") as f:
                f.write(json.dumps(health) + "\n")
                
            logger.info(f"Health check: {health}")
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            await self.log_error("health_check", str(e))
    
    def get_metrics(self) -> Dict:
        """Get current system metrics."""
        return {
            "total_trades": self.metrics["total_trades"],
            "total_profit": str(self.metrics["total_profit"]),
            "avg_latency": self.metrics["avg_latency"],
            "success_rate": self.metrics["success_rate"],
            "error_count": len(self.errors)
        }
    
    async def check_system_health(self) -> Dict:
        """Check overall system health."""
        try:
            # Update last check timestamp
            self.system_health["last_check"] = datetime.now().isoformat()
            
            # Check error count in last hour
            recent_errors = [
                e for e in self.errors
                if (datetime.now() - datetime.fromisoformat(e["timestamp"])).total_seconds() < 3600
            ]
            
            # Check average latency
            recent_latency = [t["latency"] for t in self.trades[-100:]] if self.trades else []
            avg_latency = sum(recent_latency) / len(recent_latency) if recent_latency else 0
            
            # Update health status
            if len(recent_errors) > 10 or avg_latency > 1.0:
                self.system_health["status"] = "degraded"
            else:
                self.system_health["status"] = "healthy"
            
            return {
                "status": self.system_health["status"],
                "last_check": self.system_health["last_check"],
                "error_count": len(recent_errors),
                "avg_latency": avg_latency,
                "active_components": self.get_active_components()
            }
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {
                "status": "unknown",
                "error": str(e)
            }
    
    def get_active_components(self) -> List[str]:
        """Get list of active system components."""
        # In a real implementation, this would check actual component status
        return [
            "flash_loan_agent",
            "xrpl_amm_agent",
            "risk_management_agent"
        ]
    
    async def start_monitoring(self) -> None:
        """Start continuous system monitoring."""
        try:
            while True:
                # Check system health every minute
                await self.check_system_health()
                
                # Log health check
                await self.log_health_check()
                
                # Wait for next check
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await self.log_error("monitoring", str(e), "critical")
    
    async def export_metrics(self, format: str = "json") -> Optional[str]:
        """Export metrics in specified format."""
        try:
            metrics = {
                "system_health": self.system_health,
                "performance": self.get_metrics(),
                "export_time": datetime.now().isoformat()
            }
            
            if format == "json":
                return json.dumps(metrics, indent=2)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return None
