-- Tournament winner/outright odds from Pinnacle.
-- Populated by pinnacle-scrape-odds.py (outright section).
-- Used by chatbot tournament_entrants tool to answer "is X playing?".

CREATE TABLE IF NOT EXISTS public.tournament_outright_snapshot (
  capture_date DATE NOT NULL,
  tournament_name TEXT NOT NULL,
  league_name TEXT NOT NULL,
  player_name TEXT NOT NULL,
  odds DECIMAL(10,4) NOT NULL,
  rank_in_market INTEGER NOT NULL,
  captured_at TIMESTAMPTZ,
  PRIMARY KEY (capture_date, tournament_name, player_name)
);

CREATE INDEX IF NOT EXISTS idx_tournament_outright_capture
  ON public.tournament_outright_snapshot(capture_date);
CREATE INDEX IF NOT EXISTS idx_tournament_outright_tournament
  ON public.tournament_outright_snapshot(tournament_name);
CREATE INDEX IF NOT EXISTS idx_tournament_outright_player
  ON public.tournament_outright_snapshot(player_name);

COMMENT ON TABLE public.tournament_outright_snapshot IS
  'Daily snapshot of Pinnacle tournament winner odds. One row per (date, tournament, player).';
