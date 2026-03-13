-- Add game handicap (spread) columns to bookmaker_odds_snapshot
-- Run in Supabase SQL Editor before first scrape with spread data.
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE public.bookmaker_odds_snapshot
  ADD COLUMN IF NOT EXISTS spread_line numeric,
  ADD COLUMN IF NOT EXISTS spread_odds1 numeric,
  ADD COLUMN IF NOT EXISTS spread_odds2 numeric;

COMMENT ON COLUMN public.bookmaker_odds_snapshot.spread_line IS 'Game handicap line (e.g. 4.5 = P1 +4.5 / P2 -4.5)';
COMMENT ON COLUMN public.bookmaker_odds_snapshot.spread_odds1 IS 'Decimal odds for player1 +spread_line';
COMMENT ON COLUMN public.bookmaker_odds_snapshot.spread_odds2 IS 'Decimal odds for player2 -spread_line';
