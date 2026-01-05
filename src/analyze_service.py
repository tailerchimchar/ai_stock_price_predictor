import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.BiasScorer import BiasScorer
from src.fetch_ticker_price import StockFetcher
from src.signals import StockSignals

def analyze(ticker: str, period: str = "2wk") -> dict:
	"""Return aggregated analysis for a ticker/period without side effects."""
	ticker = ticker.upper()

	fetcher = StockFetcher(ticker_symbol=ticker)
	current_price = fetcher.fetch_price()
	hist_full = fetcher.get_historical_data(period=period)

	if hist_full is None or hist_full.empty:
		raise ValueError(f"No historical data for {ticker} over {period}")

	# As-of timestamp from latest candle
	as_of = None
	if 'timestamp' in hist_full.columns:
		ts = pd.to_datetime(hist_full['timestamp'].max())
		as_of = ts.isoformat() if not pd.isna(ts) else None

	# Compute signals and assessments
	signals = StockSignals(hist_full).compute_signals()
	bias_scorer = BiasScorer(signals)
	label, score, evidence = bias_scorer.full_bias_assessment()
	price_summary = bias_scorer.get_price_summary()

	# Serialize evidence models to dicts for JSON compatibility
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
