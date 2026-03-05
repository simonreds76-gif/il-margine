-- player_hand_reference: Left-handed players (L) and right-handed (R) from OnCourt categories.
-- Populated by: python scripts/oncourt-load-player-hand.py (reads data/oncourt/categories_atp.csv)
-- Used by: chat-tools (player_record_vs_lefties), fair-odds model (vs-leftie adjustment)
-- Run in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS public.player_hand_reference (
  player_id INTEGER NOT NULL PRIMARY KEY,
  hand TEXT NOT NULL DEFAULT 'R' CHECK (hand IN ('L', 'R')),
  source TEXT DEFAULT 'oncourt' CHECK (
    source IS NULL
    OR source IN ('oncourt', 'oncourt_categories', 'manual', 'categories_atp', 'atp', 'import', 'script')
  )
);

CREATE INDEX IF NOT EXISTS idx_player_hand_reference_hand ON public.player_hand_reference(hand);

COMMENT ON TABLE public.player_hand_reference IS 'Player handedness from OnCourt categories (cat1=True = left-handed). Used for vs-leftie stats and model adjustments.';
