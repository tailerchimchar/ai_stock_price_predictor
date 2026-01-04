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
  price = fetcher.fetch_price()
  hist = fetcher.get_historical_data(period=period)
  
  print(f"\n{ticker} - Current: ${price:.2f}")
  print(f"\nHistorical ({period}, {len(hist)} candles):")
  print(hist.to_string(index=False))
  
  stockSignals = StockSignals(hist)
  computed_signals = stockSignals.compute_signals()
  bias_scorer = BiasScorer(computed_signals)
  label, score, evidence = bias_scorer.full_bias_assessment()
  
  print(f"\nFull bias assessment of {ticker}: \nLabel:{label} \n(score: {score:.2f})\n")
  print(f"Price went from {computed_signals['first_close']} to {computed_signals['last_close']} in the time period {period}.")
  print(f"Period High: {computed_signals['period_high']} and Period Low: {computed_signals['period_low']}")
  print(f"Total Return %: {((computed_signals['last_close'] / computed_signals['first_close'] - 1)*100):.2f}%")
  print("Evidence:")
  for key, value in evidence.items():
    print(f'{key}: {value}')

if __name__ == "__main__":
  main()