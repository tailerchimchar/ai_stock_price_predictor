-- =====================================================
-- Run in Supabase SQL Editor
-- B-tree indexes for analysis_db lookups
-- =====================================================
-- Your unique constraint (ticker, period, user_id) already creates a
-- unique B-tree index, so upsert/conflict lookups are already indexed.
-- Below adds an index for list_analyses and get_latest_analysis:
--   WHERE ticker = ? AND user_id = ? ORDER BY created_at DESC
-- =====================================================

-- List/latest by ticker + user_id, newest first (avoids sort)
CREATE INDEX IF NOT EXISTS analysis_db_ticker_user_id_created_at_idx
ON public.analysis_db (ticker, user_id, created_at DESC);
