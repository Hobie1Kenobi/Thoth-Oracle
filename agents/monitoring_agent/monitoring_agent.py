"""
Monitoring Agent Module
Handles system monitoring and health checks.
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
    def __init__(self, log_dir: str = "logs"):
        """Initialize the Monitoring Agent."""
        self.log_dir = log_dir
        self.system_health = {
            "status": "healthy",
            "last_check": None,
            "errors": []
        }
        self.performance_metrics = {
            "trades": [],
            "errors": [],
            "latency": []
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
            
            self.performance_metrics["trades"].append(trade)
            self.performance_metrics["latency"].append(latency)
            
            # Write to trade log file
            log_file = os.path.join(self.log_dir, "trades.log")
            with open(log_file, "a") as f:
                f.write(json.dumps(trade) + "\n")
                
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            await self.log_error("trade_logging", str(e))
    
    async def log_error(
        self,
        component: str,
        error: str,
        severity: str = "error"
    ) -> None:
        """Log an error event."""
        try:
            error_event = {
                "timestamp": datetime.now().isoformat(),
                "component": component,
                "error": error,
                "severity": severity
            }
            
            self.performance_metrics["errors"].append(error_event)
            
            # Write to error log file
            log_file = os.path.join(self.log_dir, "errors.log")
            with open(log_file, "a") as f:
                f.write(json.dumps(error_event) + "\n")
                
            # Update system health if severe error
            if severity == "critical":
                self.system_health["status"] = "degraded"
                self.system_health["errors"].append(error_event)
                
        except Exception as e:
            logger.error(f"Error logging error event: {e}")
    
    async def check_system_health(self) -> Dict:
        """Check overall system health."""
        try:
            # Update last check timestamp
            self.system_health["last_check"] = datetime.now().isoformat()
            
            # Check error count in last hour
            recent_errors = [
                e for e in self.performance_metrics["errors"]
                if (datetime.now() - datetime.fromisoformat(e["timestamp"])).total_seconds() < 3600
            ]
            
            # Check average latency
            recent_latency = self.performance_metrics["latency"][-100:] if self.performance_metrics["latency"] else []
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
    
    async def get_performance_metrics(self) -> Dict:
        """Get system performance metrics."""
        try:
            if not self.performance_metrics["trades"]:
                return {
                    "trade_count": 0,
                    "avg_profit": "0",
                    "avg_latency": 0,
                    "error_rate": 0
                }
            
            # Calculate metrics
            trades = self.performance_metrics["trades"]
            total_profit = sum(Decimal(t["profit"]) for t in trades)
            avg_profit = total_profit / len(trades)
            
            latency = self.performance_metrics["latency"]
            avg_latency = sum(latency) / len(latency) if latency else 0
            
            # Calculate error rate (errors per 100 trades)
            error_rate = (
                len(self.performance_metrics["errors"]) * 100 / len(trades)
                if trades else 0
            )
            
            return {
                "trade_count": len(trades),
                "avg_profit": str(avg_profit),
                "avg_latency": avg_latency,
                "error_rate": error_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"error": str(e)}
    
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
                
                # Clean up old metrics (keep last 24 hours)
                self.cleanup_old_metrics()
                
                # Wait for next check
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await self.log_error("monitoring", str(e), "critical")
    
    def cleanup_old_metrics(self) -> None:
        """Clean up metrics older than 24 hours."""
        try:
            cutoff = datetime.now().timestamp() - (24 * 3600)
            
            # Clean up trades
            self.performance_metrics["trades"] = [
                t for t in self.performance_metrics["trades"]
                if datetime.fromisoformat(t["timestamp"]).timestamp() > cutoff
            ]
            
            # Clean up errors
            self.performance_metrics["errors"] = [
                e for e in self.performance_metrics["errors"]
                if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff
            ]
            
            # Clean up latency (keep last 1000 points)
            if len(self.performance_metrics["latency"]) > 1000:
                self.performance_metrics["latency"] = self.performance_metrics["latency"][-1000:]
                
        except Exception as e:
            logger.error(f"Error cleaning up metrics: {e}")
            
    async def export_metrics(self, format: str = "json") -> Optional[str]:
        """Export metrics in specified format."""
        try:
            metrics = {
                "system_health": self.system_health,
                "performance": await self.get_performance_metrics(),
                "export_time": datetime.now().isoformat()
            }
            
            if format == "json":
                return json.dumps(metrics, indent=2)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Error exporting metrics: {e}")
            return None
