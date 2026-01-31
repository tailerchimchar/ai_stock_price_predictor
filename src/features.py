"""
Robust feature computation with extended lookback and adaptive windows.

- Standard names: rsi_14, sma_5, sma_20, sma_100, sma_200, atr_14, adx_14, bbands_20_2, etc.
- Per-row availability: insufficient_history mask so UI can show "insufficient history" instead of NA.
- Adaptive MAs: if MA200 unavailable, compute MA150/100 and record which length was used in metadata.
- Expects OHLCV DataFrame with columns: timestamp, open, high, low, close, volume (UTC, sorted).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange, BollingerBands

# Standard feature names
FEATURE_RSI_14 = "rsi_14"
FEATURE_SMA_5 = "sma_5"
FEATURE_SMA_20 = "sma_20"
FEATURE_SMA_100 = "sma_100"
FEATURE_SMA_200 = "sma_200"
FEATURE_ATR_14 = "atr_14"
FEATURE_ADX_14 = "adx_14"
FEATURE_BBANDS_20_2 = "bbands_20_2"  # middle band width; we store upper/middle/lower or just middle
FEATURE_MACD_12_26_9 = "macd_12_26_9"  # optional; store macd line value

# Long MA fallback order when insufficient bars for 200
LONG_MA_FALLBACK_WINDOWS = [200, 150, 100]
MIN_BARS_RSI = 2
MIN_BARS_ADX = 28  # 2 * 14
MIN_BARS_ATR = 14
MIN_BARS_BB = 20
MIN_BARS_MACD = 34  # 26 + 9 - 1 approx


def _sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window).mean()


def _adaptive_long_sma(close: pd.Series) -> Tuple[pd.Series, int]:
    """Compute longest feasible SMA from [200, 150, 100]; return (series, window_used)."""
    for w in LONG_MA_FALLBACK_WINDOWS:
        if len(close) >= w:
            return _sma(close, w), w
    return pd.Series(index=close.index, dtype=float), 0


def compute_rsi_14(close: pd.Series) -> pd.Series:
    """RSI with window 14. Standard name: rsi_14."""
    return RSIIndicator(close=close, window=14).rsi()


def compute_atr_14(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """ATR with window 14. Standard name: atr_14."""
    return AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()


def compute_adx_14(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """ADX with window 14. Standard name: adx_14."""
    return ADXIndicator(high=high, low=low, close=close, window=14).adx()


def compute_bbands_20_2(close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands (20, 2). Returns (upper, middle, lower). We store middle as bbands_20_2 or all three."""
    bb = BollingerBands(close=close, window=20, window_dev=2)
    return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()


def compute_macd_12_26_9(close: pd.Series) -> pd.Series:
    """MACD line (12, 26, 9). Standard name: macd_12_26_9 (value = macd line)."""
    from ta.trend import MACD
    macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    return macd.macd()


def compute_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Compute all features on OHLCV DataFrame (timestamp, open, high, low, close, volume).
    Returns (feature DataFrame with one row per bar, metadata dict).
    Metadata includes: sma_long_window_used (200/150/100), and per-feature availability info.
    Rows with insufficient history have NaN for that feature; metadata records which features need more bars.
    """
    if df.empty or not {"timestamp", "open", "high", "low", "close"}.issubset(df.columns):
        return pd.DataFrame(), {}
    df = df.sort_values("timestamp").reset_index(drop=True)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    out = pd.DataFrame({"timestamp": df["timestamp"]})
    meta: Dict[str, Any] = {}

    # SMA 5, 20
    out[FEATURE_SMA_5] = _sma(close, 5)
    out[FEATURE_SMA_20] = _sma(close, 20)
    # Adaptive long SMA
    long_sma, long_w = _adaptive_long_sma(close)
    out[FEATURE_SMA_100] = _sma(close, 100) if len(close) >= 100 else pd.Series(dtype=float)
    out[FEATURE_SMA_200] = long_sma
    meta["sma_long_window_used"] = long_w if long_w else None

    # RSI 14
    rsi = compute_rsi_14(close)
    out[FEATURE_RSI_14] = rsi
    meta["rsi_14_available_from_bar"] = MIN_BARS_RSI

    # ATR 14
    atr = compute_atr_14(high, low, close)
    out[FEATURE_ATR_14] = atr

    # ADX 14
    adx = compute_adx_14(high, low, close)
    out[FEATURE_ADX_14] = adx

    # Bollinger middle (20, 2)
    try:
        _, bb_mid, _ = compute_bbands_20_2(close)
        out[FEATURE_BBANDS_20_2] = bb_mid
    except Exception:
        out[FEATURE_BBANDS_20_2] = pd.NA

    # MACD line (optional)
    try:
        out[FEATURE_MACD_12_26_9] = compute_macd_12_26_9(close)
    except Exception:
        out[FEATURE_MACD_12_26_9] = pd.NA

    # Feature availability mask: which bars have "insufficient history" for each feature
    meta["insufficient_history_bars"] = {
        FEATURE_SMA_5: 5,
        FEATURE_SMA_20: 20,
        FEATURE_SMA_100: 100,
        FEATURE_SMA_200: long_w or 200,
        FEATURE_RSI_14: 15,
        FEATURE_ATR_14: 15,
        FEATURE_ADX_14: MIN_BARS_ADX,
        FEATURE_BBANDS_20_2: MIN_BARS_BB,
        FEATURE_MACD_12_26_9: MIN_BARS_MACD,
    }
    return out, meta


def feature_availability_mask(feature_df: pd.DataFrame, metadata: Dict[str, Any]) -> pd.DataFrame:
    """
    Add a column per feature indicating whether the value is available (True) or insufficient history (False).
    Column names: {feature}_available.
    """
    if feature_df.empty or not metadata.get("insufficient_history_bars"):
        return feature_df
    out = feature_df.copy()
    for feat, min_bars in metadata["insufficient_history_bars"].items():
        if feat not in out.columns:
            continue
        # First min_bars-1 rows are NaN / insufficient
        avail = out[feat].notna()
        out[f"{feat}_available"] = avail
    return out


def compute_features_for_scoring(
    df: pd.DataFrame,
    score_last_n: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Compute features on full lookback df; return (full feature DataFrame, last_n rows for scoring, metadata).
    If score_last_n is None, score_last_n = len(df). Use this when you fetch 2y of bars but only score last 3mo.
    """
    feature_df, meta = compute_features(df)
    if feature_df.empty:
        return feature_df, pd.DataFrame(), meta
    n = score_last_n if score_last_n is not None else len(feature_df)
    n = min(n, len(feature_df))
    last_df = feature_df.tail(n)
    return feature_df, last_df, meta
