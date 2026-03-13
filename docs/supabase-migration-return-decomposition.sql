-- Migration: Add decomposed return stats to player_surface_stats_v2
-- Run in Supabase SQL Editor.
--
-- New columns:
--   ret_vs_first_win_pct  = return points won vs opponent's 1st serve / faced
--   ret_vs_second_win_pct = return points won vs opponent's 2nd serve / faced
--   (plus long-window and raw count variants)

ALTER TABLE player_surface_stats_v2
  ADD COLUMN IF NOT EXISTS ret_vs_first_win_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS ret_vs_second_win_pct NUMERIC,
  ADD COLUMN IF NOT EXISTS ret_vs_first_win_pct_long NUMERIC,
  ADD COLUMN IF NOT EXISTS ret_vs_second_win_pct_long NUMERIC,
  ADD COLUMN IF NOT EXISTS ret_vs_first_faced_total INTEGER,
  ADD COLUMN IF NOT EXISTS ret_vs_second_faced_total INTEGER;
