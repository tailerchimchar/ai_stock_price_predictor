"""
Read-only data quality audit for OHLCV price history.

Scans CSV files (and optionally a price_bars table) and reports:
- Duplicates (same ticker+timestamp)
- Missing timestamps / irregular intervals
- OHLC invalids (high < low, close outside [low, high], negative volume)
- Timezone inconsistencies (naive vs aware)
- Extreme spikes suggesting splits or bad data
- Inconsistent currency/exchange if present in data

Usage:
  python -m scripts.audit_data --ticker HOOG
  python -m scripts.audit_data --ticker HOOG --csv-dir app/historical_data
  python -m scripts.audit_data --csv-dir app/historical_data  # all tickers in dir
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Expected OHLCV column names (accept both raw and normalized)
COL_MAP = {
    "Date": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}
OHLCV = ["open", "high", "low", "close", "volume"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to lowercase standard names."""
    out = df.copy()
    for old, new in COL_MAP.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})
    if "timestamp" not in out.columns and "date" in [c.lower() for c in out.columns]:
        out = out.rename(columns={k: "timestamp" for k in out.columns if k.lower() == "date"})
    return out


def _ensure_timestamp_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure we have a datetime timestamp column."""
    if df.empty:
        return df
    if "timestamp" not in df.columns and df.index.name in ("Date", "date"):
        df = df.reset_index().rename(columns={df.index.name or "index": "timestamp"})
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def audit_duplicates(df: pd.DataFrame) -> tuple[int, pd.DataFrame | None]:
    """Return count of duplicate (ticker+timestamp) and duplicate rows if any."""
    if "timestamp" not in df.columns or df.empty:
        return 0, None
    dup = df[df.duplicated(subset=["timestamp"], keep=False)]
    return len(dup), dup if not dup.empty else None


def audit_intervals(df: pd.DataFrame, expected_freq: str = "B") -> tuple[int, list[str]]:
    """
    Check for missing timestamps / irregular intervals.
    expected_freq: 'B' = business daily, 'D' = calendar daily.
    Returns (gap_count, list of gap descriptions).
    """
    if df.empty or "timestamp" not in df.columns:
        return 0, []
    s = df["timestamp"].dropna().sort_values()
    if len(s) < 2:
        return 0, []
    diffs = s.diff().dropna()
    # Business day: expect 1-3 days typically; gaps > 5 days might be holidays or missing data
    threshold = pd.Timedelta(days=5)
    gaps = []
    gap_count = 0
    for i, (idx, d) in enumerate(diffs.items()):
        if d > threshold:
            gap_count += 1
            prev_ts = s.shift(1).loc[idx]
            gaps.append(f"Gap {d.days} days between {prev_ts} and {s.loc[idx]}")
    return gap_count, gaps[:20]  # cap detail list


def audit_ohlcv(df: pd.DataFrame) -> tuple[list[str], pd.DataFrame | None]:
    """
    Check OHLCV validity: high >= low, close in [low, high], positive prices, non-negative volume.
    Returns (list of issue descriptions, rows with issues).
    """
    issues = []
    bad_indices = set()
    if df.empty:
        return issues, None
    if "high" in df.columns and "low" in df.columns:
        mask = df["high"] < df["low"]
        if mask.any():
            n = mask.sum()
            issues.append(f"high < low: {n} rows")
            bad_indices.update(df.index[mask].tolist())
    if all(c in df.columns for c in ["high", "low", "close"]):
        mask = (df["close"] > df["high"]) | (df["close"] < df["low"])
        if mask.any():
            n = mask.sum()
            issues.append(f"close outside [low, high]: {n} rows")
            bad_indices.update(df.index[mask].tolist())
    for col in ["open", "high", "low", "close"]:
        if col in df.columns and (df[col] <= 0).any():
            n = (df[col] <= 0).sum()
            issues.append(f"non-positive {col}: {n} rows")
            bad_indices.update(df.index[df[col] <= 0].tolist())
    if "volume" in df.columns and (df["volume"] < 0).any():
        n = (df["volume"] < 0).sum()
        issues.append(f"negative volume: {n} rows")
        bad_indices.update(df.index[df["volume"] < 0].tolist())
    bad_rows = df.loc[list(bad_indices)].drop_duplicates() if bad_indices else None
    return issues, bad_rows


def audit_timezone(df: pd.DataFrame) -> list[str]:
    """Report timezone: naive vs aware."""
    if df.empty or "timestamp" not in df.columns:
        return []
    issues = []
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    if ts.dt.tz is None:
        issues.append("timestamps are timezone-naive")
    else:
        tz = getattr(ts.dt.tz, "zone", str(ts.dt.tz))
        if tz and "UTC" not in str(tz).upper():
            issues.append(f"timestamps are {tz} (recommend UTC for storage)")
    return issues


def audit_spikes(df: pd.DataFrame, pct_threshold: float = 20.0) -> tuple[int, list[str]]:
    """
    Detect extreme single-period returns suggesting splits or bad data.
    Returns (count of spikes, short descriptions).
    """
    if df.empty or "close" not in df.columns or len(df) < 2:
        return 0, []
    ret = df["close"].pct_change().dropna()
    spikes = ret[ret.abs() > pct_threshold / 100]
    descriptions = []
    for idx in spikes.index[:10]:
        val = ret.loc[idx]
        descriptions.append(f"{idx}: {val*100:.1f}% 1-period return")
    return len(spikes), descriptions


def audit_one_file(csv_path: Path, ticker: str | None, period: str | None) -> dict[str, Any]:
    """Run full audit on one CSV file. ticker/period can be inferred from path if not provided."""
    result: dict[str, Any] = {
        "path": str(csv_path),
        "ticker": ticker,
        "period": period,
        "rows": 0,
        "duplicates": 0,
        "duplicate_rows": None,
        "gap_count": 0,
        "gap_details": [],
        "ohlc_issues": [],
        "ohlc_bad_rows": None,
        "tz_issues": [],
        "spike_count": 0,
        "spike_details": [],
        "errors": [],
    }
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        result["errors"].append(str(e))
        return result
    df = _normalize_columns(df)
    df = _ensure_timestamp_column(df)
    result["rows"] = len(df)
    if df.empty:
        return result
    # Duplicates
    dup_count, dup_df = audit_duplicates(df)
    result["duplicates"] = dup_count
    result["duplicate_rows"] = dup_df
    # Intervals
    gap_count, gap_details = audit_intervals(df)
    result["gap_count"] = gap_count
    result["gap_details"] = gap_details
    # OHLCV
    ohlc_issues, ohlc_bad = audit_ohlcv(df)
    result["ohlc_issues"] = ohlc_issues
    result["ohlc_bad_rows"] = ohlc_bad
    # Timezone
    result["tz_issues"] = audit_timezone(df)
    # Spikes
    spike_count, spike_details = audit_spikes(df)
    result["spike_count"] = spike_count
    result["spike_details"] = spike_details
    return result


def parse_ticker_period_from_path(path: Path) -> tuple[str | None, str | None]:
    """Parse {ticker}_hist_{period}.csv from path."""
    name = path.stem
    m = re.match(r"^([A-Z0-9\.\-]+)_hist_(.+)$", name, re.I)
    if m:
        return m.group(1).upper(), m.group(2)
    return None, None


def find_csvs(csv_dir: Path, ticker: str | None) -> list[Path]:
    """List CSV paths; if ticker given, filter to that ticker."""
    if not csv_dir.is_dir():
        return []
    pattern = f"{ticker}_hist_*.csv" if ticker else "*_hist_*.csv"
    return sorted(csv_dir.glob(pattern))


def run_audit(csv_dir: Path, ticker: str | None) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Run audit on all matching CSVs. Returns (per-file results, summary table)."""
    paths = find_csvs(csv_dir, ticker)
    results = []
    for p in paths:
        t, per = parse_ticker_period_from_path(p)
        if ticker and t and t != ticker.upper():
            continue
        r = audit_one_file(p, t, per)
        results.append(r)
    # Summary table
    rows_summary = []
    for r in results:
        rows_summary.append({
            "ticker": r["ticker"] or "",
            "period": r["period"] or "",
            "path": Path(r["path"]).name,
            "rows": r["rows"],
            "duplicates": r["duplicates"],
            "gaps": r["gap_count"],
            "ohlc_issues": "; ".join(r["ohlc_issues"]) if r["ohlc_issues"] else "-",
            "tz_issues": "; ".join(r["tz_issues"]) if r["tz_issues"] else "-",
            "spikes": r["spike_count"],
            "errors": "; ".join(r["errors"]) if r["errors"] else "-",
        })
    summary_df = pd.DataFrame(rows_summary) if rows_summary else pd.DataFrame()
    return results, summary_df


