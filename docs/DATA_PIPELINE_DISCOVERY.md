# Data Pipeline Discovery & Migration Plan

## 1) Files Found and What They Do

### Price bar fetch & storage
| File | Role |
|------|------|
| **src/data_source.py** | Wraps yfinance: `get_price()`, `get_history(period)`, `get_financials()`, `get_actions()`. Fetches raw OHLCV; no timeframe param (yfinance uses daily by default). |
| **src/fetch_ticker_price.py** | `StockFetcher`: uses DataSource + optional Cache; `get_historical_data(period)` returns normalized candles via `normalize_candles()`. |
| **src/normalization.py** | `normalize_candles(df)`: reset index → `timestamp`, convert to UTC, lowercase columns, `_validate_ohlcv()`, drop_duplicates by `timestamp`. Raises on OHLCV validation failure. |
| **src/main.py** (CLI) | Fetches history, runs signals/bias, writes CSV to `../app/historical_data/{ticker}_hist_{period}.csv` and JSON to price_summaries / bias_assessments. |

### Indicator computation
| File | Role |
|------|------|
| **src/signals.py** | `StockSignals(history).compute_signals()`: MA5, MA20, MA100, MA200 (last value only), RSI (window 14, capped by len), ADX (14), percent_price_change (5d), period high/low. No lookback; short history → NaN for MA100/MA200. |
| **src/BiasScorer.py** | Consumes signals dict; produces bias score, label, evidence. Handles missing signals with “unavailable” messages. |
| **src/analyze_service.py** | `analyze(ticker, period)`: fetches history for requested period only, runs StockSignals → BiasScorer, returns analysis dict (no history stored in DB). |
| **src/services/analyze_service.py** | Thin wrapper: `analyze_ticker(..., include_history, history_limit)` around `analyze()`. |

### DB & API
| File | Role |
|------|------|
| **src/db/database.py** | Supabase client; table name `analysis_db`. |
| **src/db/analysis_repo.py** | Upsert/list/get_latest for **analysis_db** (analysis results only, not OHLCV). |
| **app/main.py** | FastAPI: `/api/analyze` (run analysis, optional store in analysis_db), `/api/analyses`, `/api/analyses/latest` (from analysis_db); `/api/stocks/{ticker}/historical_data/{period}` reads **CSV** from `historical_data/`; price_summaries and bias_assessments from JSON files. |

### UI
| Path | Role |
|------|------|
| **web/app/analyses/page.jsx** | Calls backend `/api/analyses`, `/api/analyze`; no direct Supabase bar/feature queries. |
| **web/lib/api.js** | `fetchAnalyses`, `runAnalyze`, `fetchLatestAnalysis` → backend API. |

---

## 2) Current Schema and Data Flow

### Supabase (project: ai-stock-predictor)
- **analysis_db** (only table): `id`, `created_at`, `ticker`, `period`, `as_of`, `label`, `score`, `current_price`, `bias_assessment` (jsonb), `price_summary` (jsonb), `user_id`. Unique on `(ticker, period, user_id)`. Index on `(ticker, user_id, created_at DESC)`.
- **No** table for OHLCV price bars or computed indicators.

