-- Append-only anytime-goalscorer odds history.
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS public.goalscorer_odds_history (
  id BIGSERIAL PRIMARY KEY,
  capture_date DATE NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  match_date DATE NOT NULL,
  event_id TEXT,
  kickoff_at TIMESTAMPTZ,
  minutes_to_kickoff NUMERIC(10,1),
  snapshot_kind TEXT,
  bookmaker TEXT NOT NULL,
  competition TEXT NOT NULL DEFAULT 'Serie A',
  market TEXT NOT NULL DEFAULT 'ATGS',
  home_team TEXT NOT NULL,
  away_team TEXT NOT NULL,
  player_name TEXT NOT NULL,
  player_team TEXT,
  odds_decimal NUMERIC(10,4) NOT NULL,
  implied_prob NUMERIC(12,6),
  source TEXT NOT NULL DEFAULT 'manual',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_goalscorer_odds_history_upsert
  ON public.goalscorer_odds_history (
    captured_at,
    bookmaker,
    competition,
    market,
    match_date,
    home_team,
    away_team,
    player_name
  );

CREATE INDEX IF NOT EXISTS idx_goalscorer_odds_history_match_date
  ON public.goalscorer_odds_history (match_date, bookmaker);

CREATE INDEX IF NOT EXISTS idx_goalscorer_odds_history_player
  ON public.goalscorer_odds_history (player_name, player_team);

COMMENT ON TABLE public.goalscorer_odds_history IS
  'Append-only anytime-goalscorer odds archive for model-vs-market comparison.';
