-- Fix Supabase security advisor: views should use SECURITY INVOKER
-- Run this in Supabase Dashboard → SQL Editor (one shot).
-- Postgres 15+ required (Supabase has it).

ALTER VIEW public.market_stats SET (security_invoker = true);
ALTER VIEW public.category_stats SET (security_invoker = true);
ALTER VIEW public.overall_stats SET (security_invoker = true);

-- If your app uses the anon key to read these views, the underlying tables
-- (e.g. bets) must allow SELECT for anon. If stats stop loading after this,
-- grant SELECT to anon on those tables or adjust RLS so public read is allowed.
