"""
Convert OHLCV DataFrame to price_bars rows for upsert.
Reuses logic from cleanup script: valid OHLCV mask, dedupe by timestamp.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


def _valid_ohlcv_mask(df: pd.DataFrame) -> pd.Series:
    """Boolean mask: True for rows that pass OHLCV validity."""
    if df.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(True, index=df.index)
    if "high" in df.columns and "low" in df.columns:
        mask &= df["high"] >= df["low"]
    if all(c in df.columns for c in ["high", "low", "close"]):
        mask &= (df["close"] >= df["low"]) & (df["close"] <= df["high"])
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            mask &= df[col] > 0
    if "volume" in df.columns:
        mask &= df["volume"] >= 0
    return mask


def ohlcv_df_to_price_bar_rows(
    df: pd.DataFrame,
    ticker: str,
    timeframe: str = "1d",
    source: str = "yfinance",
) -> List[Dict[str, Any]]:
    """
    Convert OHLCV DataFrame (timestamp, open, high, low, close, volume) to list of dicts for price_bars upsert.
    Drops invalid rows and dedupes by timestamp (keep last).
    """
    if df is None or df.empty or "timestamp" not in df.columns:
        return []
    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return []
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    mask = _valid_ohlcv_mask(df)
    df = df.loc[mask]
    rows = []
    for _, r in df.iterrows():
        ts = r["timestamp"]
        if hasattr(ts, "tz_localize") and ts.tzinfo is None:
            ts = pd.Timestamp(ts).tz_localize("UTC")
        elif hasattr(ts, "tz_convert") and ts.tzinfo is not None:
            ts = ts.tz_convert("UTC")
        row = {
            "ticker": ticker,
            "timeframe": timeframe,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": int(r.get("volume", 0)),
            "source": source,
        }
        if "adjusted_close" in r and pd.notna(r.get("adjusted_close")):
            row["adjusted_close"] = float(r["adjusted_close"])
        if "Dividends" in r and pd.notna(r.get("Dividends")):
            row["dividends"] = float(r["Dividends"])
        rows.append(row)
    return rows
