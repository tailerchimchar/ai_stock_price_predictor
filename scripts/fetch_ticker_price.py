import yfinance as yf
from pydantic import BaseModel
from typing import Optional

class StockFetcher(BaseModel):
    ticker_symbol: str

    def fetch_price(self) -> Optional[float]:
        ticker = yf.Ticker(self.ticker_symbol)
        try:
            price = ticker.info.get('regularMarketPrice', None)
        except Exception as e:
            print(f"Error fetching price for {self.ticker_symbol}: {e}")
            return None
        return price

    def get_historical_data(self, period: str = "1mo"):
        ticker = yf.Ticker(self.ticker_symbol)
        hist = ticker.history(period=period)
        return hist

    def get_financials(self):
        ticker = yf.Ticker(self.ticker_symbol)
        financials = ticker.financials
        return financials
    
    def get_actions(self):
        ticker = yf.Ticker(self.ticker_symbol)
        actions = ticker.actions
        return actions

    def __str__(self):
        return f"StockFetcher(ticker_symbol={self.ticker_symbol})"

  