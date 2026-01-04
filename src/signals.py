import pandas as pd
from typing import Optional
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
# from ta.volatility import AverageTrueRange

class StockSignals():
  def __init__(self, history: pd.DataFrame):
    self.history = history
    
  def moving_average(self, window: int = 5) -> pd.Series:
    """Calculate moving average of closing prices based on a window size."""
    return self.history['close'].rolling(window=window).mean()
  
  def compute_signals(self) -> dict:
    """Compute various stock signals and return as a dictionary."""
    signals = {
      'ma_5': float(f"{self.moving_average(window=5).iloc[-1]:.2f}"),
      'ma_20': float(f"{self.moving_average(window=20).iloc[-1]:.2f}"),
      'ma_100': float(f"{self.moving_average(window=100).iloc[-1]:.2f}"),
      'ma_200': float(f"{self.moving_average(window=200).iloc[-1]:.2f}"),
      'percent_price_change': self.get_last_five_days_percent_change(),
      'rsi': self._calculate_rsi(),
      #'volatility': self._calculate_volatility(),
      'adx': self._calculate_adx(),
      'first_close': float(f"{self.history['close'].iloc[0]:.2f}"),
      'last_close': float(f"{self.history['close'].iloc[-1]:.2f}"),
      'window': len(self.history),
      'period_high': float(f"{self.history['high'].max():.2f}"),
      'period_low': float(f"{self.history['low'].min():.2f}"),
    }
    return signals
  
  # Short term momentum
  def get_last_five_days_percent_change(self) -> float:
    if( len(self.history) < 6):
      return 0.0
    """Get the difference between the last closing price and the first closing price."""
    first_close = float(f"{self.history['close'].iloc[-6]}")
    last_close = float(f"{self.history['close'].iloc[-1]}")
    return float(f"{(last_close / first_close) - 1}")
  
  def _calculate_rsi(self) -> Optional[float]:
    """Compute RSI over the full available window (capped at 14 for stability)."""
    if self.history.empty or 'close' not in self.history.columns:
      return None
    window = min(len(self.history), 14)
    if window < 2:
      return None
    rsi_series = RSIIndicator(close=self.history['close'], window=window).rsi()
    return float(rsi_series.iloc[-1]) if not rsi_series.empty else None
  
  def _calculate_adx(self, window: int = 14) -> Optional[float]:
    """Calculate ADX (Average Directional Index) to measure trend strength."""
    if self.history.empty or not {'high', 'low', 'close'} <= set(self.history.columns):
      return None

    # ADX needs at least 2x window to calculate properly
    min_rows = window * 2
    if len(self.history) < min_rows:
      return None
    
    try:
      adx_series = ADXIndicator(
        high=self.history['high'],
        low=self.history['low'],
        close=self.history['close'],
        window=window
      ).adx()
    
      return float(f"{adx_series.iloc[-1]:.2f}") if not adx_series.empty else None
  
    except (IndexError, ValueError):
      return None