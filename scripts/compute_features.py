"""
Compute features from price bars and upsert to feature_bars (Supabase).

Uses extended lookback: for a requested period (e.g. 3mo), loads at least 1–2 years of bars
so that MA200/ADX etc. are available for the last N bars. Only the computed feature rows
are stored; feature_metadata records sma_long_window_used and availability info.

Usage:
  python -m scripts.compute_features --ticker HOOG --timeframe 1d
  python -m scripts.compute_features --ticker HOOG --timeframe 1d --lookback-period 2y
  python -m scripts.compute_features --ticker HOOG --csv-dir app/historical_data --timeframe 1d
  python -m scripts.compute_features --ticker HOOG --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.database import get_db
from src.db.feature_bars_repo import upsert_feature_rows
from src.features import compute_features, compute_features_for_scoring


DEFAULT_TIMEFRAME = "1d"
DEFAULT_LOOKBACK_PERIOD = "2y"


def _bars_from_csv(csv_dir: Path, ticker: str) -> pd.DataFrame:
    """Load all CSVs for ticker into one DataFrame (timestamp, open, high, low, close, volume)."""
    pattern = f"{ticker}_hist_*.csv"
    paths = sorted(csv_dir.glob(pattern))
    dfs = []
    col_map = {"Date": "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    for p in paths:
        df = pd.read_csv(p)
        for old, new in col_map.items():
            if old in df.columns and new not in df.columns:
                df = df.rename(columns={old: new})
        if "timestamp" not in df.columns:
            continue
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["timestamp"])
        for c in ["open", "high", "low", "close"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    out = pd.concat(dfs, ignore_index=True)
    out = out.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return out


def _bars_from_db(ticker: str, timeframe: str, limit: int = 600) -> pd.DataFrame:
    """Load bars from price_bars table (Supabase)."""
    try:
        resp = (
            get_db()
            .table("price_bars")
            .select("timestamp,open,high,low,close,volume")
            .eq("ticker", ticker)
            .eq("timeframe", timeframe)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return pd.DataFrame()
    if not resp.data:
        return pd.DataFrame()
    df = pd.DataFrame(resp.data)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp")
    return df


def _bars_from_fetch(ticker: str, period: str) -> pd.DataFrame:
    """Fetch bars via yfinance and normalize."""
    from src.data_source import DataSource
    from src.normalization import normalize_candles
    raw = DataSource(ticker).get_history(period)
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = normalize_candles(raw, validate=False)
    if df.empty:
        return pd.DataFrame()
    return df


def feature_df_to_rows(
    feature_df: pd.DataFrame,
    ticker: str,
    timeframe: str,
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Convert feature DataFrame to list of dicts for feature_bars upsert."""
    if feature_df.empty or "timestamp" not in feature_df.columns:
        return []
    rows = []
    feat_cols = [c for c in feature_df.columns if c != "timestamp" and not c.endswith("_available")]
    for _, r in feature_df.iterrows():
        ts = r["timestamp"]
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        row = {
            "ticker": ticker,
            "timeframe": timeframe,
            "timestamp": ts,
            "computed_at": pd.Timestamp.utcnow().isoformat(),
            "feature_metadata": metadata,
        }
        for col in feat_cols:
            val = r.get(col)
            if pd.notna(val):
                row[col] = float(val)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute features and upsert to feature_bars.")
    parser.add_argument("--ticker", type=str, required=True, help="Ticker (e.g. HOOG).")
    parser.add_argument("--timeframe", type=str, default=DEFAULT_TIMEFRAME, help="Bar granularity (default 1d).")
    parser.add_argument("--csv-dir", type=str, default=None, help="Load bars from CSV dir instead of DB/fetch.")
    parser.add_argument("--lookback-period", type=str, default=DEFAULT_LOOKBACK_PERIOD, help="yfinance period when fetching (default 2y).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB.")
    args = parser.parse_args()
    ticker = args.ticker.upper().strip()
    timeframe = args.timeframe or DEFAULT_TIMEFRAME
    if args.csv_dir:
        csv_dir = Path(args.csv_dir)
        if not csv_dir.is_dir():
            print(f"CSV dir not found: {csv_dir}", file=sys.stderr)
            return 1
        df = _bars_from_csv(csv_dir, ticker)
    else:
        df = _bars_from_db(ticker, timeframe)
        if df.empty:
            df = _bars_from_fetch(ticker, args.lookback_period)
    if df.empty:
        print("No price bars to compute features from.")
        return 1
    feature_df, meta = compute_features(df)
    if feature_df.empty:
        print("Feature computation produced no rows.")
        return 1
    rows = feature_df_to_rows(feature_df, ticker, timeframe, meta)
    if not rows:
        print("No rows to upsert.")
        return 0
    if args.dry_run:
        print(f"Dry-run: would upsert {len(rows)} feature rows for {ticker} ({timeframe}). sma_long_window_used={meta.get('sma_long_window_used')}")
        return 0
    try:
        upsert_feature_rows(get_db(), rows)
        print(f"Upserted {len(rows)} feature rows for {ticker} ({timeframe}). sma_long_window_used={meta.get('sma_long_window_used')}")
    except Exception as e:
        print(f"Upsert failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
