-- Safe performance hotfixes to apply after the Nano -> Micro upgrade.
-- Focus:
--   1. Cover hot foreign keys on read/write tables
--   2. Review and remove duplicate bookmaker_odds_snapshot key/index
-- Do NOT mass-drop "unused" indexes from the linter without validating query plans.

-- ---------------------------------------------------------------------------
-- 1. Foreign-key covering indexes
-- ---------------------------------------------------------------------------

create index concurrently if not exists idx_bets_bookmaker_id
  on public.bets (bookmaker_id);

create index concurrently if not exists idx_daily_fair_odds_player1_id
  on public.daily_fair_odds (player1_id);

create index concurrently if not exists idx_daily_fair_odds_player2_id
  on public.daily_fair_odds (player2_id);

create index concurrently if not exists idx_oncourt_tours_court_id
  on public.oncourt_tours (court_id);

-- ---------------------------------------------------------------------------
-- 2. Review duplicate bookmaker_odds_snapshot key/index before dropping
-- ---------------------------------------------------------------------------

select indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and tablename = 'bookmaker_odds_snapshot'
order by indexname;

select conname, contype
from pg_constraint
where conrelid = 'public.bookmaker_odds_snapshot'::regclass
order by conname;

-- If both of these exist and cover the same columns:
--   bookmaker_odds_snapshot_upsert_key
--   bookmaker_odds_snapshot_capture_date_bookmaker_league_playe_key
-- keep ONE only.
--
-- Prefer keeping the explicit upsert key and dropping the duplicate object
-- after confirming whether the long-named object is an index or constraint.
--
-- Example only: do not run blindly without confirming the exact object type.
--
-- drop index concurrently if exists public.bookmaker_odds_snapshot_capture_date_bookmaker_league_playe_key;
-- alter table public.bookmaker_odds_snapshot drop constraint if exists bookmaker_odds_snapshot_capture_date_bookmaker_league_playe_key;
