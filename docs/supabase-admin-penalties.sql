-- Private editorial decisions. Only the server's service role may access this table.
begin;
create table if not exists public.admin_penalty_state (
  id text primary key,
  revision integer not null default 0,
  updated_at timestamptz not null default now(),
  payload jsonb not null default '{"tickets":{},"clubs":{},"audit":[]}'::jsonb
);
alter table public.admin_penalty_state enable row level security;
revoke all on public.admin_penalty_state from anon, authenticated;
grant select, insert, update on public.admin_penalty_state to service_role;
insert into public.admin_penalty_state(id) values ('editorial') on conflict do nothing;
-- A restrictive policy composes with the existing public read policy.
drop policy if exists "Private monitor snapshots" on public.goalscorer_live_snapshot;
create policy "Private monitor snapshots" on public.goalscorer_live_snapshot
as restrictive for select to anon, authenticated
using (snapshot_key not in ('monitor_state', 'tennis_evidence_v1'));
commit;
