"""
Idempotent data cleanup: normalize OHLCV, dedupe, store in price_bars (Supabase).

Reads from CSV dir (per-ticker files) or fetches via yfinance, then:
- Normalizes timestamps to UTC and lowercase columns
- Dedupes by (ticker, timeframe, timestamp); keeps last/most-complete row
- Drops invalid OHLCV rows (high < low, close outside range, non-positive price, negative volume)
- Upserts into public.price_bars (run migration 003 first)

Re-running on the same input does not change DB after first run.

Usage:
  python -m scripts.cleanup_data --ticker HOOG
  python -m scripts.cleanup_data --ticker HOOG --csv-dir app/historical_data
  python -m scripts.cleanup_data --ticker HOOG --timeframe 1d --period 2y
  python -m scripts.cleanup_data --ticker HOOG --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.database import get_db
from src.db.price_bars_repo import upsert_bars
from src.normalization import normalize_candles


DEFAULT_TIMEFRAME = "1d"
DEFAULT_PERIOD = "2y"


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


def _df_to_bar_rows(df: pd.DataFrame, ticker: str, timeframe: str) -> List[Dict[str, Any]]:
    """Convert normalized OHLCV DataFrame to list of dicts for price_bars upsert."""
    if df.empty or "timestamp" not in df.columns:
        return []
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    mask = _valid_ohlcv_mask(df)
    df = df.loc[mask]
    rows = []
    for _, r in df.iterrows():
        ts = r["timestamp"]
        if hasattr(ts, "tz_localize") and ts.tzinfo is None:
            ts = pd.Timestamp(ts).tz_localize("UTC")
        elif hasattr(ts, "tz_convert"):
            ts = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
        row = {
            "ticker": ticker,
            "timeframe": timeframe,
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": int(r.get("volume", 0)),
            "source": "csv",
        }
        if "adjusted_close" in r and pd.notna(r["adjusted_close"]):
            row["adjusted_close"] = float(r["adjusted_close"])
        if "Dividends" in r and pd.notna(r["Dividends"]):
            row["dividends"] = float(r["Dividends"])
        rows.append(row)
    return rows


def _load_from_csv(csv_path: Path, ticker: str, period_from_path: str, timeframe: str) -> pd.DataFrame:
    """Load one CSV, normalize to UTC/lowercase, return DataFrame."""
    df = pd.read_csv(csv_path)
    # Normalize column names (yfinance or already normalized)
    col_map = {"Date": "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    if "timestamp" not in df.columns and "date" in [c.lower() for c in df.columns]:
        df = df.rename(columns={k: "timestamp" for k in df.columns if k.lower() == "date"})
    if "timestamp" not in df.columns:
        return pd.DataFrame()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"])
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    return df


def _parse_ticker_period(path: Path) -> tuple[str | None, str | None]:
    name = path.stem
    m = re.match(r"^([A-Z0-9\.\-]+)_hist_(.+)$", name, re.I)
    if m:
        return m.group(1).upper(), m.group(2)
    return None, None


def run_cleanup_from_csv(csv_dir: Path, ticker: str, timeframe: str) -> List[Dict[str, Any]]:
    """Load all CSVs for ticker from csv_dir, normalize, dedupe (keep last per timestamp), return rows for upsert."""
    pattern = f"{ticker}_hist_*.csv"
    paths = sorted(csv_dir.glob(pattern))
    all_rows: List[Dict[str, Any]] = []
    for p in paths:
        t, per = _parse_ticker_period(p)
        if t != ticker:
            continue
        df = _load_from_csv(p, ticker, per or "", timeframe)
        if df.empty:
            continue
        rows = _df_to_bar_rows(df, ticker, timeframe)
        all_rows.extend(rows)
    if not all_rows:
        return []
    # Dedupe by (ticker, timeframe, timestamp) keeping last
    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["ticker", "timeframe", "timestamp"], keep="last")
    df = df.sort_values("timestamp")
    return df.to_dict("records")


def run_cleanup_from_fetch(ticker: str, period: str, timeframe: str) -> List[Dict[str, Any]]:
    """Fetch history via yfinance, normalize, return rows for upsert."""
    from src.data_source import DataSource
    raw = DataSource(ticker).get_history(period)
    if raw is None or raw.empty:
        return []
    # Use existing normalizer (validate=False so we don't raise on bad rows; we filter later)
    df = normalize_candles(raw, validate=False)
    if df.empty:
        return []
    return _df_to_bar_rows(df, ticker.upper(), timeframe)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup OHLCV data and upsert to price_bars (idempotent).")
    parser.add_argument("--ticker", type=str, required=True, help="Ticker symbol (e.g. HOOG).")
    parser.add_argument("--csv-dir", type=str, default=None, help="Directory with {ticker}_hist_{period}.csv. If omitted, fetch from yfinance.")
    parser.add_argument("--timeframe", type=str, default=DEFAULT_TIMEFRAME, help="Bar granularity (default 1d).")
    parser.add_argument("--period", type=str, default=DEFAULT_PERIOD, help="yfinance period when fetching (default 2y).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB; print row count.")
    args = parser.parse_args()
    ticker = args.ticker.upper().strip()
    timeframe = args.timeframe or DEFAULT_TIMEFRAME
    if args.csv_dir:
        csv_dir = Path(args.csv_dir)
        if not csv_dir.is_dir():
            print(f"CSV dir not found: {csv_dir}", file=sys.stderr)
            return 1
        rows = run_cleanup_from_csv(csv_dir, ticker, timeframe)
    else:
        rows = run_cleanup_from_fetch(ticker, args.period, timeframe)
    if not rows:
        print("No rows to upsert.")
        return 0
    if args.dry_run:
        print(f"Dry-run: would upsert {len(rows)} rows for {ticker} ({timeframe}).")
        return 0
    try:
        upsert_bars(get_db(), rows)
        print(f"Upserted {len(rows)} rows for {ticker} ({timeframe}).")
    except Exception as e:
        print(f"Upsert failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
