-- Add confidence to daily_fair_odds (run in Supabase SQL editor if column missing).
-- Values: 'high' | 'medium' | 'low' | 'none' (none = zero data, 50/50 by construction).
ALTER TABLE daily_fair_odds ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'high';
