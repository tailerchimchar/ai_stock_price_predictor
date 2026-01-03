"""Integration tests for modules working together."""

import pytest
import pandas as pd
import pytz
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.normalization import normalize_candles
from src.fetch_ticker_price import StockFetcher


class FakeDataSource:
    """Fake data source for testing."""
    
    def __init__(self, price=None, history=None):
        self._price = price
        self._history = history if history is not None else pd.DataFrame()
    
    def get_price(self):
        return self._price
    
    def get_history(self, period: str):
        return self._history
    
    def get_financials(self):
        return pd.DataFrame()
    
    def get_actions(self):
        return pd.DataFrame()


class TestIntegration:
    """Test modules working together."""
    
    def test_normalize_then_validate(self):
        """Normalization and validation should work together."""
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=2, tz=est)
        df = pd.DataFrame({
            'Open': [100.0, 101.0],
            'High': [105.0, 106.0],
            'Low': [99.0, 100.0],
            'Close': [104.0, 105.0],
            'Volume': [1000000, 1100000],
        }, index=dates)
        df.index.name = 'Date'
        
        result = normalize_candles(df, validate=True)
        
        # Should have lowercase columns
        assert 'open' in result.columns
        # Should be UTC
        assert str(result['timestamp'].dt.tz) == 'UTC'
        # Should be sorted
        assert result['timestamp'].is_monotonic_increasing
    
    def test_stock_fetcher_with_normalization(self):
        """StockFetcher should normalize data from source."""
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=2, tz=est)
        mock_df = pd.DataFrame({
            'Open': [100.0, 101.0],
            'High': [105.0, 106.0],
            'Low': [99.0, 100.0],
            'Close': [104.0, 105.0],
            'Volume': [1000000, 1100000],
        }, index=dates)
        mock_df.index.name = 'Date'
        
        source = FakeDataSource(history=mock_df)
        fetcher = StockFetcher("SPY", use_cache=False, source=source)
        result = fetcher.get_historical_data("1mo")
        
        # Data should be normalized
        assert 'timestamp' in result.columns
        assert 'open' in result.columns
        assert str(result['timestamp'].dt.tz) == 'UTC'
    
    def test_stock_fetcher_with_caching(self):
        """StockFetcher should cache results."""
        source = FakeDataSource(price=150.5)
        fetcher = StockFetcher("SPY", use_cache=True, source=source)
        
        # First call
        price1 = fetcher.fetch_price()
        # Second call should use cache
        price2 = fetcher.fetch_price()
        
        assert price1 == price2 == 150.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
