# Feature JSONB + BiasScorer v3 + data pipeline docs and cron

## Summary

- **feature_bars** now stores all indicators in a single **`features`** JSONB column (migration 006 + optional 007). New indicators can be added without schema changes.
- **BiasScorer v3** uses RSI, ADX, BBands, and MACD from `feature_bars` when available (with fallback to in-memory signals). Same label buckets; additive impacts for BBands (±0.05) and MACD (±0.05); NA weight over 8 contributors.
- **analyze_service** supports `BIAS_SCORER_VERSION=v3`: when v3 and feature_bars has data for the ticker, signals are built from the latest feature row + price context; otherwise it uses `StockSignals(history).compute_signals()`.
- **Docs:** DATA_PIPELINE_SCRIPTS_AND_REPOS (scripts/repos + typical local flow), GITHUB_ACTIONS_CRON_DATA_PIPELINE (cron setup, secrets, schedule).
- **GitHub Actions:** `.github/workflows/data-pipeline-cron.yml` runs cleanup → compute_features → audit_data daily at 22:00 UTC for configurable tickers (repository variable `TICKERS` or default).
- **Features:** Added rsi_28, bbands_upper, bbands_lower in `src/features.py`. ADX guarded for short series so `test_compute_features_short_series` passes. v2/v3 ADX messages use formatted values (e.g. "23.8").

## Changes

### Migrations
- **006_feature_bars_features_jsonb.sql** — Add `features` jsonb; backfill from existing columns.
- **007_drop_feature_bars_legacy_columns.sql** — Optional; drop legacy scalar columns after 006 is verified.

### Backend
- **src/db/feature_bars_repo.py** — Rows use `features` dict; added `get_latest_feature_bars(db, ticker, timeframe, limit)`.
- **scripts/compute_features.py** — Builds one `features` dict per row (no per-column writes).
- **src/features.py** — Added rsi_28, bbands_upper, bbands_lower; ADX only computed when `len(close) >= MIN_BARS_ADX` (fixes short-series crash).
- **src/scoring/v3.py** — New BiasScorerV3: v2 logic + BBands and MACD impacts; same labels; 8 contributors for NA weight.
- **src/scoring/__init__.py** — `get_scorer("v3")` → BiasScorerV3.
- **src/scoring/v2.py** — ADX message formatting uses `self._fmt(adx)` for weak/moderate/strong-unclear.
- **src/analyze_service.py** — v3: try `get_latest_feature_bars`; if present, build signals via `_signals_from_feature_bar(features, hist_full)`; else `StockSignals(hist_full).compute_signals()`. Audit enabled for v2 and v3.

### Docs
- **docs/DATA_PIPELINE_SCRIPTS_AND_REPOS.md** — What audit_data, cleanup_data, compute_features and the three repos do; typical flow to see data locally.
- **docs/GITHUB_ACTIONS_CRON_DATA_PIPELINE.md** — GitHub secrets, schedule (22:00 UTC daily), workflow steps, optional audit_data.
- **README.md** — Links to both docs and to cron workflow.

### CI / automation
- **.github/workflows/data-pipeline-cron.yml** — Schedule 22:00 UTC; cleanup → compute_features → audit_data per ticker; env from secrets; tickers from `vars.TICKERS` or default.

## How to test

1. Run migrations 006 (and optionally 007) in Supabase SQL Editor.
2. From project root with `.env` set:  
   `python -m scripts.cleanup_data --ticker UNH --timeframe 1d --period 2y`  
   `python -m scripts.compute_features --ticker UNH --timeframe 1d`
3. Set `BIAS_SCORER_VERSION=v3`, start API and `npm run dev` in `web/`, run analyze for UNH; evidence should include BBands and MACD when feature_bars has data.

## Rollback

- Default scorer remains v1 (`BIAS_SCORER_VERSION` unset or `v1`). Set to `v2` or `v3` explicitly.
- If 007 was run, re-adding legacy columns would require a new migration; 006 keeps legacy columns until 007 is applied.
