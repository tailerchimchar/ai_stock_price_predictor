# GitHub Actions: Cron job for the data pipeline

This doc describes how to run the data pipeline (cleanup + compute_features) on a schedule using GitHub Actions, what to configure in GitHub, how often to run it, and why those choices were made.

---

## What the workflow does

One scheduled workflow runs daily and, for each configured ticker:

1. **cleanup_data** — Fetches or uses existing price history, normalizes it, and upserts into `price_bars` (Supabase).
2. **compute_features** — Reads from `price_bars`, computes indicators, and upserts into `feature_bars` (Supabase).

So after each run, `price_bars` and `feature_bars` are up to date for those tickers. The API (and BiasScorer v3) can then read from the DB instead of recomputing on every request.

**Audit** (`audit_data`) is read-only and optional in cron; you can add it as a step if you want a daily data-quality report in the logs.

---

## Steps you must do in GitHub

### 1. Create repository secrets

The workflow needs your Supabase credentials so the scripts can write to `price_bars` and `feature_bars`.

1. In your repo on GitHub, go to **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret** and add:
   - **Name:** `SUPABASE_URL`  
     **Value:** Your Supabase project URL (e.g. `https://xxxxx.supabase.co`). Find it in Supabase Dashboard → Project Settings → API.
   - **Name:** `SUPABASE_KEY`  
     **Value:** Your Supabase **service role** key (or the anon key if your RLS allows the scripts to insert/update). For backend scripts that write to tables, the **service role** key is usually used so RLS doesn’t block the job. Find it in Supabase Dashboard → Project Settings → API → `service_role` (secret).

Do not commit these values; only store them as repository secrets.

### 2. (Optional) Set a repository variable for tickers

To avoid editing the workflow file every time you add/remove tickers:

1. **Settings** → **Secrets and variables** → **Actions** → **Variables**.
2. **New repository variable**:
   - **Name:** `TICKERS`
   - **Value:** Comma-separated tickers, e.g. `AAPL,MSFT,HODL,HOOG`.

The workflow uses this variable if it exists; otherwise it falls back to a default list in the YAML (e.g. `AAPL,MSFT`).

### 3. Add the workflow file

The workflow file must live in **`.github/workflows/`** in the default branch (e.g. `main`).

- **Path:** `.github/workflows/data-pipeline-cron.yml`
- Commit and push this file. Once pushed, GitHub Actions will run the workflow on the schedule defined in the file.

### 4. Permissions

The workflow runs with the default `GITHUB_TOKEN`. It does not need to push code or read other repos; it only needs to clone the repo and run the job. The default permissions are enough. If your repo has “Limit actions to default GITHUB_TOKEN” or similar, the workflow still runs; it only needs **Contents: read** to checkout the code.

---

## How often to run: schedule and rationale

**Chosen schedule: once per day at 22:00 UTC.**

- **Why daily:** The pipeline fills **daily** bars (`timeframe=1d`). One new bar per ticker per trading day. Running once per day is enough to capture the latest close; running more often doesn’t add new daily data, only duplicates work.
- **Why 22:00 UTC:** US equity markets close at 16:00 Eastern (20:00 or 21:00 UTC depending on DST). Data providers (e.g. yfinance) typically have the day’s bar available within 1–2 hours. 22:00 UTC is a safe, conservative time so the daily bar is available and the pipeline runs after the market has closed and data has settled. If you use a different data source with different latency, you can change the cron (e.g. 23:00 UTC).
- **Cron expression:** `0 22 * * *` = “At 22:00 UTC every day.” GitHub Actions uses UTC. You cannot use repository variables inside the cron string; the schedule is fixed in the workflow file. To change frequency, edit the `schedule` in the YAML.

**Decision summary:**

| Decision        | Choice              | Reason                                                                 |
|----------------|---------------------|------------------------------------------------------------------------|
| Frequency      | Once per day        | Daily bars only need one update per day.                               |
| Time           | 22:00 UTC           | After US close and typical data availability.                          |
| Order          | Cleanup → Features  | Features depend on price bars; cleanup must run first.                 |
| Audit in cron  | Optional            | Audit is read-only; add a step if you want daily quality reports.      |
| Tickers        | Variable or default | Variable `TICKERS` keeps the list out of code; default avoids empty.   |

---

## Workflow file location and name

- **Path:** `.github/workflows/data-pipeline-cron.yml`
- **Name (in YAML):** `Data pipeline (cleanup + features)` — this is what you see in the Actions tab.

---

## What the YAML does (summary)

1. **Trigger:** `schedule` with cron `0 22 * * *`; also `workflow_dispatch` so you can run the job manually from the Actions tab.
2. **Job:** Single job, Ubuntu runner.
3. **Steps:**
   - Checkout the repo.
   - Set up Python (e.g. 3.11).
   - Install dependencies from `requirements.txt`.
   - Build ticker list: use `vars.TICKERS` if the repository variable exists, else a default list.
   - For each ticker: run `cleanup_data`, then `compute_features`, with `SUPABASE_URL` and `SUPABASE_KEY` from secrets.

If a step fails, the job fails and you can see the log in the Actions run. Later steps (e.g. other tickers) won’t run unless you use a strategy to continue on error (not recommended for data pipelines; fail fast is better).

---

## After you add the workflow

1. Go to the **Actions** tab and select “Data pipeline (cleanup + features)”.
2. You can run it once manually via **Run workflow** (uses `workflow_dispatch`).
3. After the first scheduled run (or manual run), check Supabase: `price_bars` and `feature_bars` should have new or updated rows for the configured tickers.
4. If the workflow fails, open the failed run and inspect the step logs; usually the error is a missing secret, wrong key, or network/rate limit from the data source.

---

## Security and secrets

- **Secrets:** Stored in GitHub and exposed to the workflow as environment variables. They are not logged (GitHub masks them). Use the **service role** key only if you need to bypass RLS for the pipeline; restrict who can edit the repo and who can approve workflows if you use protected environments.
- **Supabase:** Prefer a dedicated service role key for automation if your project has RLS. Restrict that key’s use in Supabase if possible. Do not put the key in the workflow file or in repo variables (use Secrets for sensitive values).

---

## Local testing vs cron

- **Local:** To run the same pipeline by hand and see data in the UI, follow [DATA_PIPELINE_SCRIPTS_AND_REPOS.md](DATA_PIPELINE_SCRIPTS_AND_REPOS.md) → “Typical flow: see data locally.”
- **Cron:** This workflow runs the same commands on a schedule; only the trigger (time vs manual) and the environment (GitHub runner + secrets) differ.

---

## Optional: add audit_data to the workflow

If you want a daily data-quality report in the logs, add a step after cleanup (or after features) that runs:

```bash
python -m scripts.audit_data --ticker $TICKER
```

for each ticker. The script is read-only and only prints to stdout; the log will show duplicates, gaps, invalid OHLCV, etc. No YAML for this is included below; you can add it by repeating the ticker loop with the audit command.