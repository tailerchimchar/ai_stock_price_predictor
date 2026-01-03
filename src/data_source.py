"""Data source module - handles API calls to yfinance."""

import yfinance as yf
import pandas as pd
from typing import Optional
import time
from .logger import get_logger

logger = get_logger(__name__)


class DataSource:
    """Simple wrapper around yfinance API with retries."""
    
    def __init__(self, ticker: str, max_retries: int = 3):
        self.ticker = ticker
        self._yf = yf.Ticker(ticker)
        self.max_retries = max_retries
    
    def _retry(self, func, *args, **kwargs):
        """Execute function with retry logic and exponential backoff."""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Attempt {attempt}/{self.max_retries} for {func.__name__}")
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed after {self.max_retries} attempts: {e}")
                    raise
                wait_time = 2 ** (attempt - 1)  # Exponential backoff
                logger.warning(f"Attempt {attempt} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
    
    def get_price(self) -> Optional[float]:
        """Fetch current market price with retries."""
        try:
            price = self._retry(lambda: self._yf.info.get('regularMarketPrice'))
            if price:
                logger.info(f"Fetched price for {self.ticker}: ${price}")
            else:
                logger.warning(f"No price data available for {self.ticker}")
            return price
        except Exception as e:
            logger.error(f"Error fetching price for {self.ticker}: {e}")
            return None
    
    def get_history(self, period: str) -> pd.DataFrame:
        """Fetch historical OHLCV data with retries."""
        try:
            data = self._retry(lambda: self._yf.history(period=period))
            logger.info(f"Fetched {len(data)} candles for {self.ticker} ({period})")
            return data
        except Exception as e:
            logger.error(f"Error fetching history for {self.ticker}: {e}")
            return pd.DataFrame()
    
    def get_financials(self) -> pd.DataFrame:
        """Fetch financial statements with retries."""
        try:
            data = self._retry(lambda: self._yf.financials)
            logger.info(f"Fetched financials for {self.ticker}")
            return data
        except Exception as e:
            logger.error(f"Error fetching financials for {self.ticker}: {e}")
            return pd.DataFrame()
    
    def get_actions(self) -> pd.DataFrame:
        """Fetch dividends and stock splits with retries."""
        try:
            data = self._retry(lambda: self._yf.actions)
            logger.info(f"Fetched actions for {self.ticker}")
            return data
        except Exception as e:
            logger.error(f"Error fetching actions for {self.ticker}: {e}")
            return pd.DataFrame()
