-- Add schedule metadata to Pinnacle bookmaker odds history.
--
-- These columns let CLV audits choose the last pre-match capture by event date/start
-- instead of relying only on player-name pairs and broad date windows.
--
-- Apply with:
--   psql "$DATABASE_URL" -f db/migrations/20260529_0001_bookmaker_odds_history_schedule.sql

begin;

alter table public.bookmaker_odds_history
    add column if not exists match_date date,
    add column if not exists kickoff_iso text;

comment on column public.bookmaker_odds_history.match_date is
    'UTC event date from the Pinnacle matchup schedule, used for CLV join diagnostics.';
comment on column public.bookmaker_odds_history.kickoff_iso is
    'UTC kickoff/start timestamp from the Pinnacle matchup schedule, used for close-price selection.';

create index if not exists bookmaker_odds_history_match_date_idx
    on public.bookmaker_odds_history (match_date);

create index if not exists bookmaker_odds_history_kickoff_iso_idx
    on public.bookmaker_odds_history (kickoff_iso);

commit;
