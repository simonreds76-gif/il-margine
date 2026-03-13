-- Migration: Create player_surface_stats_v2 (decomposed serve/return stats)
-- Run in Supabase SQL Editor BEFORE oncourt-compute-player-stats-extended.py
--
-- Extends player_surface_stats with:
--   Serve: first_serve_pct, first_serve_win_pct, second_serve_win_pct, ace_rate, df_rate
--   Return: ret_vs_first_win_pct, ret_vs_second_win_pct (decomposed)
--   Pressure: bp_save_rate, bp_convert_rate
--   All with 12m and 36m (long) variants

CREATE TABLE IF NOT EXISTS player_surface_stats_v2 (
  player_id INTEGER NOT NULL,
  surface TEXT NOT NULL,
  match_count INTEGER,
  service_pts INTEGER,
  return_pts INTEGER,

  -- Base (12m)
  hold_pct NUMERIC,
  return_pct NUMERIC,

  -- Base (36m)
  hold_pct_long NUMERIC,
  return_pct_long NUMERIC,
  match_count_long INTEGER,

  -- Serve decomposition (12m)
  first_serve_pct NUMERIC,
  first_serve_win_pct NUMERIC,
  second_serve_win_pct NUMERIC,
  ace_rate NUMERIC,
  df_rate NUMERIC,

  -- Pressure (12m)
  bp_save_rate NUMERIC,
  bp_convert_rate NUMERIC,

  -- Return decomposition (12m)
  ret_vs_first_win_pct NUMERIC,
  ret_vs_second_win_pct NUMERIC,

  -- Raw counts
  aces_total INTEGER,
  dfs_total INTEGER,
  bp_faced_total INTEGER,
  bp_saved_total INTEGER,
  ret_vs_first_faced_total INTEGER,
  ret_vs_second_faced_total INTEGER,

  -- Serve decomposition (36m)
  first_serve_pct_long NUMERIC,
  first_serve_win_pct_long NUMERIC,
  second_serve_win_pct_long NUMERIC,
  ace_rate_long NUMERIC,
  df_rate_long NUMERIC,
  bp_save_rate_long NUMERIC,
  bp_convert_rate_long NUMERIC,

  -- Return decomposition (36m)
  ret_vs_first_win_pct_long NUMERIC,
  ret_vs_second_win_pct_long NUMERIC,

  PRIMARY KEY (player_id, surface)
);

CREATE INDEX IF NOT EXISTS idx_player_surface_stats_v2_player ON player_surface_stats_v2(player_id);
CREATE INDEX IF NOT EXISTS idx_player_surface_stats_v2_surface ON player_surface_stats_v2(surface);
