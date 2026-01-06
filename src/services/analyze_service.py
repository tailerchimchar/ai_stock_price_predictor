from typing import Any, Dict
from pathlib import Path
import sys

# Ensure src is importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Reuse your existing core analyzer (no side effects)
from src.analyze_service import analyze


def analyze_ticker(*, ticker: str, period: str, include_history: bool = False, history_limit: int = 0) -> Dict[str, Any]:
    """Run analysis and optionally include limited history."""
    result = analyze(ticker, period)
    if include_history:
        hist = result.get("history")
        if hist is not None and history_limit:
            result["history"] = hist[:history_limit]
    else:
        result.pop("history", None)
    return result
