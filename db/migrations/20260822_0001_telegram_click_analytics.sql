begin;

alter table public.telegram_clicks
    add column if not exists visitor_hash text,
    add column if not exists country_code text,
    add column if not exists device_type text,
    add column if not exists browser_family text;

comment on table public.telegram_clicks is
    'First-party /go/telegram click events. Raw IP addresses and user-agent strings are never stored.';
comment on column public.telegram_clicks.visitor_hash is
    'Server-side HMAC of network and browser metadata, used only for approximate unique-visitor counts.';
comment on column public.telegram_clicks.country_code is
    'Two-letter country code supplied by the hosting edge, when available.';
comment on column public.telegram_clicks.device_type is
    'Coarse device family: mobile, tablet, desktop or other.';
comment on column public.telegram_clicks.browser_family is
    'Coarse browser family derived from the request user-agent; the raw user-agent is not retained.';

create index if not exists telegram_clicks_visitor_clicked_at_idx
    on public.telegram_clicks (visitor_hash, clicked_at desc)
    where visitor_hash is not null;

create index if not exists telegram_clicks_country_clicked_at_idx
    on public.telegram_clicks (country_code, clicked_at desc)
    where country_code is not null;

commit;
