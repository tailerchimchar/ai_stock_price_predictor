import pytest
import pandas as pd
from datetime import datetime
import pytz
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.fetch_ticker_price import StockFetcher


class FakeDataSource:
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


class TestStockFetcher:
    def test_fetch_price_invalid_ticker(self):
        fetcher = StockFetcher(ticker_symbol="INVALID123", use_cache=False, source=FakeDataSource(price=None))
        assert fetcher.fetch_price() is None

    def test_fetch_price_exception_handling(self):
        class ErrorSource(FakeDataSource):
            def get_price(self):
                raise Exception("API Error")

        fetcher = StockFetcher(ticker_symbol="SPY", use_cache=False, source=ErrorSource())
        assert fetcher.fetch_price() is None

    def test_get_historical_data_empty_response(self):
        fetcher = StockFetcher(ticker_symbol="INVALID", use_cache=False, source=FakeDataSource(history=pd.DataFrame()))
        result = fetcher.get_historical_data(period="1wk")
        assert result.empty

    def test_get_historical_data_timezone_conversion(self):
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=3, tz=est)
        mock_df = pd.DataFrame({
            'Open': [100.0, 101.0, 102.0],
            'High': [105.0, 106.0, 107.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [104.0, 105.0, 106.0],
            'Volume': [1000000, 1100000, 1200000],
            'Dividends': [0.0, 0.0, 0.0],
            'Stock Splits': [0.0, 0.0, 0.0],
            'Capital Gains': [0.0, 0.0, 0.0]
        }, index=dates)
        mock_df.index.name = 'Date'

        fetcher = StockFetcher(ticker_symbol="SPY", use_cache=False, source=FakeDataSource(history=mock_df))
        result = fetcher.get_historical_data(period="1wk")

        assert 'timestamp' in result.columns
        # Normalization now uses UTC instead of CST
        assert str(result['timestamp'].dt.tz) == 'UTC'

    def test_get_historical_data_normalization(self):
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=3, tz=est)
        mock_df = pd.DataFrame({
            'Open': [100.0, 101.0, 102.0],
            'High': [105.0, 106.0, 107.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [104.0, 105.0, 106.0],
            'Volume': [1000000, 1100000, 1200000]
        }, index=dates)
        mock_df.index.name = 'Date'

        fetcher = StockFetcher(ticker_symbol="SPY", use_cache=False, source=FakeDataSource(history=mock_df))
        result = fetcher.get_historical_data(period="1mo")

        # Required OHLCV columns
        for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
            assert col in result.columns

        # Action columns are removed during normalization (kept separate)
        assert 'dividends' not in result.columns
        assert 'stock_splits' not in result.columns
        assert 'capital_gains' not in result.columns
        
        assert result['timestamp'].is_monotonic_increasing
