import json
import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))
from BiasScorer import BiasScorer
from src.fetch_ticker_price import StockFetcher
from src.signals import StockSignals

def main():
  parser = argparse.ArgumentParser(description='AI Stock Price Predictor')
  parser.add_argument('ticker', nargs='?', help='Stock ticker (e.g., SPY)')
  parser.add_argument('period', nargs='?', default='2wk', help='Historical data period',
    choices=['1d', '1wk', '2wk', '1mo', '3mo', '6mo', '1y'])
  args = parser.parse_args()
  
  # Get ticker and period (CLI args or interactive)
  ticker = args.ticker or input("Ticker symbol: ").strip()
  ticker = ticker.upper()
  
  if not args.ticker:
    period = input("Period (1d/1wk/2wk/1mo/3mo/6mo/1y) [2wk]: ").strip() or '2wk'
  else:
    period = args.period
  
  # Fetch and display
  fetcher = StockFetcher(ticker_symbol=ticker)
  
  # Full historical data 
  price = fetcher.fetch_price()
  hist_full = fetcher.get_historical_data(period=period)
  print(f"\n{ticker} - Current: ${price:.2f}")
  print(f"\nHistorical ({period}, {len(hist_full)} candles):")
  
  # Display and save historical data
  hist_display = hist_full.round({'open': 2, 'high': 2, 'low': 2, 'close': 2, 'Dividends': 2})
  print(hist_display.to_string(index=False))
  hist_display.to_csv(f"../app/historical_data/{ticker}_hist_{period}.csv", index=False)
  
  stockSignals = StockSignals(hist_full)
  computed_signals = stockSignals.compute_signals()
  bias_scorer = BiasScorer(computed_signals)
  
  # Bias assessment
  bias_assessment = json.loads(bias_scorer.get_bias_assessment())
  print(f"\n{'='*60}")
  print(f"BIAS ASSESSMENT: {ticker} ({period})")
  print(f"{'='*60}")
  print(json.dumps(bias_assessment, indent=2))
  
  # Save bias assessment to JSON file
  with open(f"../app/bias_assessments/{ticker}_bias_assessment_{period}.json", 'w') as f:
    json.dump(bias_assessment, f, indent=2)

  
  # Price summary
  price_summary = bias_scorer.get_price_summary()
  print(f"\n{'='*60}")
  print("PRICE SUMMARY")
  print(f"{'='*60}")
  print(json.dumps(price_summary, indent=2))
  
  # Save price summary to JSON file
  with open(f"../app/price_summaries/{ticker}_price_summary_{period}.json", 'w') as f:
    json.dump(price_summary, f, indent=2)
if __name__ == "__main__":
  main()