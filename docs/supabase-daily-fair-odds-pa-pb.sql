-- Add p_a, p_b (serve point win probabilities) to daily_fair_odds for handicap calculations.
-- Required for handicap_probs: model handicap probs need real (p_a, p_b), not inverted from match prob.
-- Run in Supabase SQL Editor. Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE public.daily_fair_odds
  ADD COLUMN IF NOT EXISTS p_a numeric,
  ADD COLUMN IF NOT EXISTS p_b numeric;

COMMENT ON COLUMN public.daily_fair_odds.p_a IS 'P(player1 wins point on own serve) - from matchup model';
COMMENT ON COLUMN public.daily_fair_odds.p_b IS 'P(player2 wins point on own serve) - from matchup model';