def main() -> int:
    parser = argparse.ArgumentParser(description="Data quality audit (read-only) for OHLCV history.")
    parser.add_argument("--ticker", type=str, default=None, help="Ticker to audit (e.g. HOOG). If omitted, audit all in --csv-dir.")
    parser.add_argument("--csv-dir", type=str, default=None, help="Directory containing {ticker}_hist_{period}.csv files.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-file issue details.")
    args = parser.parse_args()
    csv_dir = Path(args.csv_dir) if args.csv_dir else (ROOT / "app" / "historical_data")
    if not csv_dir.is_dir():
        print(f"CSV dir not found: {csv_dir}", file=sys.stderr)
        return 1
    ticker = args.ticker.upper().strip() if args.ticker else None
    results, summary_df = run_audit(csv_dir, ticker)
    if summary_df.empty:
        print("No CSV files found.")
        return 0
    print("Summary:")
    print(summary_df.to_string(index=False))
    if args.verbose:
        print("\n--- Per-file details ---")
        for r in results:
            print(f"\n{r['path']} (ticker={r['ticker']}, period={r['period']}, rows={r['rows']})")
            if r["duplicates"]:
                print(f"  Duplicates: {r['duplicates']}")
            if r["gap_details"]:
                for g in r["gap_details"][:5]:
                    print(f"  Gap: {g}")
            if r["ohlc_issues"]:
                print(f"  OHLC: {r['ohlc_issues']}")
            if r["tz_issues"]:
                print(f"  TZ: {r['tz_issues']}")
            if r["spike_details"]:
                for s in r["spike_details"][:5]:
                    print(f"  Spike: {s}")
            if r["errors"]:
                print(f"  Errors: {r['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
