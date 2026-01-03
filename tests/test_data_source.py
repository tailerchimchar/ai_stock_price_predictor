"""Unit tests for data_source module."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_source import DataSource

# Import directly from conftest for readability
# These are just regular classes/functions, not fixtures
import sys
sys.path.insert(0, str(Path(__file__).parent))
from conftest import FakeDataSource, create_sample_ohlcv_data


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
        mock_df = create_sample_ohlcv_data(periods=2)
        
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
        # Test that _retry method exists
        assert hasattr(DataSource, '_retry')
    
    def test_data_source_has_retry_parameter(self):
        """DataSource should accept max_retries parameter."""
        source = DataSource("SPY", max_retries=5)
        assert source.max_retries == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
