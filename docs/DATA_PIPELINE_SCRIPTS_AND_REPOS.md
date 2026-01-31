# Data Pipeline: Scripts and Repos

This doc explains what the three CLI scripts and three DB repos do and how they fit together.

---

## Scripts (run by you or by a cron job)

### 1. `audit_data.py` — **Read-only** data quality report

**What it does:** Scans price history (from CSV files or from the `price_bars` table) and **reports** issues. It does **not** change any data.

**It reports:**
- Duplicates (same ticker + timestamp)
- Missing timestamps / irregular gaps
- Invalid OHLCV (e.g. high < low, close outside [low, high], negative volume)
- Timezone issues (naive vs UTC)
- Extreme price spikes (possible bad data or splits)

**When to use:** Before or after cleanup to see how healthy your data is.

**Example:**
```bash
python -m scripts.audit_data --ticker HODL
python -m scripts.audit_data --ticker HODL --csv-dir app/historical_data
```

---

### 2. `cleanup_data.py` — Normalize and store **price bars** (OHLCV)

**What it does:** Takes raw price history (from CSV or by fetching via yfinance), normalizes it (UTC, valid OHLCV, deduped), and **upserts** it into the **`price_bars`** table in Supabase.

**Steps:**
- Load bars (CSV or yfinance)
- Normalize timestamps to UTC, validate OHLCV
- Dedupe by (ticker, timeframe, timestamp)
- Upsert into `price_bars`

**When to use:** To backfill or refresh the canonical OHLCV store. Safe to run repeatedly (idempotent).

**Example:**
```bash
python -m scripts.cleanup_data --ticker HODL
python -m scripts.cleanup_data --ticker HODL --timeframe 1d --period 2y
```

---

### 3. `compute_features.py` — Compute indicators and store **feature bars**

**What it does:** Reads **price bars** (from `price_bars` table, or CSV, or yfinance), computes technical indicators (RSI, SMA, ATR, ADX, Bollinger Bands, MACD, etc.), and **upserts** them into the **`feature_bars`** table in Supabase.

**Steps:**
- Load price bars (DB, CSV, or fetch)
- Run `src.features.compute_features()` (extended lookback so MA200/ADX etc. are available)
- Build one row per bar with a **`features`** JSONB object (all indicator values)
- Upsert into `feature_bars`

**When to use:** After you have price bars (e.g. after `cleanup_data`). Needed so **BiasScorer v3** can use BBands/MACD etc. from the DB instead of only in-memory signals.

**Example:**
```bash
python -m scripts.compute_features --ticker HODL --timeframe 1d
python -m scripts.compute_features --ticker HODL --timeframe 1d --lookback-period 2y
```

---

## Repos (used by scripts and by the API)

### 1. `price_bars_repo.py` — **price_bars** table (OHLCV)

**Table:** `price_bars` — one row per (ticker, timeframe, timestamp) with open, high, low, close, volume, etc.

**Functions:**
- **`upsert_bars(db, rows)`** — Insert or update OHLCV rows. Used by `cleanup_data.py` and by `analyze_service` when `STORE_PRICE_BARS_ON_ANALYZE` is set.

**Who uses it:** `cleanup_data.py`, `analyze_service.py` (optional), `compute_features.py` (to read bars from DB).

---

### 2. `feature_bars_repo.py` — **feature_bars** table (indicators)

**Table:** `feature_bars` — one row per (ticker, timeframe, timestamp) with a **`features`** JSONB column (rsi_14, sma_5, adx_14, bbands_upper, macd_12_26_9, etc.) and `feature_metadata`.

**Functions:**
- **`upsert_feature_rows(db, rows)`** — Insert or update feature rows (each row has `features` dict). Used by `compute_features.py`.
- **`get_latest_feature_bars(db, ticker, timeframe, limit=1)`** — Fetch the latest N feature rows for a ticker. Used by **analyze_service** when **BiasScorer v3** is enabled so the scorer can use precomputed indicators from the DB.

**Who uses it:** `compute_features.py` (writes), `analyze_service.py` (reads when v3 and feature_bars has data).

---

### 3. `score_audit_repo.py` — **score_audit_log** table (audit trail)

**Table:** `score_audit_log` — one row per score calculation: ticker, period, signals_used (jsonb), score, label, created_at.

**Functions:**
- **`insert_score_audit(db, ticker, period, signals_used, score, label)`** — Append one audit row. Used by **analyze_service** when `SCORE_AUDIT_LOG` is set and scorer is v2 or v3.

**Who uses it:** `analyze_service.py` only (writes). No script reads this; it’s for debugging and future calibration (e.g. Platt scaling).

---

## How they relate (flow)

