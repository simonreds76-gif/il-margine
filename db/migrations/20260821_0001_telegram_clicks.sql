begin;

create table if not exists public.telegram_clicks (
    id          bigint generated always as identity primary key,
    source      text        not null default 'unknown',
    clicked_at  timestamptz not null default now(),

    constraint telegram_clicks_source_length_chk
        check (char_length(source) between 1 and 64)
);

comment on table public.telegram_clicks is
    'First-party click count for internal /go/telegram calls to action. Contains no IP address or personal data.';
comment on column public.telegram_clicks.source is
    'Sanitized CTA placement identifier, for example homepage_hero or player_props_alerts.';

create index if not exists telegram_clicks_clicked_at_idx
    on public.telegram_clicks (clicked_at desc);

create index if not exists telegram_clicks_source_clicked_at_idx
    on public.telegram_clicks (source, clicked_at desc);

alter table public.telegram_clicks enable row level security;

-- No public policies: only server-side service-role routes may read or write clicks.
revoke all on table public.telegram_clicks from anon, authenticated;
revoke all on sequence public.telegram_clicks_id_seq from anon, authenticated;

commit;
