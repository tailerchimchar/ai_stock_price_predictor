"""Unit tests for feature computation (src.features)."""

import pandas as pd
import pytest

from src.features import (
    compute_features,
    compute_features_for_scoring,
    _adaptive_long_sma,
    _sma,
    FEATURE_RSI_14,
    FEATURE_SMA_5,
    FEATURE_SMA_20,
    FEATURE_SMA_200,
    FEATURE_ATR_14,
    FEATURE_ADX_14,
)


def make_ohlcv(periods: int, start_price: float = 100.0) -> pd.DataFrame:
    """Deterministic OHLCV with timestamp, open, high, low, close, volume."""
    dates = pd.date_range("2024-01-01", periods=periods, freq="B", tz="UTC")
    close = start_price + pd.Series(range(periods), index=dates).astype(float) * 0.5
    high = close + 1
    low = close - 1
    open_ = close.shift(1).fillna(close.iloc[0])
    volume = 1_000_000
    return pd.DataFrame({
        "timestamp": dates,
        "open": open_.values,
        "high": high.values,
        "low": low.values,
        "close": close.values,
        "volume": [volume] * periods,
    })


def test_compute_features_empty():
    out, meta = compute_features(pd.DataFrame())
    assert out.empty
    assert meta == {}


def test_compute_features_missing_columns():
    df = pd.DataFrame({"timestamp": [1, 2], "close": [100.0, 101.0]})
    out, meta = compute_features(df)
    assert out.empty
    assert meta == {}


def test_compute_features_short_series():
    """With ~25 bars: sma_5, sma_20 should have values; sma_200/sma_100 should be NA."""
    df = make_ohlcv(25)
    out, meta = compute_features(df)
    assert len(out) == 25
    assert out["timestamp"].is_monotonic_increasing
    # Last row: sma_5 and sma_20 should be non-NA
    assert pd.notna(out[FEATURE_SMA_5].iloc[-1])
    assert pd.notna(out[FEATURE_SMA_20].iloc[-1])
    # sma_200 needs 200 bars; we have 25 -> adaptive returns 0, so sma_200 all NA
    assert meta.get("sma_long_window_used") is None or meta.get("sma_long_window_used") == 0
    assert pd.isna(out[FEATURE_SMA_200].iloc[-1])


def test_compute_features_long_series():
    """With 250 bars: sma_200 should be non-NA on last rows; adaptive window = 200."""
    df = make_ohlcv(250)
    out, meta = compute_features(df)
    assert len(out) == 250
    assert meta.get("sma_long_window_used") == 200
    # Last row should have sma_200
    assert pd.notna(out[FEATURE_SMA_200].iloc[-1])
    assert pd.notna(out[FEATURE_RSI_14].iloc[-1])
    assert pd.notna(out[FEATURE_ATR_14].iloc[-1])


def test_adaptive_long_sma():
    close = pd.Series([100.0] * 300, index=pd.RangeIndex(300))
    series, w = _adaptive_long_sma(close)
    assert w == 200
    assert len(series) == 300
    assert series.iloc[-1] == 100.0
    close_short = pd.Series([100.0] * 120, index=pd.RangeIndex(120))
    series2, w2 = _adaptive_long_sma(close_short)
    assert w2 == 100
    assert pd.notna(series2.iloc[-1])


def test_sma_deterministic():
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    s = _sma(close, 3)
    assert s.iloc[2] == 2.0  # (1+2+3)/3
    assert s.iloc[4] == 4.0  # (3+4+5)/3


def test_compute_features_for_scoring():
    df = make_ohlcv(100)
    full, last_n, meta = compute_features_for_scoring(df, score_last_n=10)
    assert len(full) == 100
    assert len(last_n) == 10
    assert last_n["timestamp"].iloc[0] == full["timestamp"].iloc[-10]
    assert last_n["timestamp"].iloc[-1] == full["timestamp"].iloc[-1]


def test_compute_features_monotonic_timestamps():
    df = make_ohlcv(50)
    out, _ = compute_features(df)
    assert out["timestamp"].is_monotonic_increasing


def test_compute_features_no_duplicate_timestamps():
    df = make_ohlcv(30)
    out, _ = compute_features(df)
    assert out["timestamp"].nunique() == len(out)
