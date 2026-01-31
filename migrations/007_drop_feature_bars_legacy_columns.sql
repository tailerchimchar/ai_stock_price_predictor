-- =====================================================
-- Run in Supabase SQL Editor AFTER 006 is verified.
-- Drops legacy scalar columns; all data lives in features jsonb.
-- =====================================================

ALTER TABLE public.feature_bars
  DROP COLUMN IF EXISTS rsi_14,
  DROP COLUMN IF EXISTS sma_5,
  DROP COLUMN IF EXISTS sma_20,
  DROP COLUMN IF EXISTS sma_100,
  DROP COLUMN IF EXISTS sma_200,
  DROP COLUMN IF EXISTS atr_14,
  DROP COLUMN IF EXISTS adx_14,
  DROP COLUMN IF EXISTS bbands_20_2,
  DROP COLUMN IF EXISTS macd_12_26_9;
