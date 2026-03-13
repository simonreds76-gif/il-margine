-- H2H table in OnCourt IDs (canonical pair ordering: player_a_id < player_b_id)

create table if not exists public.player_h2h (
  player_a_id integer not null references public.oncourt_players(id) on delete cascade,
  player_b_id integer not null references public.oncourt_players(id) on delete cascade,
  surface text not null,
  wins_a integer not null default 0,
  wins_b integer not null default 0,
  match_count integer not null default 0,
  last_match_date date,
  updated_at timestamptz not null default now(),

  constraint player_h2h_pkey primary key (player_a_id, player_b_id, surface),
  constraint player_h2h_pair_order_chk check (player_a_id < player_b_id),
  constraint player_h2h_nonnegative_chk check (wins_a >= 0 and wins_b >= 0 and match_count >= 0),
  constraint player_h2h_count_chk check (match_count = wins_a + wins_b)
);

create index if not exists idx_player_h2h_player_a on public.player_h2h(player_a_id);
create index if not exists idx_player_h2h_player_b on public.player_h2h(player_b_id);
create index if not exists idx_player_h2h_surface on public.player_h2h(surface);

comment on table public.player_h2h is 'Head-to-head records by player pair and surface using OnCourt player IDs.';
