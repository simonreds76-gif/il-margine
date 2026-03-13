-- Enable RLS on public tables reported by Supabase Database Linter (rls_disabled_in_public).
-- Run in Supabase Dashboard → SQL Editor (run the whole file or run table-by-table).
-- After this: service_role (scripts/API) keeps full access; anon gets SELECT only.
-- If a table does not exist, comment out or skip that block.
-- Ref: https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public

-- 1. sackmann_matches
ALTER TABLE public.sackmann_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_sackmann_matches"
  ON public.sackmann_matches FOR SELECT TO anon USING (true);

-- 2. sackmann_players
ALTER TABLE public.sackmann_players ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_sackmann_players"
  ON public.sackmann_players FOR SELECT TO anon USING (true);

-- 3. player_hand_reference
ALTER TABLE public.player_hand_reference ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_player_hand_reference"
  ON public.player_hand_reference FOR SELECT TO anon USING (true);

-- 4. tml_matches
ALTER TABLE public.tml_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_tml_matches"
  ON public.tml_matches FOR SELECT TO anon USING (true);

-- 5. surface_league_averages
ALTER TABLE public.surface_league_averages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_surface_league_averages"
  ON public.surface_league_averages FOR SELECT TO anon USING (true);

-- 6. player_recent_activity
ALTER TABLE public.player_recent_activity ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_player_recent_activity"
  ON public.player_recent_activity FOR SELECT TO anon USING (true);

-- 7. tournament_game_averages
ALTER TABLE public.tournament_game_averages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_tournament_game_averages"
  ON public.tournament_game_averages FOR SELECT TO anon USING (true);

-- 8. tournament_serve_profile
ALTER TABLE public.tournament_serve_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_tournament_serve_profile"
  ON public.tournament_serve_profile FOR SELECT TO anon USING (true);

-- 9. player_id_map
ALTER TABLE public.player_id_map ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_player_id_map"
  ON public.player_id_map FOR SELECT TO anon USING (true);

-- 10. bookmaker_odds_snapshot
ALTER TABLE public.bookmaker_odds_snapshot ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_bookmaker_odds_snapshot"
  ON public.bookmaker_odds_snapshot FOR SELECT TO anon USING (true);

-- 11. player_h2h
ALTER TABLE public.player_h2h ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_player_h2h"
  ON public.player_h2h FOR SELECT TO anon USING (true);

-- 12. player_advanced_stats
ALTER TABLE public.player_advanced_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_player_advanced_stats"
  ON public.player_advanced_stats FOR SELECT TO anon USING (true);

-- 13. tournament_surface_speed
ALTER TABLE public.tournament_surface_speed ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_tournament_surface_speed"
  ON public.tournament_surface_speed FOR SELECT TO anon USING (true);

-- 14. tournament_outright_snapshot
ALTER TABLE public.tournament_outright_snapshot ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_anon_select_tournament_outright_snapshot"
  ON public.tournament_outright_snapshot FOR SELECT TO anon USING (true);
