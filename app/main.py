from typing import Optional
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import json
import sys
from pathlib import Path
from stock_response_model import StockResponseModel

# Ensure project root is on sys.path for scripts and src imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
  sys.path.append(str(ROOT))

from src.analyze_service import analyze

app = FastAPI(title="Stock Data API", version="1.0.0")

origins = [
  "http://localhost:5173"
]

app.add_middleware(
  CORSMiddleware,
  allow_origins=origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "healthy"}
  
@app.post("/api/stocks/{ticker}/period/{period}/")
async def analyze_stock(ticker: str, period: str):
  try:
    result = analyze(ticker, period)
    return result
  except FileNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
    
  
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