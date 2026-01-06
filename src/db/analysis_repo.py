from typing import Any, Dict, List, Optional
from supabase import Client as DB
from src.db.database import TABLE_NAME


def insert_analysis(db: DB, *, result: Dict[str, Any]) -> str:
    """Upsert a single analysis row; return its id as string."""
    resp = (
        db.table(TABLE_NAME)
        .upsert(result, on_conflict="ticker,period", returning="representation")
        .execute()
    )
    row = resp.data[0] if resp.data else {}
    return str(row.get("id", ""))


def list_analyses(db: DB, *, ticker: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List analyses for a ticker, newest first."""
    q = (
        db.table(TABLE_NAME)
        .select("*")
        .eq("ticker", ticker)
        .order("created_at", desc=True)
        .limit(limit)
    )
    return q.execute().data or []


def get_latest_analysis(db: DB, *, ticker: str, period: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch the latest analysis for a ticker (optionally filtered by period)."""
    q = (
        db.table(TABLE_NAME)
        .select("*")
        .eq("ticker", ticker)
        .order("created_at", desc=True)
        .limit(1)
    )
    if period:
        q = q.eq("period", period)
    data = q.execute().data or []
    return data[0] if data else None
