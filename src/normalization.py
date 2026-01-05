"""Normalization module - handles data cleaning and standardization.

OHLCV = Open, High, Low, Close, Volume (standard candlestick data)
"""

import pandas as pd
from .logger import get_logger

logger = get_logger(__name__)

def normalize_candles(df: pd.DataFrame, validate: bool = True) -> pd.DataFrame:
    """
    Normalize yfinance data to production-ready format.
    
    Steps:
    1. Convert Date index to timestamp column
    2. Convert timezone to UTC (standard for time series)
    3. Rename columns to lowercase
    4. Validate OHLCV relationships
    5. Clean dtypes and remove duplicates
    
    Args:
        df: Raw yfinance DataFrame
        validate: Perform strict OHLCV validation (default True)
        
    Returns:
        Normalized DataFrame with UTC timestamps and validated OHLCV
    """
    if df.empty:
        logger.warning("Empty DataFrame provided to normalize_candles")
        return df

    # Step 1: Convert index to timestamp column
    df = df.reset_index().rename(columns={'Date': 'timestamp'})
    
    # Step 2: Convert to UTC (standard for storage)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_convert('UTC')
    else:
        # Assume US market timezone (EST/EDT)
        df['timestamp'] = df['timestamp'].dt.tz_localize('America/New_York').dt.tz_convert('UTC')
    
    # Step 3: Rename to lowercase
    df = df.rename(columns={
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume',
    })
    
    # Step 4: Validate OHLCV
    if validate:
        _validate_ohlcv(df)
    
    # Step 5: Clean and sort
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    if 'volume' in df.columns:
        df['volume'] = df['volume'].astype(int)
    
    df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
    
    logger.info(f"Normalized {len(df)} candles to UTC")
    return df


def _validate_ohlcv(df: pd.DataFrame) -> None:
    """
    Validate OHLCV data quality.
    
    Checks:
    - High >= Low, Open, Close
    - Low <= Open, Close
    - All prices > 0
    - Volume >= 0
    """
    issues = []
    
    # High should be the highest price in the candle
    if (df['high'] < df['low']).any():
        count = (df['high'] < df['low']).sum()
        issues.append(f"High < Low in {count} candles")
    
    if (df['high'] < df['open']).any():
        count = (df['high'] < df['open']).sum()
        issues.append(f"High < Open in {count} candles")
    
    if (df['high'] < df['close']).any():
        count = (df['high'] < df['close']).sum()
        issues.append(f"High < Close in {count} candles")
    
    # Low should be the lowest price in the candle
    if (df['low'] > df['open']).any():
        count = (df['low'] > df['open']).sum()
        issues.append(f"Low > Open in {count} candles")
    
    if (df['low'] > df['close']).any():
        count = (df['low'] > df['close']).sum()
        issues.append(f"Low > Close in {count} candles")
    
    # Prices should be positive
    price_cols = ['open', 'high', 'low', 'close']
    if (df[price_cols] <= 0).any().any():
        issues.append("Found non-positive prices")
    
    # Volume should be non-negative
    if (df['volume'] < 0).any():
        count = (df['volume'] < 0).sum()
        issues.append(f"Negative volume in {count} candles")
    
    if issues:
        logger.error(f"OHLCV validation failed: {'; '.join(issues)}")
    else:
        logger.info("✓ OHLCV validation passed")
