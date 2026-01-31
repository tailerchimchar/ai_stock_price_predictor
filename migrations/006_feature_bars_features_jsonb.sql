-- =====================================================
-- Run in Supabase SQL Editor
-- Add single JSONB column `features` for all computed indicators;
-- backfill from existing scalar columns. Keeps legacy columns for now.
-- =====================================================

ALTER TABLE public.feature_bars
ADD COLUMN IF NOT EXISTS features jsonb DEFAULT '{}';

-- Backfill: build features from existing columns (only non-null values)
UPDATE public.feature_bars
SET features = jsonb_strip_nulls(
  jsonb_build_object(
    'rsi_14', rsi_14,
    'sma_5', sma_5,
    'sma_20', sma_20,
    'sma_100', sma_100,
    'sma_200', sma_200,
    'atr_14', atr_14,
    'adx_14', adx_14,
    'bbands_20_2', bbands_20_2,
    'macd_12_26_9', macd_12_26_9
  )
)
WHERE features IS NULL OR features = '{}';

COMMENT ON COLUMN public.feature_bars.features IS 'All computed indicators as key-value; add new keys without schema change.';
