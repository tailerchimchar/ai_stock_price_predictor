"""Repository for price_bars table (OHLCV)."""

from typing import Any, Dict, List

from supabase import Client as DB

TABLE_NAME = "price_bars"
UNIQUE_COLS = "ticker,timeframe,timestamp"


def upsert_bars(db: DB, rows: List[Dict[str, Any]]) -> int:
    """
    Upsert OHLCV rows into price_bars. Idempotent: same (ticker, timeframe, timestamp) overwrites.
    Each row must have: ticker, timeframe, timestamp, open, high, low, close, volume.
    Optional: adjusted_close, dividends, splits, source.
    timestamp: ISO string or datetime; stored as UTC.
    Returns number of rows in request (Supabase returns inserted/updated count in response).
    """
    if not rows:
        return 0
    # Ensure timestamp is ISO string for JSON
    for r in rows:
        ts = r.get("timestamp")
        if hasattr(ts, "isoformat"):
            r["timestamp"] = ts.isoformat()
    resp = (
        db.table(TABLE_NAME)
        .upsert(rows, on_conflict=UNIQUE_COLS, returning="minimal")
        .execute()
    )
    return len(rows)
