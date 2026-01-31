"""Repository for score_audit_log table (audit every score calculation)."""

from typing import Any, Dict

from supabase import Client as DB

TABLE_NAME = "score_audit_log"


def insert_score_audit(
    db: DB,
    *,
    ticker: str,
    period: str,
    signals_used: Dict[str, Any],
    score: float,
    label: str,
) -> None:
    """
    Append one row to score_audit_log for auditing.
    signals_used: dict of signal keys/values (e.g. from scorer's signals); will be stored as jsonb.
    """
    row = {
        "ticker": ticker,
        "period": period,
        "signals_used": signals_used,
        "score": score,
        "label": label,
    }
    db.table(TABLE_NAME).insert(row).execute()
