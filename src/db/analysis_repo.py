from typing import Any, Dict, List, Optional
from supabase import Client as DB
from src.db.database import TABLE_NAME


def insert_analysis(db: DB, *, result: Dict[str, Any], user_id: str) -> str:
    """
    Upsert a single analysis row with user_id; return its id as string.
    
    Args:
        db: Supabase client
        result: Analysis data dict
        user_id: User UUID who owns this analysis
    """
    result["user_id"] = user_id  # Ensure user_id is set server-side
    resp = (
        db.table(TABLE_NAME)
        .upsert(result, on_conflict="ticker,period,user_id", returning="representation")
        .execute()
    )
    row = resp.data[0] if resp.data else {}
    return str(row.get("id", ""))


def list_analyses(db: DB, *, ticker: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    List analyses for a ticker owned by user_id, newest first.
    
    Args:
        db: Supabase client
        ticker: Stock ticker symbol
        user_id: User UUID to filter by
        limit: Max results
    """
    q = (
        db.table(TABLE_NAME)
        .select("*")
        .eq("ticker", ticker)
        .eq("user_id", user_id)  # Filter by user
        .order("created_at", desc=True)
        .limit(limit)
    )
    return q.execute().data or []


def get_latest_analysis(db: DB, *, ticker: str, user_id: str, period: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch the latest analysis for a ticker owned by user_id (optionally filtered by period).
    
    Args:
        db: Supabase client
        ticker: Stock ticker symbol
        user_id: User UUID to filter by
        period: Optional period filter
    """
    q = (
        db.table(TABLE_NAME)
        .select("*")
        .eq("ticker", ticker)
        .eq("user_id", user_id)  # Filter by user
        .order("created_at", desc=True)
        .limit(1)
    )
    if period:
        q = q.eq("period", period)
    data = q.execute().data or []
    return data[0] if data else None
