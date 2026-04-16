begin;

create or replace view v_pipeline_health as
with recent_runs as (
    select
        pipeline,
        host,
        trigger_kind,
        status,
        started_at,
        finished_at,
        rows_in,
        rows_out,
        error_type,
        error_message,
        details,
        row_number() over (partition by pipeline order by started_at desc) as rn
    from run_status
),
counts_24h as (
    select
        pipeline,
        count(*) filter (where started_at >= now() - interval '24 hours') as runs_24h,
        count(*) filter (where started_at >= now() - interval '24 hours' and status = 'ok') as ok_24h,
        count(*) filter (where started_at >= now() - interval '24 hours' and status = 'failed') as failed_24h,
        count(*) filter (where started_at >= now() - interval '24 hours' and status = 'running') as running_24h
    from run_status
    group by pipeline
)
select
    r.pipeline,
    r.host,
    r.trigger_kind,
    r.status as last_status,
    r.started_at as last_started_at,
    r.finished_at as last_finished_at,
    extract(epoch from (coalesce(r.finished_at, now()) - r.started_at))::double precision as last_duration_seconds,
    r.rows_in as last_rows_in,
    r.rows_out as last_rows_out,
    r.error_type as last_error_type,
    r.error_message as last_error_message,
    r.details as last_details,
    coalesce(c.runs_24h, 0) as runs_24h,
    coalesce(c.ok_24h, 0) as ok_24h,
    coalesce(c.failed_24h, 0) as failed_24h,
    coalesce(c.running_24h, 0) as running_24h
from recent_runs r
left join counts_24h c on c.pipeline = r.pipeline
where r.rn = 1;

create or replace view v_stuck_runs as
select
    pipeline,
    host,
    trigger_kind,
    run_id,
    started_at,
    extract(epoch from (now() - started_at))::double precision as age_seconds,
    rows_in,
    rows_out,
    details
from run_status
where status = 'running'
  and started_at <= now() - interval '15 minutes'
order by started_at asc;

create or replace view v_silent_pipelines as
with cadence(pipeline, expected_interval, grace_interval) as (
    values
        ('pinnacle-capture-history'::text, interval '30 minutes', interval '75 minutes'),
        ('fetch-results-snapshot'::text, interval '24 hours', interval '36 hours'),
        ('goalscorer-settle'::text, interval '24 hours', interval '36 hours'),
        ('team-props'::text, interval '24 hours', interval '36 hours'),
        ('oncourt-daily'::text, interval '24 hours', interval '36 hours'),
        ('oncourt-am-refresh'::text, interval '24 hours', interval '36 hours'),
        ('oncourt-weekly'::text, interval '7 days', interval '9 days')
),
latest as (
    select
        pipeline,
        max(started_at) as last_started_at,
        max(finished_at) as last_finished_at
    from run_status
    group by pipeline
)
select
    c.pipeline,
    c.expected_interval,
    c.grace_interval,
    l.last_started_at,
    l.last_finished_at,
    extract(epoch from (now() - l.last_started_at))::double precision as seconds_since_last_start
from cadence c
left join latest l on l.pipeline = c.pipeline
where l.last_started_at is null
   or l.last_started_at <= now() - c.grace_interval
order by c.pipeline;

commit;
