-- Add handicap (spread) columns to daily_fair_odds.
-- Populated by compute-handicap-values.py after Pinnacle scrape.
-- Run in Supabase SQL Editor. Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE public.daily_fair_odds
  ADD COLUMN IF NOT EXISTS spread_line numeric,
  ADD COLUMN IF NOT EXISTS spread_odds1 numeric,
  ADD COLUMN IF NOT EXISTS spread_odds2 numeric,
  ADD COLUMN IF NOT EXISTS handicap_edge_p1 numeric,
  ADD COLUMN IF NOT EXISTS handicap_edge_p2 numeric;

COMMENT ON COLUMN public.daily_fair_odds.spread_line IS 'Pinnacle game handicap line (e.g. 4.5 = P1 +4.5 / P2 -4.5)';
COMMENT ON COLUMN public.daily_fair_odds.spread_odds1 IS 'Decimal odds for player1 +spread_line';
COMMENT ON COLUMN public.daily_fair_odds.spread_odds2 IS 'Decimal odds for player2 -spread_line';
COMMENT ON COLUMN public.daily_fair_odds.handicap_edge_p1 IS 'Model edge % for backing P1 +spread_line (from handicap_value)';
COMMENT ON COLUMN public.daily_fair_odds.handicap_edge_p2 IS 'Model edge % for backing P2 -spread_line (from handicap_value)';
