from typing import Optional
import pandas as pd

from .data_source import DataSource
from .normalization import normalize_candles
from .caching import Cache

class StockFetcher:
    """Main interface for stock data with optional caching."""

    def __init__(self, ticker_symbol: str, use_cache: bool = True, source: Optional[DataSource] = None, cache: Optional[Cache] = None):
        self.ticker_symbol = ticker_symbol
        self.use_cache = use_cache
        self.source = source or DataSource(self.ticker_symbol)
        self.cache = None
        if use_cache:
            self.cache = cache or Cache()    
            
    def fetch_price(self) -> Optional[float]:
        """Get current stock price."""
        cache_key = f"{self.ticker_symbol}_price"
        
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            price = self.source.get_price()
        except Exception:
            return None
        
        if self.cache and price is not None:
            self.cache.set(cache_key, price)
        
        return price
    
    def get_historical_data(self, period: str = "1mo") -> pd.DataFrame:
        """Get normalized historical OHLCV data."""
        cache_key = f"{self.ticker_symbol}_hist_{period}"
        
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        
        data = normalize_candles(self.source.get_history(period))
        
        if self.cache and not data.empty:
            self.cache.set(cache_key, data)
        
        return data
    
    def get_financials(self) -> pd.DataFrame:
        """Get financial statements."""
        return self.source.get_financials()
    
    def get_actions(self) -> pd.DataFrame:
        """Get dividends and stock splits."""
        return self.source.get_actions()
    
    def __str__(self):
        return f"StockFetcher(ticker_symbol={self.ticker_symbol})"
    
    class Config:
        arbitrary_types_allowed = True

  