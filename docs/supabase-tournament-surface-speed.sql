-- Tournament surface speed (CPI) from Tennis Abstract ATP reports.
-- Source endpoint pattern:
--   https://www.tennisabstract.com/cgi-bin/surface-speed.cgi?year=YYYY
--
-- Suggested usage:
-- 1) Run this SQL once in Supabase.
-- 2) Run scripts/scrape-tennisabstract-surface-speed.py to ingest all years.
-- 3) Keep FAIR_ODDS_CPI_ENABLED=false until validated in backtest/live.

CREATE TABLE IF NOT EXISTS tournament_surface_speed (
  season_year     INTEGER NOT NULL,
  surface         TEXT NOT NULL,
  tournament_name TEXT NOT NULL,
  tournament_key  TEXT NOT NULL,
  cpi             NUMERIC NOT NULL,
  sample_size     INTEGER,
  source_url      TEXT,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (season_year, surface, tournament_key)
);

CREATE INDEX IF NOT EXISTS idx_tournament_surface_speed_year_surface
  ON tournament_surface_speed(season_year, surface);

CREATE INDEX IF NOT EXISTS idx_tournament_surface_speed_tournament_key
  ON tournament_surface_speed(tournament_key);

COMMENT ON TABLE tournament_surface_speed IS
  'ATP tournament CPI/surface-speed ratings by year from Tennis Abstract. Optional input for fair-odds pace adjustments.';

