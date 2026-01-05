import datetime
from pydantic import BaseModel
from typing import List, Optional, Literal, Annotated
from pydantic import Field

class EvidenceItemModel(BaseModel):
  key: str
  value: Optional[float] = None          # store raw number (e.g., 0.0569)
  message: str                           # human-readable
  impact: Optional[float] = 0.0          # how much it changed score
  direction: Optional[Literal["bullish", "bearish", "neutral",]] = None
  
  
class BiasAssessmentModel(BaseModel):
  """Pydantic model for bias assessment."""
  label: Literal['bullish', 'bearish', 'neutral', 'slightly bullish', 'slightly bearish']  # 'bullish', 'bearish', or 'neutral'
  score: Annotated[float, Field(ge=0, le=1)]  # Numerical score between 0 and 1
  evidence: List[EvidenceItemModel]  # Evidence supporting the bias assessment

class PriceSummaryModel(BaseModel):
  """Pydantic model for price summary."""
  first_close: float
  last_close: float
  period_high: float
  period_low: float
  total_return_pct: float  # Total return percentage over the period

class StockResponseModel(BaseModel):
  """Pydantic model for stock data response."""
  ticker: str
  period: str
  as_of: datetime.datetime  # ISO formatted datetime string
  current_price: float
  bias_assessment: BiasAssessmentModel  # Contains label, score, and evidence
  price_summary: PriceSummaryModel  # Contains price metrics and statistics
  historical_data: Optional[List[dict]] = None  # List of candlestick data as dicts
  financials: Optional[dict] = None  # Financial statements as dict
  income_statements: Optional[dict] = None  # Income statements as dict
  balance_sheets: Optional[dict] = None  # Balance sheets as dict