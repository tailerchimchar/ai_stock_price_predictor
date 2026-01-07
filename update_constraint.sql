-- CRITICAL: Update unique constraint to include user_id
-- Run this in Supabase SQL Editor BEFORE testing

-- Drop the old constraint (if exists)
ALTER TABLE public.analysis_db 
DROP CONSTRAINT IF EXISTS analysis_db_ticker_period_key;

-- Add new constraint with user_id
ALTER TABLE public.analysis_db
ADD CONSTRAINT analysis_db_ticker_period_user_id_key
UNIQUE (ticker, period, user_id);

-- Verify the constraint was created
SELECT 
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS constraint_definition
FROM pg_constraint
WHERE conrelid = 'public.analysis_db'::regclass
  AND contype = 'u';  -- unique constraints
