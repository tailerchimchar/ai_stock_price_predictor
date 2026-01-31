"""Repository for feature_bars table (computed indicators)."""

from typing import Any, Dict, List

from supabase import Client as DB

TABLE_NAME = "feature_bars"
UNIQUE_COLS = "ticker,timeframe,timestamp"


def upsert_feature_rows(db: DB, rows: List[Dict[str, Any]]) -> int:
    """
    Upsert feature rows into feature_bars. Idempotent.
    Each row: ticker, timeframe, timestamp, computed_at, feature_metadata, and features (jsonb dict).
    """
    if not rows:
        return 0
    for r in rows:
        ts = r.get("timestamp")
        if hasattr(ts, "isoformat"):
            r["timestamp"] = ts.isoformat()
    db.table(TABLE_NAME).upsert(rows, on_conflict=UNIQUE_COLS, returning="minimal").execute()
    return len(rows)


def get_latest_feature_bars(
    db: DB,
    ticker: str,
    timeframe: str,
    limit: int = 1,
) -> List[Dict[str, Any]]:
    """
    Return the latest feature_bars rows for (ticker, timeframe), newest first.
    Each row includes features (jsonb) and feature_metadata.
    """
    resp = (
        db.table(TABLE_NAME)
        .select("timestamp,features,feature_metadata,computed_at")
        .eq("ticker", ticker)
        .eq("timeframe", timeframe)
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return list(resp.data) if resp.data else []
