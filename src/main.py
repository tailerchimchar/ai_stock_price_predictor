import sys
from pathlib import Path

# Add parent directory to path so we can import scripts
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.fetch_ticker_price import StockFetcher

def main():
  print("Hello, AI Stock Price Predictor!")
  ticker = str(input("Enter a stock ticker symbol: ")).upper().strip()
  fetcher = StockFetcher(ticker_symbol=ticker)
  print(f"The current price of {ticker} is ${fetcher.fetch_price()}")
  print(f"Historical data for the past week:\n{fetcher.get_historical_data(period='1wk')}")
  # print(f"Financials:\n{fetcher.get_financials()}")
  # print(f"Actions:\n{fetcher.get_actions()}")
  
if __name__ == "__main__":
  main()