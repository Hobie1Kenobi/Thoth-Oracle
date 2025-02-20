"""
Currency Pair Tracking and Analysis Module
Handles tracking and analysis of currency pairs across multiple AMM pools
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class CurrencyPairTracker:
    def __init__(self):
        self.pairs: Dict[str, dict] = {}
        self.historical_prices: Dict[str, List[dict]] = {}
        self.analysis_window = timedelta(hours=24)

    def add_pair(self, token_a: str, token_b: str):
        """Add a new currency pair for tracking."""
        pair_id = f"{token_a}/{token_b}"
        if pair_id not in self.pairs:
            self.pairs[pair_id] = {
                "token_a": token_a,
                "token_b": token_b,
                "current_price": 0.0,
                "last_update": datetime.now()
            }
            self.historical_prices[pair_id] = []
            logger.info(f"Added new currency pair for tracking: {pair_id}")

    def update_price(self, token_a: str, token_b: str, price: float, volume: float = 0.0):
        """Update price information for a currency pair."""
        pair_id = f"{token_a}/{token_b}"
        timestamp = datetime.now()

        if pair_id not in self.pairs:
            self.add_pair(token_a, token_b)

        price_data = {
            "timestamp": timestamp,
            "price": price,
            "volume": volume
        }

        self.pairs[pair_id].update({
            "current_price": price,
            "last_update": timestamp
        })

        self.historical_prices[pair_id].append(price_data)
        
        # Clean up old data
        self.cleanup_historical_data(pair_id)

    def cleanup_historical_data(self, pair_id: str):
        """Remove historical data outside the analysis window."""
        cutoff_time = datetime.now() - self.analysis_window
        self.historical_prices[pair_id] = [
            entry for entry in self.historical_prices[pair_id]
            if entry["timestamp"] > cutoff_time
        ]

    def calculate_metrics(self, token_a: str, token_b: str) -> dict:
        """Calculate various metrics for a currency pair."""
        pair_id = f"{token_a}/{token_b}"
        if pair_id not in self.pairs:
            return {}

        historical_data = self.historical_prices[pair_id]
        if not historical_data:
            return {}

        # Convert to pandas DataFrame for easier analysis
        df = pd.DataFrame(historical_data)
        
        # Basic metrics
        current_price = self.pairs[pair_id]["current_price"]
        price_24h_ago = df.iloc[0]["price"] if len(df) > 0 else current_price
        
        # Calculate price changes
        price_change_24h = current_price - price_24h_ago
        price_change_pct = (price_change_24h / price_24h_ago * 100) if price_24h_ago != 0 else 0

        # Calculate volatility (standard deviation of returns)
        returns = df["price"].pct_change().dropna()
        volatility = returns.std() * 100 if len(returns) > 1 else 0

        # Calculate volume metrics
        volume_24h = df["volume"].sum()
        
        # Calculate moving averages
        ma_1h = df["price"].rolling(window=60).mean().iloc[-1] if len(df) >= 60 else current_price
        ma_24h = df["price"].rolling(window=1440).mean().iloc[-1] if len(df) >= 1440 else current_price

        return {
            "current_price": current_price,
            "price_change_24h": price_change_24h,
            "price_change_pct_24h": price_change_pct,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "ma_1h": ma_1h,
            "ma_24h": ma_24h,
            "last_update": self.pairs[pair_id]["last_update"]
        }

    def get_price_history(self, token_a: str, token_b: str, 
                         interval: str = "1h") -> List[dict]:
        """Get historical price data for a currency pair at specified interval."""
        pair_id = f"{token_a}/{token_b}"
        if pair_id not in self.historical_prices:
            return []

        df = pd.DataFrame(self.historical_prices[pair_id])
        
        # Convert timestamp to datetime if it's not already
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Resample data to the specified interval
        if interval == "1h":
            resampled = df.resample("1H", on="timestamp").agg({
                "price": "last",
                "volume": "sum"
            }).dropna()
        elif interval == "1d":
            resampled = df.resample("1D", on="timestamp").agg({
                "price": "last",
                "volume": "sum"
            }).dropna()
        else:
            return self.historical_prices[pair_id]

        return resampled.reset_index().to_dict("records")

    def get_correlation_matrix(self, pairs: List[str]) -> pd.DataFrame:
        """Calculate correlation matrix between multiple currency pairs."""
        price_data = {}
        
        for pair_id in pairs:
            if pair_id in self.historical_prices and self.historical_prices[pair_id]:
                df = pd.DataFrame(self.historical_prices[pair_id])
                price_data[pair_id] = df.set_index("timestamp")["price"]

        if not price_data:
            return pd.DataFrame()

        # Combine all price series into a single DataFrame
        combined = pd.DataFrame(price_data)
        
        # Calculate correlation matrix
        return combined.corr()

    def get_pair_analytics(self, token_a: str, token_b: str) -> dict:
        """Get comprehensive analytics for a currency pair."""
        metrics = self.calculate_metrics(token_a, token_b)
        price_history = self.get_price_history(token_a, token_b)
        
        return {
            "metrics": metrics,
            "price_history": price_history,
            "last_update": datetime.now()
        }
