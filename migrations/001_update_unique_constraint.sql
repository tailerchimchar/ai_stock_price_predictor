-- =====================================================
-- IMPORTANT: Run this in Supabase SQL Editor
-- =====================================================
-- This updates the unique constraint to include user_id
-- so multiple users can store analyses for the same ticker/period

-- 1. Drop old unique constraint (ticker, period)
ALTER TABLE public.analysis_db 
DROP CONSTRAINT IF EXISTS analysis_db_ticker_period_key;

-- 2. Add new unique constraint (ticker, period, user_id)
ALTER TABLE public.analysis_db
ADD CONSTRAINT analysis_db_ticker_period_user_id_key
UNIQUE (ticker, period, user_id);

-- 3. Verify constraint exists
SELECT conname, contype, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'public.analysis_db'::regclass 
AND contype = 'u';
