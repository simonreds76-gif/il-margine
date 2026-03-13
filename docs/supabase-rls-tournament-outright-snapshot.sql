-- Enable RLS on tournament_outright_snapshot (fixes Supabase linter: rls_disabled_in_public)
-- Run in Supabase Dashboard → SQL Editor

ALTER TABLE public.tournament_outright_snapshot ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow_anon_select_tournament_outright_snapshot" ON public.tournament_outright_snapshot;
CREATE POLICY "allow_anon_select_tournament_outright_snapshot"
  ON public.tournament_outright_snapshot FOR SELECT TO anon USING (true);
