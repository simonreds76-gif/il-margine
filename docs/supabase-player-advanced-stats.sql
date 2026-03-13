-- Advanced serve/return profile in OnCourt IDs, per player + surface

create table if not exists public.player_advanced_stats (
  player_id integer not null references public.oncourt_players(id) on delete cascade,
  surface text not null,

  first_serve_pct numeric(7,4),
  first_serve_win_pct numeric(7,4),
  second_serve_win_pct numeric(7,4),
  ace_rate numeric(7,4),
  df_rate numeric(7,4),
  bp_save_pct numeric(7,4),
  bp_convert_pct numeric(7,4),

  match_count integer not null default 0,
  service_points integer not null default 0,
  service_games integer not null default 0,

  first_serves_in integer not null default 0,
  first_serve_points_won integer not null default 0,
  second_serve_points integer not null default 0,
  second_serve_points_won integer not null default 0,

  aces integer not null default 0,
  double_faults integer not null default 0,
  break_points_saved integer not null default 0,
  break_points_faced integer not null default 0,

  return_break_points_converted integer not null default 0,
  return_break_points_chances integer not null default 0,

  updated_at timestamptz not null default now(),

  constraint player_advanced_stats_pkey primary key (player_id, surface),

  constraint player_advanced_stats_nonnegative_chk check (
    match_count >= 0 and
    service_points >= 0 and
    service_games >= 0 and
    first_serves_in >= 0 and
    first_serve_points_won >= 0 and
    second_serve_points >= 0 and
    second_serve_points_won >= 0 and
    aces >= 0 and
    double_faults >= 0 and
    break_points_saved >= 0 and
    break_points_faced >= 0 and
    return_break_points_converted >= 0 and
    return_break_points_chances >= 0
  ),

  constraint player_advanced_stats_pct_chk check (
    (first_serve_pct is null or (first_serve_pct >= 0 and first_serve_pct <= 1)) and
    (first_serve_win_pct is null or (first_serve_win_pct >= 0 and first_serve_win_pct <= 1)) and
    (second_serve_win_pct is null or (second_serve_win_pct >= 0 and second_serve_win_pct <= 1)) and
    (ace_rate is null or (ace_rate >= 0 and ace_rate <= 1)) and
    (df_rate is null or (df_rate >= 0 and df_rate <= 1)) and
    (bp_save_pct is null or (bp_save_pct >= 0 and bp_save_pct <= 1)) and
    (bp_convert_pct is null or (bp_convert_pct >= 0 and bp_convert_pct <= 1))
  )
);

create index if not exists idx_player_advanced_stats_surface on public.player_advanced_stats(surface);

comment on table public.player_advanced_stats is 'Advanced serve/return stats by player and surface using OnCourt player IDs.';
