-- =====================================================
-- Run in Supabase SQL Editor
-- Wide table for computed features per (ticker, timeframe, timestamp).
-- Index for fast retrieval by ticker/timeframe and time range.
-- =====================================================

CREATE TABLE IF NOT EXISTS public.feature_bars (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker text NOT NULL,
  timeframe text NOT NULL DEFAULT '1d',
  "timestamp" timestamptz NOT NULL,
  rsi_14 double precision,
  sma_5 double precision,
  sma_20 double precision,
  sma_100 double precision,
  sma_200 double precision,
  atr_14 double precision,
  adx_14 double precision,
  bbands_20_2 double precision,
  macd_12_26_9 double precision,
  computed_at timestamptz DEFAULT (now() AT TIME ZONE 'utc'),
  feature_metadata jsonb,
  CONSTRAINT feature_bars_ticker_timeframe_timestamp_key UNIQUE (ticker, timeframe, "timestamp")
);

CREATE INDEX IF NOT EXISTS feature_bars_ticker_timeframe_timestamp_idx
ON public.feature_bars (ticker, timeframe, "timestamp");

COMMENT ON TABLE public.feature_bars IS 'Computed indicators per bar; NA when insufficient lookback.';
