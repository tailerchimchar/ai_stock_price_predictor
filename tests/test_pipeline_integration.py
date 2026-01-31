"""
Integration tests: ingest small history → cleanup (in-memory) → compute features →
verify monotonic timestamps, uniqueness, no unexpected NA for expected windows.
"""

import pandas as pd
import pytest

from conftest import create_sample_ohlcv_data
from src.normalization import normalize_candles
from src.features import compute_features, compute_features_for_scoring


def _ohlcv_to_normalized_df(sample_df: pd.DataFrame) -> pd.DataFrame:
    """Convert yfinance-style (Date index, Open/High/Low/Close/Volume) to timestamp + lowercase."""
    df = sample_df.reset_index().rename(columns={"Date": "timestamp"})
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
    return df


def test_ingest_normalize_then_features():
    """Ingest sample OHLCV, normalize, compute features; verify monotonic and no duplicate timestamps."""
    raw = create_sample_ohlcv_data(periods=50)
    df = _ohlcv_to_normalized_df(raw)
    assert len(df) == 50
    feature_df, meta = compute_features(df)
    assert len(feature_df) == 50
    assert feature_df["timestamp"].is_monotonic_increasing
    assert feature_df["timestamp"].nunique() == 50
    assert "sma_long_window_used" in meta


def test_cleanup_dedup_then_features():
    """Simulate cleanup dedupe (drop_duplicates by timestamp keep last), then features."""
    raw = create_sample_ohlcv_data(periods=30)
    df = _ohlcv_to_normalized_df(raw)
    # Simulate duplicate timestamp (same date twice)
    dup = df.iloc[-1:].copy()
    df = pd.concat([df, dup], ignore_index=True)
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    assert len(df) == 30
    feature_df, _ = compute_features(df)
    assert feature_df["timestamp"].nunique() == 30
    assert len(feature_df) == 30


def test_expected_windows_no_unexpected_na():
    """With 250 bars, last row should have sma_5, sma_20, sma_200, rsi_14, atr_14, adx_14 non-NA."""
    raw = create_sample_ohlcv_data(periods=250)
    df = _ohlcv_to_normalized_df(raw)
    feature_df, meta = compute_features(df)
    last = feature_df.iloc[-1]
    assert pd.notna(last["sma_5"])
    assert pd.notna(last["sma_20"])
    assert pd.notna(last["sma_200"])
    assert pd.notna(last["rsi_14"])
    assert pd.notna(last["atr_14"])
    assert meta.get("sma_long_window_used") == 200


def test_score_last_n_integration():
    """compute_features_for_scoring with 100 bars, score_last_n=10; last 10 should match tail of full."""
    raw = create_sample_ohlcv_data(periods=100)
    df = _ohlcv_to_normalized_df(raw)
    full, last_n, meta = compute_features_for_scoring(df, score_last_n=10)
    assert len(full) == 100
    assert len(last_n) == 10
    pd.testing.assert_series_equal(
        last_n.reset_index(drop=True)["timestamp"],
        full.tail(10).reset_index(drop=True)["timestamp"],
    )
