-- =====================================================
-- Run in Supabase SQL Editor
-- Creates price_bars table for canonical OHLCV storage.
-- Uniqueness: (ticker, timeframe, timestamp).
-- =====================================================

CREATE TABLE IF NOT EXISTS public.price_bars (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker text NOT NULL,
  timeframe text NOT NULL DEFAULT '1d',
  "timestamp" timestamptz NOT NULL,
  open double precision NOT NULL,
  high double precision NOT NULL,
  low double precision NOT NULL,
  close double precision NOT NULL,
  volume bigint NOT NULL DEFAULT 0,
  adjusted_close double precision,
  dividends double precision DEFAULT 0,
  splits double precision DEFAULT 0,
  source text DEFAULT 'yfinance',
  created_at timestamptz DEFAULT (now() AT TIME ZONE 'utc'),
  CONSTRAINT price_bars_ticker_timeframe_timestamp_key UNIQUE (ticker, timeframe, "timestamp")
);

CREATE INDEX IF NOT EXISTS price_bars_ticker_timeframe_timestamp_idx
ON public.price_bars (ticker, timeframe, "timestamp");

COMMENT ON TABLE public.price_bars IS 'Canonical OHLCV bars per ticker/timeframe; UTC timestamps.';
