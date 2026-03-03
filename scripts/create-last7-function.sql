-- Run in Supabase SQL Editor to create a function that calculates last 7 days P/L in the database

CREATE OR REPLACE FUNCTION get_last7_profit()
RETURNS TABLE(total_profit numeric, bet_count bigint)
LANGUAGE sql
SECURITY DEFINER
AS $$
  SELECT 
    COALESCE(SUM(profit_loss::numeric), 0)::numeric as total_profit,
    COUNT(*)::bigint as bet_count
  FROM bets
  WHERE status IN ('won', 'lost')
    AND settled_at IS NOT NULL
    AND settled_at >= (NOW() AT TIME ZONE 'UTC' - INTERVAL '7 days');
$$;
