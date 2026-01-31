# AI Stock Price Predictor

Backend API and web app for stock analysis and price prediction.

## Running locally

### 1. Backend (FastAPI)

From the **project root**, with your virtual environment activated:

```bash
uvicorn app.main:app --reload --port 8000
```

Or with Python explicitly:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

- API: **http://localhost:8000**
- Docs: **http://localhost:8000/docs**

Backend expects a `.env` in the project root with `SUPABASE_URL`, `SUPABASE_KEY`, and `SUPABASE_JWT_SECRET` (see [AUTH_SETUP.md](AUTH_SETUP.md)).

### 2. Frontend (Next.js)

In a **second terminal**:

```bash
cd web
npm install
npm run dev
```

- App: **http://localhost:3000**

Create `web/.env.development.local` with:

- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (see [AUTH_SETUP.md](AUTH_SETUP.md)).

### 3. Run both at once (optional)

From the project root (with venv activated and `npm install` already run in `web/`):

```bash
npm run dev
```

This runs the API and the web app together via `concurrently`.

---

### Testing sign-up and users

1. **Start backend and frontend** (see above), then open **http://localhost:3000/auth**.

2. **Sign up a user**
   - Click the link so the form is in **Sign Up** mode (or use the toggle).
   - Enter any **email** and a **password** (min 6 characters).
   - Click **Sign Up**.
   - Supabase sends a confirmation email; open the link to confirm (unless you turned off “Confirm email” in Supabase Dashboard → Authentication → Providers → Email).

3. **Sign in**
   - On the same auth page, switch to **Sign In**, enter the same email and password, then **Sign In**. You should be redirected to `/analyses`.

4. **Test with multiple users**
   - Sign out, then sign up with a **different email** and password.
   - Sign in as User A, run an analysis and store it.
   - Sign out, sign in as User B; you should not see User A’s analyses. Run and store an analysis as User B.
   - Sign back in as User A; you should only see User A’s data (multi-user isolation).

**Quick test users:** use any emails you control (e.g. `test1@example.com`, `test2@example.com`) and any password ≥ 6 characters. No seed script is required; sign-up and sign-in are done from the auth page.

To **skip email confirmation** in development: Supabase Dashboard → Authentication → Providers → Email → disable “Confirm email”. Then you can sign in immediately after sign-up without opening the confirmation link.

---

## Testing

### Prerequisites

- **Python 3.10+** (recommended: use a virtual environment)
- Dependencies from `requirements.txt`

### Setup

1. Create and activate a virtual environment:

   **Windows (PowerShell):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **Windows (cmd):**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate.bat
   ```

   **macOS/Linux:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run tests

From the **project root** (`ai_stock_price_predictor`):

| Command | Description |
|--------|-------------|
| `pytest` | Run all tests in `tests/` |
| `pytest -v` | Run all tests with verbose output |
| `pytest tests/test_normalization.py` | Run a single test file |
| `pytest tests/test_normalization.py -v` | Run one file with verbose output |
| `pytest tests/test_normalization.py -k "test_something"` | Run tests whose name matches `test_something` |

**Examples:**

```bash
# All tests
pytest

# Verbose
pytest -v

# One file
pytest tests/test_bias_scorer.py -v

# One test by name
pytest tests/test_caching.py -k "test_cache_hit" -v
```

Tests use mocks and fixtures (see `tests/conftest.py`); no live API keys or database are required for the test suite. Database-related tests set `SUPABASE_URL` and `SUPABASE_KEY` via `monkeypatch` when needed.

### Test layout

- **`tests/`** – pytest test modules and shared fixtures
- **`tests/conftest.py`** – shared fixtures (e.g. `FakeDataSource`, `create_sample_ohlcv_data`)
- **`test_jwt.py`** – JWT/auth script at project root (run with `python test_jwt.py` if needed)

### Web app (lint only)

The `web/` Next.js app has no test script; you can lint it from the repo root:

```bash
npm --prefix web run lint
```

Or from `web/`:

```bash
cd web
npm run lint
```

---

## Data pipeline (audit, cleanup, features)

The repo includes a **data quality and feature pipeline** you can run locally or in a container/scheduled job. See [docs/DATA_PIPELINE_DISCOVERY.md](docs/DATA_PIPELINE_DISCOVERY.md) for schema, issues, and migration plan. For a plain-English explanation of what **audit_data**, **cleanup_data**, **compute_features** and the DB repos do and how they relate, see [docs/DATA_PIPELINE_SCRIPTS_AND_REPOS.md](docs/DATA_PIPELINE_SCRIPTS_AND_REPOS.md).

### Prerequisites

- Run migrations in Supabase SQL Editor (see `migrations/`):
  - **003_create_price_bars.sql** – OHLCV table `price_bars` (ticker, timeframe, timestamp)
  - **004_create_feature_bars.sql** – wide feature table `feature_bars`
- `.env` with `SUPABASE_URL` and `SUPABASE_KEY` for cleanup and compute_features (when writing to DB)

### Commands (from project root)

| Command | Description |
|--------|--------------|
| `python -m scripts.audit_data --ticker HOOG` | Read-only audit: scan CSV dir for ticker, report duplicates, gaps, OHLC invalids, timezone, spikes |
| `python -m scripts.audit_data --csv-dir app/historical_data` | Audit all tickers in directory |
| `python -m scripts.audit_data --ticker HOOG -v` | Audit with per-file issue details |
| `python -m scripts.cleanup_data --ticker HOOG` | Normalize, dedupe, upsert OHLCV to `price_bars` (idempotent). Uses yfinance if no `--csv-dir` |
| `python -m scripts.cleanup_data --ticker HOOG --csv-dir app/historical_data` | Cleanup from CSV files |
| `python -m scripts.cleanup_data --ticker HOOG --dry-run` | No DB write; print row count |
| `python -m scripts.compute_features --ticker HOOG --timeframe 1d` | Compute indicators (RSI, SMA, ATR, ADX, etc.) with 2y lookback, upsert to `feature_bars` |
| `python -m scripts.compute_features --ticker HOOG --csv-dir app/historical_data` | Compute from CSV bars |
| `python -m scripts.compute_features --ticker HOOG --dry-run` | No DB write; print row count |

### Logs

Scripts log to stdout. Use `-v` on audit for per-file details.

### Production / scheduled job

- Run migrations once in Supabase.
- Schedule cleanup and compute_features (e.g. daily) for desired tickers; same commands, ensure `SUPABASE_URL` and `SUPABASE_KEY` are set in the environment.
- Re-running cleanup or compute_features is **idempotent**: same input produces the same DB state.
- To run the pipeline on a schedule via **GitHub Actions** (cron), see [docs/GITHUB_ACTIONS_CRON_DATA_PIPELINE.md](docs/GITHUB_ACTIONS_CRON_DATA_PIPELINE.md) for setup, secrets, schedule rationale, and the workflow file (`.github/workflows/data-pipeline-cron.yml`).
