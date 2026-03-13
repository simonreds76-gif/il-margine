-- Fix RLS for tournament_surface_speed and tournament_outright_snapshot
-- Run in Supabase Dashboard → SQL Editor (paste and run)
-- See docs/RLS-SETUP.md for clickable links

-- tournament_surface_speed
ALTER TABLE public.tournament_surface_speed ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_anon_select_tournament_surface_speed" ON public.tournament_surface_speed;
CREATE POLICY "allow_anon_select_tournament_surface_speed"
  ON public.tournament_surface_speed FOR SELECT TO anon USING (true);

-- tournament_outright_snapshot
ALTER TABLE public.tournament_outright_snapshot ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_anon_select_tournament_outright_snapshot" ON public.tournament_outright_snapshot;
CREATE POLICY "allow_anon_select_tournament_outright_snapshot"
  ON public.tournament_outright_snapshot FOR SELECT TO anon USING (true);
