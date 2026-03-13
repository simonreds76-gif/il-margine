-- Append-only Pinnacle odds history for CLV / near-close analysis.
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS public.bookmaker_odds_history (
  id BIGSERIAL PRIMARY KEY,
  capture_date DATE NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  capture_mode TEXT NOT NULL DEFAULT 'snapshot',
  bookmaker TEXT NOT NULL,
  league TEXT NOT NULL,
  league_name TEXT,
  player1_name TEXT NOT NULL,
  player2_name TEXT NOT NULL,
  odds1 NUMERIC(10,4) NOT NULL,
  odds2 NUMERIC(10,4) NOT NULL,
  pinnacle_margin NUMERIC(10,4),
  ou_line NUMERIC(10,2),
  ou_over NUMERIC(10,4),
  ou_under NUMERIC(10,4),
  spread_line NUMERIC(10,2),
  spread_odds1 NUMERIC(10,4),
  spread_odds2 NUMERIC(10,4)
);

CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_history_capture_date
  ON public.bookmaker_odds_history (capture_date, bookmaker, league);

CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_history_captured_at
  ON public.bookmaker_odds_history (captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_history_players
  ON public.bookmaker_odds_history (player1_name, player2_name);

CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_history_capture_mode
  ON public.bookmaker_odds_history (capture_mode, capture_date);

COMMENT ON TABLE public.bookmaker_odds_history IS
  'Append-only Pinnacle odds capture history for CLV analysis and near-close reconstruction.';

COMMENT ON COLUMN public.bookmaker_odds_history.capture_mode IS
  'Capture source tag, e.g. daily, close, intraday.';
