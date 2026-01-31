import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scoring import get_scorer
from src.fetch_ticker_price import StockFetcher
from src.signals import StockSignals


def _store_price_bars_if_enabled(ticker: str, hist_full: pd.DataFrame) -> None:
    """If STORE_PRICE_BARS_ON_ANALYZE is set and DB available, upsert bars to price_bars."""
    if not os.getenv("STORE_PRICE_BARS_ON_ANALYZE"):
        return
    try:
        from src.db.database import get_db
        from src.db.price_bars_repo import upsert_bars
        from src.pipeline.bar_utils import ohlcv_df_to_price_bar_rows

        db = get_db()
        rows = ohlcv_df_to_price_bar_rows(hist_full, ticker, timeframe="1d", source="yfinance")
        if rows:
            upsert_bars(db, rows)
    except Exception:
        pass  # Do not break analyze if DB or env is missing


def _signals_from_feature_bar(features: dict, hist_full: pd.DataFrame) -> dict:
    """Build signals dict from feature_bars row features + price context from hist_full."""
    if hist_full is None or hist_full.empty or "close" not in hist_full.columns:
        return {}
    close = hist_full["close"]
    last_close = float(close.iloc[-1])
    first_close = float(close.iloc[0])
    period_high = float(hist_full["high"].max()) if "high" in hist_full.columns else last_close
    period_low = float(hist_full["low"].min()) if "low" in hist_full.columns else last_close
    percent_price_change = (last_close / first_close - 1) if first_close else 0.0
    if len(hist_full) >= 6:
        percent_price_change = (last_close / float(close.iloc[-6]) - 1)
    signals = {
        "rsi": features.get("rsi_14"),
        "ma_5": features.get("sma_5"),
        "ma_20": features.get("sma_20"),
        "ma_100": features.get("sma_100"),
        "ma_200": features.get("sma_200"),
        "adx": features.get("adx_14"),
        "atr_14": features.get("atr_14"),
        "bbands_upper": features.get("bbands_upper"),
        "bbands_lower": features.get("bbands_lower"),
        "bbands_20_2": features.get("bbands_20_2"),
        "macd_12_26_9": features.get("macd_12_26_9"),
        "last_close": last_close,
        "first_close": first_close,
        "period_high": period_high,
        "period_low": period_low,
        "percent_price_change": percent_price_change,
        "price_change": (last_close - first_close) / first_close * 100 if first_close else 0,
    }
    return signals


def _audit_score_if_enabled(version: str, ticker: str, period: str, signals: dict, score: float, label: str) -> None:
    """If v2/v3 and SCORE_AUDIT_LOG is set and DB available, append one row to score_audit_log."""
    if version not in ("v2", "v3") or not os.getenv("SCORE_AUDIT_LOG"):
        return
    try:
        from src.db.database import get_db
        from src.db.score_audit_repo import insert_score_audit

        # Snapshot signals for JSON safety (e.g. numpy scalars -> float)
        signals_snapshot = {}
        for k, v in signals.items():
            if v is None:
                signals_snapshot[k] = None
            elif isinstance(v, (int, float, str, bool)):
                signals_snapshot[k] = v
            elif hasattr(v, "item"):
                signals_snapshot[k] = float(v)
            else:
                signals_snapshot[k] = v
        insert_score_audit(
            get_db(),
            ticker=ticker,
            period=period,
            signals_used=signals_snapshot,
            score=score,
            label=label,
        )
    except Exception:
        pass


def analyze(ticker: str, period: str = "2wk") -> dict:
    """Return aggregated analysis for a ticker/period without side effects."""
    ticker = ticker.upper()
    version = os.getenv("BIAS_SCORER_VERSION", "v1").strip().lower()
    if version not in ("v1", "v2", "v3"):
        version = "v1"

    fetcher = StockFetcher(ticker_symbol=ticker)
    current_price = fetcher.fetch_price()
    hist_full = fetcher.get_historical_data(period=period)

    if hist_full is None or hist_full.empty:
        raise ValueError(f"No historical data for {ticker} over {period}")

    _store_price_bars_if_enabled(ticker, hist_full)

    as_of = None
    if "timestamp" in hist_full.columns:
        ts = pd.to_datetime(hist_full["timestamp"].max())
        as_of = ts.isoformat() if not pd.isna(ts) else None

    # v3: prefer feature_bars when available; else compute from history
    signals = None
    if version == "v3":
        try:
            from src.db.database import get_db
            from src.db.feature_bars_repo import get_latest_feature_bars

            rows = get_latest_feature_bars(get_db(), ticker, "1d", limit=1)
            if rows and rows[0].get("features"):
                signals = _signals_from_feature_bar(rows[0]["features"], hist_full)
        except Exception:
            pass
    if signals is None:
        signals = StockSignals(hist_full).compute_signals()

    ScorerClass = get_scorer(version)
    bias_scorer = ScorerClass(signals)
    label, score, evidence = bias_scorer.full_bias_assessment()
    price_summary = bias_scorer.get_price_summary()

    _audit_score_if_enabled(version, ticker, period, signals, score, label)

    evidence_serialized = {
        key: value.model_dump() if hasattr(value, "model_dump") else value
        for key, value in evidence.items()
    }

    return {
        "ticker": ticker,
        "period": period,
        "as_of": as_of,
        "current_price": round(current_price, 2) if current_price is not None else None,
        "bias_assessment": {
            "label": label,
            "score": score,
            "evidence": evidence_serialized,
        },
        "price_summary": price_summary,
    }


__all__ = ["analyze"]
