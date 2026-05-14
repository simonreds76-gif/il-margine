-- Adds row-level coverage metadata used by internal Challenger ML research lanes.
-- Safe to run repeatedly. Columns are nullable so older rows remain valid.

ALTER TABLE daily_fair_odds
  ADD COLUMN IF NOT EXISTS match_count_12m_p1        integer,
  ADD COLUMN IF NOT EXISTS match_count_12m_p2        integer,
  ADD COLUMN IF NOT EXISTS matches_total_p1          integer,
  ADD COLUMN IF NOT EXISTS matches_total_p2          integer,
  ADD COLUMN IF NOT EXISTS recent_challenger_plus_p1 integer,
  ADD COLUMN IF NOT EXISTS recent_challenger_plus_p2 integer,
  ADD COLUMN IF NOT EXISTS last_match_days_p1        integer,
  ADD COLUMN IF NOT EXISTS last_match_days_p2        integer,
  ADD COLUMN IF NOT EXISTS data_coverage_tag         text;

CREATE INDEX IF NOT EXISTS idx_daily_fair_odds_coverage
  ON daily_fair_odds (data_coverage_tag)
  WHERE data_coverage_tag IS NOT NULL;
