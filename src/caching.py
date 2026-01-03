"""Caching module - simple file-based cache with logging."""

import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional
from .logger import get_logger

logger = get_logger(__name__)


class Cache:
    """Simple file-based cache with TTL and logging."""
    
    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        logger.info(f"Cache initialized at {self.cache_dir} with TTL={ttl_hours}h")
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        path = self.cache_dir / f"{key}.pkl"
        
        if not path.exists():
            logger.debug(f"Cache miss: {key} (file not found)")
            return None
        
        # Check expiration
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age > self.ttl:
            logger.debug(f"Cache expired: {key} (age={age})")
            path.unlink()
            return None
        
        try:
            with open(path, 'rb') as f:
                value = pickle.load(f)
            logger.info(f"Cache hit: {key} (age={age})")
            return value
        except Exception as e:
            logger.error(f"Cache read error for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Cache a value."""
        try:
            with open(self.cache_dir / f"{key}.pkl", 'wb') as f:
                pickle.dump(value, f)
            logger.info(f"Cache set: {key}")
        except Exception as e:
            logger.error(f"Cache write error for {key}: {e}")
    
    def clear(self, key: Optional[str] = None) -> None:
        """Clear cache (all or specific key)."""
        if key:
            path = self.cache_dir / f"{key}.pkl"
            if path.exists():
                path.unlink()
                logger.info(f"Cache cleared: {key}")
            else:
                logger.debug(f"Cache clear: {key} (not found)")
        else:
            count = len(list(self.cache_dir.glob("*.pkl")))
            for f in self.cache_dir.glob("*.pkl"):
                f.unlink()
            logger.info(f"Cache cleared all ({count} files)")
