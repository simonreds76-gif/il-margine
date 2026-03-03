-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/YOUR_PROJECT/sql
-- Fixes won/lost bets with null settled_at so they appear in Last 7 days P/L

-- 1. Check which bets are affected (run first to see)
SELECT id, event, selection, status, profit_loss, settled_at, posted_at
FROM bets
WHERE status IN ('won', 'lost') AND settled_at IS NULL
ORDER BY posted_at DESC;

-- 2. Set settled_at = NOW() for won/lost with null (so they count in Last 7 days)
UPDATE bets
SET settled_at = NOW()
WHERE status IN ('won', 'lost') AND settled_at IS NULL;

-- 3. Verify - Buse should now have settled_at set
SELECT id, event, status, profit_loss, settled_at FROM bets
WHERE event ILIKE '%Buse%' OR event ILIKE '%Berrettini%'
ORDER BY id DESC LIMIT 5;
