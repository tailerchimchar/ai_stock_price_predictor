# AI Stock Price Predictor

Backend API and web app for stock analysis and price prediction.

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
