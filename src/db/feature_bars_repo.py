"""Repository for feature_bars table (computed indicators)."""

from typing import Any, Dict, List

from supabase import Client as DB

TABLE_NAME = "feature_bars"
UNIQUE_COLS = "ticker,timeframe,timestamp"


def upsert_feature_rows(db: DB, rows: List[Dict[str, Any]]) -> int:
    """
    Upsert feature rows into feature_bars. Idempotent.
    Each row: ticker, timeframe, timestamp, plus optional rsi_14, sma_5, ... feature_metadata.
    """
    if not rows:
        return 0
    for r in rows:
        ts = r.get("timestamp")
        if hasattr(ts, "isoformat"):
            r["timestamp"] = ts.isoformat()
    db.table(TABLE_NAME).upsert(rows, on_conflict=UNIQUE_COLS, returning="minimal").execute()
    return len(rows)
