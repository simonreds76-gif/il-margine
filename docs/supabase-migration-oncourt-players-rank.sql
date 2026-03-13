-- Add rank and surface points columns to oncourt_players.
-- Run in Supabase SQL Editor.

ALTER TABLE public.oncourt_players
  ADD COLUMN IF NOT EXISTS atp_rank INTEGER,
  ADD COLUMN IF NOT EXISTS hard_points NUMERIC,
  ADD COLUMN IF NOT EXISTS clay_points NUMERIC,
  ADD COLUMN IF NOT EXISTS grass_points NUMERIC;
