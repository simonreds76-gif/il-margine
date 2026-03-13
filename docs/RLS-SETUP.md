# RLS Setup (Supabase Row Level Security)

When Supabase reports **RLS Disabled in Public** for a table, enable RLS and add a read policy.

## Quick fix (tournament_surface_speed + tournament_outright_snapshot)

**[supabase-rls-fix-both.sql](./supabase-rls-fix-both.sql)** — Ctrl+click to open (or find it in the explorer under `docs/`), copy all, paste into Supabase SQL Editor, run.

## Individual files

- [docs/supabase-rls-tournament-surface-speed.sql](supabase-rls-tournament-surface-speed.sql) — `tournament_surface_speed` only
- [docs/supabase-rls-tournament-outright-snapshot.sql](supabase-rls-tournament-outright-snapshot.sql) — `tournament_outright_snapshot` only

## All public tables

**[docs/supabase-enable-rls-public-tables.sql](supabase-enable-rls-public-tables.sql)** — full list for all tables reported by the linter.
