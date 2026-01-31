-- =====================================================
-- Run in Supabase SQL Editor
-- Table for auditing every score calculation (ticker, period, signals_used, score, label).
-- =====================================================

CREATE TABLE IF NOT EXISTS public.score_audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker text NOT NULL,
  period text NOT NULL,
  signals_used jsonb NOT NULL DEFAULT '{}',
  score double precision NOT NULL,
  label text NOT NULL,
  created_at timestamptz DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS score_audit_log_ticker_created_at_idx
ON public.score_audit_log (ticker, created_at DESC);

COMMENT ON TABLE public.score_audit_log IS 'Audit log for every bias score calculation (v2 + SCORE_AUDIT_LOG).';
