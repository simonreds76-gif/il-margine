-- Keep silent-pipeline alerts aligned with pipelines that still have an
-- automatic schedule. Goalscorer settlement and team-props settlement are
-- manual-only during the offseason, so requiring daily heartbeats creates
-- false alerts.

begin;

create or replace view v_silent_pipelines as
with cadence(pipeline, expected_interval, grace_interval) as (
    values
        ('pinnacle-capture-history'::text, interval '30 minutes', interval '75 minutes'),
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

comment on view v_silent_pipelines is
    'Scheduled pipeline heartbeat gaps. Cadence must match currently enabled automatic schedules.';

commit;
