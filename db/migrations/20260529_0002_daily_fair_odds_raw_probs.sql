alter table if exists public.daily_fair_odds
  add column if not exists p1_win_prob_raw double precision,
  add column if not exists p2_win_prob_raw double precision;

comment on column public.daily_fair_odds.p1_win_prob_raw is
  'Pre post-hoc-calibration P1 win probability from the tennis fair-odds pipeline. Used for internal calibration overlays.';

comment on column public.daily_fair_odds.p2_win_prob_raw is
  'Pre post-hoc-calibration P2 win probability from the tennis fair-odds pipeline. Used for internal calibration overlays.';
