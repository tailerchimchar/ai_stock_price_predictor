import os
import datetime
from typing import Optional
from pathlib import Path

# Load environment variables FIRST, before any other imports
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import json
import sys
from app.stock_response_model import StockResponseModel
from app.auth import get_current_user, get_optional_user

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
]

# Append deployed frontend URL only if present
_frontend_origin = os.getenv("FRONTEND_ORIGIN")
if _frontend_origin:
  origins.append(_frontend_origin)

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_origin_regex=r"https://.*\.vercel\.app|http://(localhost|127\.0\.0\.1|10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3})\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[0-1])\.(?:\d{1,3})\.\d{1,3})(?::\d{1,5})?",
  allow_credentials=False,  # Using Bearer tokens, not cookies
  allow_methods=["GET", "POST", "OPTIONS"],
  allow_headers=["authorization", "content-type"],
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
async def analyze(req: AnalyzeRequest, user_id: str = Depends(get_optional_user)):
  """
  Analyze a ticker/period; optionally store the result when store=True.
  Auth is optional: analysis runs without auth, but storing requires authentication.
  """
  try:
    request_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = analyze_ticker(
      ticker=req.ticker,
      period=req.period,
      include_history=req.include_history,
      history_limit=req.history_limit,
    )
    result["timestamp"] = request_ts
  except FileNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc))
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=f"Invalid request: {str(exc)}")

  # Convert evidence dict to list for Pydantic validation
  bias_assessment = result.get("bias_assessment", {})
  if isinstance(bias_assessment.get("evidence"), dict):
    bias_assessment["evidence"] = list(bias_assessment["evidence"].values())

  if req.store:
    if not user_id:
      raise HTTPException(
        status_code=401,
        detail="Authentication required to store analyses"
      )
    
    payload = {
      "ticker": req.ticker,
      "period": req.period,
      "as_of": result.get("as_of"),
      "label": bias_assessment.get("label"),
      "score": bias_assessment.get("score"),
      "current_price": result.get("current_price"),
      "price_summary": result.get("price_summary", {}),
      "bias_assessment": dict(bias_assessment),
    }
    try:
      insert_analysis(get_db(), result=payload, user_id=user_id)
    except RuntimeError as exc:
      raise HTTPException(status_code=400, detail=str(exc))

  return result


@app.get("/api/analyses")
async def analyses(ticker: str, limit: int = Query(50, gt=0, le=1000), user_id: str = Depends(get_current_user)):
  """Get stored analyses for a ticker. Requires authentication."""
  try:
    return list_analyses(get_db(), ticker=ticker, user_id=user_id, limit=limit)
  except RuntimeError as exc:
    raise HTTPException(status_code=400, detail=str(exc))

@app.get("/api/analyses/latest")
async def latest_analysis(ticker: str, period: Optional[str] = None, user_id: str = Depends(get_current_user)):
  """Get latest analysis for a ticker. Requires authentication."""
  try:
    return get_latest_analysis(get_db(), ticker=ticker, user_id=user_id, period=period)
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