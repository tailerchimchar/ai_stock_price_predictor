"""Unit tests for caching module."""

import pytest
import pandas as pd
import time
from pathlib import Path
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.caching import Cache


class TestCacheBasics:
    """Test basic cache operations."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_cache_init_creates_directory(self, temp_cache_dir):
        """Cache should create directory on init."""
        cache_path = Path(temp_cache_dir) / "test_cache"
        cache = Cache(cache_dir=str(cache_path))
        
        assert cache_path.exists()
        assert cache_path.is_dir()
    
    def test_cache_set_and_get(self, temp_cache_dir):
        """Should be able to set and get cached values."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        
        assert result == "test_value"
    
    def test_cache_get_nonexistent(self, temp_cache_dir):
        """Getting nonexistent key should return None."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        result = cache.get("nonexistent_key")
        
        assert result is None
    
    def test_cache_dataframe(self, temp_cache_dir):
        """Should be able to cache DataFrames."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        cache.set("df_key", df)
        result = cache.get("df_key")
        
        assert isinstance(result, pd.DataFrame)
        assert result.equals(df)
    
    def test_cache_numeric_types(self, temp_cache_dir):
        """Should be able to cache numeric types."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        cache.set("float_key", 123.45)
        cache.set("int_key", 42)
        
        assert cache.get("float_key") == 123.45
        assert cache.get("int_key") == 42


class TestCacheTTL:
    """Test cache TTL (time-to-live) behavior."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_cache_expires_after_ttl(self, temp_cache_dir):
        """Cache should expire after TTL."""
        # TTL of 1 second for testing
        cache = Cache(cache_dir=temp_cache_dir, ttl_hours=1/3600)
        
        cache.set("expiring_key", "value")
        time.sleep(1.5)  # Wait for expiration
        
        result = cache.get("expiring_key")
        assert result is None
    
    def test_cache_valid_before_ttl(self, temp_cache_dir):
        """Cache should be valid before TTL expires."""
        cache = Cache(cache_dir=temp_cache_dir, ttl_hours=24)
        
        cache.set("valid_key", "value")
        result = cache.get("valid_key")
        
        assert result == "value"


class TestCacheClear:
    """Test cache clearing operations."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_clear_specific_key(self, temp_cache_dir):
        """Should be able to clear a specific key."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear("key1")
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
    
    def test_clear_all(self, temp_cache_dir):
        """Should be able to clear all cache entries."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()  # Clear all
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_clear_nonexistent_key(self, temp_cache_dir):
        """Clearing nonexistent key should not raise error."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        cache.clear("nonexistent_key")  # Should not raise


class TestCacheErrorHandling:
    """Test cache error handling."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_cache_handles_unpicklable_object(self, temp_cache_dir):
        """Cache should handle errors gracefully."""
        cache = Cache(cache_dir=temp_cache_dir)
        
        # Lambda functions can't be pickled
        try:
            cache.set("bad_key", lambda x: x)
        except:
            pass  # Should handle error gracefully
        
        # Cache should still work
        cache.set("good_key", "value")
        assert cache.get("good_key") == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