### File-based “schema”
- **historical_data/{ticker}_hist_{period}.csv**: written by CLI; columns (after normalization) are typically `timestamp`, `open`, `high`, `low`, `close`, `volume` (and possibly Dividends if not stripped). No `ticker` or `timeframe` in file; implied by path.
- **price_summaries/** and **bias_assessments/** JSON: one file per (ticker, period).

### How the UI gets data
- **Historical bars**: GET `/api/stocks/{ticker}/historical_data/{period}` → server reads CSV and returns list of rows (no DB).
- **Analysis**: POST `/api/analyze` runs full pipeline (yfinance → normalize → signals → bias) and optionally writes to **analysis_db**; GET `/api/analyses` and `/api/analyses/latest` read from **analysis_db** only.

---

## 3) Suspected Issues

- **Duplicates**: Normalization drops duplicates by `timestamp` only; no (ticker, timeframe) in key. Multiple periods (e.g. 1mo and 3mo) can produce overlapping dates in different CSVs; no single source of truth.
- **Missing timestamps / irregular intervals**: No gap detection; holidays/weekends may look like gaps; no explicit interval (e.g. 1d) stored.
- **OHLC invalids**: `_validate_ohlcv` checks high ≥ low, close in [low, high], positive prices, non-negative volume—but raises and stops; no repair or reporting per bar.
- **Timezone**: Normalization converts to UTC and treats naive as US/Eastern; good. But yfinance can return timezone-aware (e.g. US/Eastern); need to ensure all stored bars are consistently UTC.
- **Extreme spikes / corporate actions**: No split/dividend adjustment in pipeline; `get_actions()` exists but is unused. No spike detection or adjustment factor stored.
- **NA indicators**: MA100/MA200 need 100/200 bars; for short periods (e.g. 3mo) they are NaN; no extended lookback or adaptive fallback (e.g. MA150/100).
- **Inconsistent granularity**: Timeframe (1d vs 1h) not stored; yfinance `history(period)` is daily.
- **API quirk**: `/api/stocks/{ticker}/historical_data/{period}` returns a list of records; route is declared with `response_model=StockResponseModel` which expects an object with `historical_data`—likely a mismatch (pre-existing).

---

## 4) Migration Plan (with rollback / safety)

### Phase 1 – Audit & cleanup (no API contract change)
1. **Audit script (read-only)**  
   - Input: path to CSV dir and/or ticker list; optional DB connection for future `price_bars` table.  
   - Output: summary table + per-ticker issue list (duplicates, gaps, OHLC invalids, timezone, spikes).  
   - No writes; safe to run anytime.

2. **New Supabase table: price_bars**  
   - Columns: `id` (uuid), `ticker` (text), `timeframe` (text, e.g. `1d`), `timestamp` (timestamptz), `open`, `high`, `low`, `close`, `volume` (numeric), optional `adjusted_close`, `dividends`, `splits`, `source` (e.g. `yfinance`), `created_at`.  
   - Uniqueness: `UNIQUE (ticker, timeframe, timestamp)`.  
   - Indexes: B-tree on `(ticker, timeframe, timestamp)` for lookups and dedupe.

3. **Cleanup job (idempotent)**  
   - Reads from CSV dir (or fetches via yfinance for given ticker/period).  
   - Normalizes: UTC, lowercase, validate OHLCV (optionally report-only for bad rows).  
   - Dedupes: keep one row per (ticker, timeframe, timestamp) (e.g. latest or most complete).  
   - Writes/upserts into `price_bars`.  
   - Re-running on same input should not change DB after first run (same key → same row).

4. **Backward compatibility**  
   - Keep existing CSV-based endpoint as-is: `/api/stocks/{ticker}/historical_data/{period}` still reads from CSV.  
   - Optional: later add a second source (e.g. read from `price_bars` when CSV missing or via feature flag) with same response shape.

### Phase 2 – Feature pipeline & storage
5. **Feature computation redesign**  
   - For a requested period (e.g. 3mo), fetch or use at least 1–2 years of daily bars (from `price_bars` or yfinance) for computation; score only the last N bars.  
   - Feature availability: mask or metadata columns so UI can show “insufficient history” instead of raw NA.  
   - Adaptive windows: e.g. if MA200 unavailable, use MA150 or MA100 and record which length was used.  
   - Standard names: e.g. `rsi_14`, `macd_12_26_9`, `atr_14`, `bbands_20_2`, `sma_20`, `sma_200`, etc.

6. **Features storage (wide table)**  
   - Table: e.g. `feature_bars` with `ticker`, `timeframe`, `timestamp`, then many numeric columns (rsi_14, atr_14, sma_20, …), plus `computed_at` (timestamptz) and optional `feature_metadata` (jsonb) for “sma_used: 100” etc.  
   - Index: B-tree on `(ticker, timeframe, timestamp)` for fast time-range retrieval.  
   - Keeps UI queries simple (one row per bar, filter by ticker/timeframe, order by timestamp).

### Phase 3 – Tests & CLI
7. **Tests**  
   - Unit: indicator functions on small known DataFrames (expected values for RSI, SMA, etc.).  
   - Integration: ingest small ticker history → cleanup → compute features → assert no unexpected NA for expected windows, monotonic timestamps, uniqueness.

8. **CLI**  
   - `python -m scripts.audit_data --ticker HOOG` (or `--csv-dir`, `--ticker-file`).  
   - `python -m scripts.cleanup_data --ticker HOOG` (idempotent write to DB/CSV).  
   - `python -m scripts.compute_features --ticker HOOG --timeframe 1d` (with lookback).  
   - Logging and a short README section for local and production (container/scheduled job).

### Rollback / safety
- **Audit**: read-only; no rollback needed.  
- **price_bars migration**: standard migration; rollback = drop table (and optionally re-run old CSV-only path).  
- **Cleanup job**: idempotent; no duplicate rows thanks to unique constraint.  
- **Feature table**: additive; existing API does not depend on it until we switch; rollback = drop feature table and keep using current analyze path.  
- **Existing analysis_db and CSV/JSON endpoints**: unchanged; no breaking change to current API contracts.

---

## 5) Implementation Order

1. **A)** Audit script (Python): scan CSV (and optionally DB) → report.  
2. **B)** Migration for `price_bars` + cleanup job (idempotent).  
3. **C)** Feature pipeline: lookback, NA mask, adaptive windows, standard names.  
4. **D)** Migration for `feature_bars` (wide) + indexing.  
5. **E)** Unit + integration tests.  
6. **F)** CLI entrypoints + README section.
