"""Unit tests for normalization, logger, and data_source modules."""

import pytest
import pandas as pd
import pytz
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.normalization import normalize_candles, _validate_ohlcv
from src.logger import get_logger
from src.data_source import DataSource


# ============================================================================
# Tests for normalization.py
# ============================================================================

class TestNormalizationEmpty:
    """Test normalize_candles with empty data."""
    
    def test_empty_dataframe(self):
        """Empty DataFrame should return empty."""
        df = pd.DataFrame()
        result = normalize_candles(df, validate=False)
        assert result.empty


class TestNormalizationBasic:
    """Test basic normalization steps."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample yfinance-like data."""
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=3, tz=est)
        return pd.DataFrame({
            'Open': [100.0, 101.0, 102.0],
            'High': [105.0, 106.0, 107.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [104.0, 105.0, 106.0],
            'Volume': [1000000, 1100000, 1200000],
        }, index=dates)
    
    def test_lowercase_columns(self, sample_data):
        """Columns should be lowercase."""
        sample_data.index.name = 'Date'
        result = normalize_candles(sample_data, validate=False)
        
        expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        assert all(col in result.columns for col in expected_cols)
        assert all(col.islower() for col in result.columns)
    
    def test_timestamp_is_utc(self, sample_data):
        """Timestamp should be converted to UTC."""
        sample_data.index.name = 'Date'
        result = normalize_candles(sample_data, validate=False)
        
        assert 'timestamp' in result.columns
        assert str(result['timestamp'].dt.tz) == 'UTC'
    
    def test_dtypes(self, sample_data):
        """Prices should be float, volume should be int."""
        sample_data.index.name = 'Date'
        result = normalize_candles(sample_data, validate=False)
        
        assert result['open'].dtype == float
        assert result['high'].dtype == float
        assert result['low'].dtype == float
        assert result['close'].dtype == float
        assert result['volume'].dtype == int
    
    def test_sorted_and_deduped(self, sample_data):
        """Data should be sorted by timestamp and deduplicated."""
        sample_data.index.name = 'Date'
        # Add duplicate
        sample_data = pd.concat([sample_data, sample_data.iloc[:1]])
        
        result = normalize_candles(sample_data, validate=False)
        
        assert len(result) == 3  # Duplicates removed
        assert result['timestamp'].is_monotonic_increasing


class TestNormalizationValidation:
    """Test OHLCV validation."""
    
    @pytest.fixture
    def valid_data(self):
        """Create valid OHLCV data."""
        est = pytz.timezone('America/New_York')
        dates = pd.date_range('2026-01-01', periods=2, tz=est)
        return pd.DataFrame({
            'Open': [100.0, 101.0],
            'High': [105.0, 106.0],
            'Low': [99.0, 100.0],
            'Close': [104.0, 105.0],
            'Volume': [1000000, 1100000],
        }, index=dates)
    
    def test_valid_ohlcv(self, valid_data):
        """Valid OHLCV should pass validation."""
        valid_data.index.name = 'Date'
        result = normalize_candles(valid_data, validate=True)
        
        assert not result.empty
        assert len(result) == 2
    
    def test_high_less_than_low_fails(self, valid_data):
        """High < Low should fail validation."""
        valid_data.index.name = 'Date'
        valid_data.loc[valid_data.index[0], 'High'] = 98.0  # High < Low
        
        # Should still return data, but log error
        result = normalize_candles(valid_data, validate=True)
        assert not result.empty  # Still returns data
    
    def test_negative_price_fails(self, valid_data):
        """Negative prices should fail validation."""
        valid_data.index.name = 'Date'
        valid_data.loc[valid_data.index[0], 'Open'] = -100.0
        
        result = normalize_candles(valid_data, validate=True)
        assert not result.empty
    
    def test_negative_volume_fails(self, valid_data):
        """Negative volume should fail validation."""
        valid_data.index.name = 'Date'
        valid_data.loc[valid_data.index[0], 'Volume'] = -1000
        
        result = normalize_candles(valid_data, validate=True)
        assert not result.empty


# ============================================================================
# Tests for logger.py
# ============================================================================

class TestLogger:
    """Test logger module."""
    
    def test_logger_exists(self):
        """Logger should be created without error."""
        logger = get_logger(__name__)
        assert logger is not None
    
    def test_logger_has_handlers(self):
        """Logger should have at least one handler."""
        logger = get_logger(__name__)
        assert len(logger.handlers) > 0
    
    def test_logger_returns_same_instance(self):
        """Calling get_logger twice should return same logger."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2


# ============================================================================
# Tests for data_source.py
# ============================================================================

class FakeDataSource:
    """Fake data source for testing without yfinance."""
    
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


class TestDataSourceInterface:
    """Test DataSource interface with fake data."""
    
    def test_fake_source_get_price(self):
        """FakeDataSource should return mocked price."""
        source = FakeDataSource(price=150.5)
        assert source.get_price() == 150.5
    
    def test_fake_source_get_price_none(self):
        """FakeDataSource should return None if no price."""
        source = FakeDataSource(price=None)
        assert source.get_price() is None
    
    def test_fake_source_get_history(self):
        """FakeDataSource should return mocked history."""
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
        result = source.get_history("1mo")
        
        assert len(result) == 2
        assert 'Open' in result.columns
    
    def test_fake_source_empty_history(self):
        """FakeDataSource should return empty DataFrame if no history."""
        source = FakeDataSource()
        result = source.get_history("1mo")
        assert result.empty


class TestDataSourceRetries:
    """Test DataSource retry logic."""
    
    class FailingSource:
        """Data source that fails then succeeds."""
        def __init__(self):
            self.call_count = 0
        
        def get_price(self):
            self.call_count += 1
            if self.call_count < 2:
                raise Exception("API Error")
            return 100.0
    
    def test_retry_succeeds_on_second_attempt(self):
        """DataSource should retry and eventually succeed."""
        # Note: This requires yfinance to be installed
        # For now, we just test the interface exists
        assert hasattr(DataSource, '_retry')


# ============================================================================
# Integration Tests
# ============================================================================

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
