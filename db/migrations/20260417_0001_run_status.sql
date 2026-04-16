-- Slice 2: run_status table + supporting indexes and trigger.
--
-- One row per pipeline run. Source of truth for pipeline health.
-- Replaces mtime-based inference.
--
-- Apply with:
--   psql "$DATABASE_URL" -f db/migrations/20260417_0001_run_status.sql
--
-- Verification (in a psql session after apply):
--   \d run_status
--   insert into run_status (pipeline, host, trigger_kind)
--       values ('smoke', 'local-dev', 'manual');
--   select * from run_status where pipeline = 'smoke';
--   delete from run_status where pipeline = 'smoke';

begin;

create table if not exists run_status (
    run_id         uuid        primary key default gen_random_uuid(),
    pipeline       text        not null,
    host           text        not null,
    trigger_kind   text        not null,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz,
    status         text        not null default 'running',
    rows_in        integer,
    rows_out       integer,
    error_type     text,
    error_message  text,
    details        jsonb       not null default '{}'::jsonb,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),

    constraint run_status_status_chk
        check (status in ('running', 'ok', 'failed', 'timeout', 'aborted')),
    constraint run_status_finished_consistency_chk
        check (
            (status = 'running' and finished_at is null)
            or
            (status <> 'running' and finished_at is not null)
        )
);

comment on table run_status is
    'One row per pipeline run. Source of truth for pipeline health.';
comment on column run_status.pipeline is
    'Stable identifier, e.g. goalscorer-hot-live, pinnacle-corners-clv, oncourt-daily.';
comment on column run_status.host is
    'Where the run executed: github-actions, laptop-win, hetzner-cx11, local-dev.';
comment on column run_status.trigger_kind is
    'What started the run: schedule, workflow_dispatch, manual, watchdog.';
comment on column run_status.details is
    'Free-form per-pipeline diagnostics (source URLs, freshness, skipped counts).';

create index if not exists run_status_pipeline_started_idx
    on run_status (pipeline, started_at desc);

create index if not exists run_status_running_idx
    on run_status (started_at)
    where status = 'running';

create or replace function run_status_set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists run_status_updated_at_trg on run_status;
create trigger run_status_updated_at_trg
    before update on run_status
    for each row execute function run_status_set_updated_at();

commit;
