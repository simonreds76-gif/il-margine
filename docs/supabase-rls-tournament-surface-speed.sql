-- Enable RLS on tournament_surface_speed (fixes Supabase linter: rls_disabled_in_public)
-- Run in Supabase Dashboard → SQL Editor

ALTER TABLE public.tournament_surface_speed ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow_anon_select_tournament_surface_speed" ON public.tournament_surface_speed;
CREATE POLICY "allow_anon_select_tournament_surface_speed"
  ON public.tournament_surface_speed FOR SELECT TO anon USING (true);
