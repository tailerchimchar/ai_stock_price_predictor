"""Shared test fixtures and utilities."""

import pandas as pd
import pytz
from pathlib import Path


class FakeDataSource:
    """
    Mock data source for testing without yfinance API calls.
    
    Use this for integration tests where you want to test the flow
    without hitting real APIs. Does NOT test retry logic or error handling.
    """
    
    def __init__(self, price=None, history=None, raise_on_price=False, raise_on_history=False):
        self._price = price
        self._history = history if history is not None else pd.DataFrame()
        self.raise_on_price = raise_on_price
        self.raise_on_history = raise_on_history
    
    def get_price(self):
        """Return mocked price or raise exception."""
        if self.raise_on_price:
            raise Exception("Simulated API error")
        return self._price
    
    def get_history(self, period: str):
        """Return mocked history or raise exception."""
        if self.raise_on_history:
            raise Exception("Simulated API error")
        return self._history
    
    def get_financials(self):
        return pd.DataFrame()
    
    def get_actions(self):
        return pd.DataFrame()


def create_sample_ohlcv_data(periods=3, timezone='America/New_York'):
    """
    Create sample OHLCV data for testing.
    
    Args:
        periods: Number of candles to generate
        timezone: Timezone for the data
        
    Returns:
        DataFrame with OHLCV data
    """
    tz = pytz.timezone(timezone)
    dates = pd.date_range('2026-01-01', periods=periods, tz=tz)
    df = pd.DataFrame({
        'Open': [100.0 + i for i in range(periods)],
        'High': [105.0 + i for i in range(periods)],
        'Low': [99.0 + i for i in range(periods)],
        'Close': [104.0 + i for i in range(periods)],
        'Volume': [1000000 + i * 100000 for i in range(periods)],
    }, index=dates)
    df.index.name = 'Date'
    return df
