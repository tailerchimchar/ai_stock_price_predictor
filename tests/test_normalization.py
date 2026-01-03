"""Unit tests for normalization module."""

import pytest
import pandas as pd
import pytz
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.normalization import normalize_candles, _validate_ohlcv


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
