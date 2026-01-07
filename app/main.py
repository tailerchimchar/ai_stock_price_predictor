import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import json
import sys
from pathlib import Path
from app.stock_response_model import StockResponseModel

# Ensure project root is on sys.path for src imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
  sys.path.append(str(ROOT))

from src.db.database import get_db, healthcheck
from src.db.analysis_repo import insert_analysis, list_analyses, get_latest_analysis
from src.services.analyze_service import analyze_ticker

''' 
Example json's to pass in:
{
  "ticker": "AAPL",
  "period": "1y",
  "store": True,
  "include_history": False,
  "history_limit": 0
}

{
  "ticker": "MSFT",
  "period": "6mo"
}
'''
class AnalyzeRequest(BaseModel):
  ticker: str = Field(..., example="AAPL", description="Stock ticker symbol")
  period: str = Field(..., example="1y", description="Time period (e.g., 1mo, 3mo, 6mo, 1y, 2y)")
  store: bool = Field(default=False, description="Store result in database")
  include_history: bool = Field(default=False, description="Include price history in response")
  history_limit: int = Field(default=0, description="Limit number of history records (0 = all)")

app = FastAPI(title="Stock Data API", version="1.0.0")

origins = [
  "http://localhost:5173",
  "http://localhost:3000",  # Next.js dev server
  "https://ai-stock-price-predictor-7pmv.onrender.com",  # Production API
  os.getenv("FRONTEND_ORIGIN", ""),  # Your deployed frontend URL
]

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_origin_regex=r"https://.*\.vercel\.app",
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.get("/")
def root():
  return {"message": f"Welcome to the Stock Data API. Visit /docs for API documentation."}

@app.get("/health")
async def health():
  try:
    return {"status": "healthy", "db": healthcheck()}
  except RuntimeError as exc:
    raise HTTPException(status_code=503, detail=str(exc))


@app.post("/api/analyze", response_model=StockResponseModel)
async def analyze(req: AnalyzeRequest):
  """Analyze a ticker/period; optionally store the result when store=True."""
  try:
    result = analyze_ticker(
      ticker=req.ticker,
      period=req.period,
      include_history=req.include_history,
      history_limit=req.history_limit,
    )
  except FileNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc))
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=f"Invalid request: {str(exc)}")

  # Convert evidence dict to list for Pydantic validation
  bias_assessment = result.get("bias_assessment", {})
  if isinstance(bias_assessment.get("evidence"), dict):
    bias_assessment["evidence"] = list(bias_assessment["evidence"].values())

  if req.store:
    payload = {
      "ticker": req.ticker,
      "period": req.period,
      "label": bias_assessment.get("label"),
      "score": bias_assessment.get("score"),
      "current_price": result.get("current_price"),
      "price_summary": result.get("price_summary", {}),
      "bias_assessment": dict(bias_assessment),  # Convert to dict if needed
      # "evidence": list(bias_assessment.get("evidence", {}).values())  # Convert evidence to list
    }
    try:
      insert_analysis(get_db(), result=payload)
    except RuntimeError as exc:
      raise HTTPException(status_code=400, detail=str(exc))

  return result


@app.get("/api/analyses")
async def analyses(ticker: str, limit: int = Query(50, gt=0, le=1000)):
  try:
    return list_analyses(get_db(), ticker=ticker, limit=limit)
  except RuntimeError as exc:
    raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/analyses/latest")
async def latest_analysis(ticker: str, period: Optional[str] = None):
  try:
    return get_latest_analysis(get_db(), ticker=ticker, period=period)
  except RuntimeError as exc:
    raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/stocks/{ticker}/historical_data/{period}", response_model=StockResponseModel)
async def read_csv(ticker: str, period: str, limit: int = Query(500, gt=0, lt=10000)):
  data = pd.read_csv(f"historical_data/{ticker}_hist_{period}.csv").head(limit)
  return data.to_dict(orient="records")

@app.get("/api/stocks/{ticker}/price_summaries/{period}")
async def get_highs_lows(ticker: str, period: str):
  try:
    with open(f"price_summaries/{ticker}_price_summary_{period}.json", 'r') as f:
      data = json.load(f)
    return data
  except FileNotFoundError:
    raise HTTPException(status_code=404, detail="Price summary not found")

@app.get("/api/stocks/{ticker}/bias_assessments/{period}")
async def get_bias_assessment(ticker: str, period: str):
  try:
    with open(f"bias_assessments/{ticker}_bias_assessment_{period}.json", 'r') as f:
      data = json.load(f)
    return data
  except FileNotFoundError:
    raise HTTPException(status_code=404, detail="Bias assessment not found")