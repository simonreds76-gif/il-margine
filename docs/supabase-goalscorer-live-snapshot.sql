create table if not exists public.goalscorer_live_snapshot (
  snapshot_key text primary key,
  updated_at timestamptz not null default now(),
  payload jsonb not null default '{}'::jsonb
);

alter table public.goalscorer_live_snapshot enable row level security;

drop policy if exists "Public read goalscorer live snapshot" on public.goalscorer_live_snapshot;
create policy "Public read goalscorer live snapshot"
on public.goalscorer_live_snapshot
for select
using (true);

comment on table public.goalscorer_live_snapshot is
  'Hosted snapshot of live goalscorer CSV/TXT/JSON outputs for deployed Next.js pages.';