```
CSV / yfinance
       │
       ▼
┌──────────────────┐     upsert      ┌─────────────┐
│  audit_data.py   │ ──(read only)──►│ price_bars  │◄── price_bars_repo.upsert_bars
│  (report issues) │                  │  (OHLCV)    │    (cleanup_data.py, analyze)
└──────────────────┘                  └──────┬──────┘
                                             │
       ┌──────────────────┐                 │ read
       │  cleanup_data.py  │ ──(normalize)───┘
       │  (normalize+upsert)│
       └──────────────────┘
                                             │
                                             ▼
       ┌──────────────────────┐     upsert  ┌──────────────┐
       │ compute_features.py  │ ───────────►│ feature_bars │◄── feature_bars_repo
       │ (indicators → DB)    │             │ (features    │    (analyze v3 reads
       └──────────────────────┘             │  jsonb)      │     get_latest_feature_bars)
                                             └──────────────┘

When user hits API (analyze):
  - Fetches history (yfinance)
  - Optionally stores to price_bars (if STORE_PRICE_BARS_ON_ANALYZE)
  - If v3: tries to load latest feature_bars for ticker → if found, uses those + price context for scoring
  - Else: uses StockSignals(history).compute_signals() (no BBands/MACD in that path)
  - Scores with v1 / v2 / v3
  - Optionally appends to score_audit_log (if SCORE_AUDIT_LOG and v2/v3)
```

---

## Why your UI doesn’t show BBands/MACD yet

1. **Scorer version:** The app uses `BIAS_SCORER_VERSION` (default **v1**). So you’re likely still on v1 or v2, which don’t add BBands/MACD evidence.

2. **v3 and feature_bars:** Even with **v3**, BBands and MACD evidence only appear when v3 **reads from the `feature_bars` table**. If you haven’t run `compute_features` for that ticker, `feature_bars` has no rows for it, so v3 falls back to `StockSignals(history).compute_signals()` — which only has RSI, MAs, ADX, etc., **not** BBands or MACD. So you see “BBands unavailable” and “MACD unavailable”.

**To see v3 with BBands and MACD:**

1. Set **`BIAS_SCORER_VERSION=v3`** (e.g. in `.env` or your environment).
2. Run the feature pipeline for that ticker so `feature_bars` is populated:
   ```bash
   python -m scripts.cleanup_data --ticker HODL --timeframe 1d --period 2y
   python -m scripts.compute_features --ticker HODL --timeframe 1d
   ```
3. Restart the app (or ensure it reads the new env) and run analyze for HODL again. v3 will load the latest row from `feature_bars` and the evidence will include BBands and MACD when present.

---

## Typical flow: see data locally (assume `.env` is set)

Prerequisites: `.env` in the project root with `SUPABASE_URL` and `SUPABASE_KEY` (and any other vars your app needs). Migrations 003, 004, 005, and 006 have been run in the Supabase SQL Editor so `price_bars`, `feature_bars`, and `score_audit_log` exist and `feature_bars` has a `features` jsonb column.

### 1. Pick a ticker and run the pipeline once

From the project root:

```bash
# Optional: audit existing data (read-only)
python -m scripts.audit_data --ticker AAPL

# Ingest and normalize OHLCV into price_bars (idempotent)
python -m scripts.cleanup_data --ticker AAPL --timeframe 1d --period 2y

# Compute indicators and write to feature_bars (idempotent)
python -m scripts.compute_features --ticker AAPL --timeframe 1d
```

You should see “Upserted N price rows” and “Upserted N feature rows” (or dry-run messages if you used `--dry-run`).

### 2. Use the API / UI

- **Backend:** Start the FastAPI app (e.g. `uvicorn app.main:app --reload` from the repo root or `app` dir, depending on your setup).
- **Frontend:** From `web/`, run `npm run dev` and open the app.
- In the UI, request an analysis for the same ticker (e.g. AAPL) and a period (e.g. 2mo).

### 3. What you should see

- **Without v3:** The analyzer uses v1 (or v2 if `BIAS_SCORER_VERSION=v2`). Evidence comes from in-memory signals only (RSI, MAs, ADX, etc.). No BBands/MACD in evidence.
- **With v3:** Set `BIAS_SCORER_VERSION=v3` in `.env` (or export it), restart the backend, then run analyze again for AAPL. The analyzer will load the latest row from `feature_bars` for AAPL and build signals from it. Evidence should include BBands and MACD when the DB row has those keys, plus the same price/RSI/MA/ADX evidence.

### 4. Confirm data in Supabase (optional)

In Supabase: **Table Editor** → `price_bars` and `feature_bars`. Filter by `ticker = 'AAPL'` and `timeframe = '1d'`. You should see rows with recent `timestamp`s; `feature_bars` rows should have the `features` column populated (jsonb).

### 5. Re-running the pipeline

Re-run the same `cleanup_data` and `compute_features` commands for the same ticker anytime. They are idempotent: same inputs produce the same DB state, so you can run them daily (e.g. via cron or GitHub Actions) without duplicating data.
