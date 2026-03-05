-- Fix player_hand_reference so OnCourt load works.
-- Run once in Supabase SQL Editor if you get: player_hand_reference_source_check
-- Or: the load scripts auto-negotiate source payload and only need this for legacy schemas.

DO $$
BEGIN
  -- 1. Add source column if missing
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'player_hand_reference' AND column_name = 'source'
  ) THEN
    ALTER TABLE public.player_hand_reference ADD COLUMN source TEXT DEFAULT 'oncourt';
  END IF;

  -- 2. Drop old constraint (if it exists)
  ALTER TABLE public.player_hand_reference DROP CONSTRAINT IF EXISTS player_hand_reference_source_check;

  -- 3. Make source nullable with default
  ALTER TABLE public.player_hand_reference ALTER COLUMN source DROP NOT NULL;
  ALTER TABLE public.player_hand_reference ALTER COLUMN source SET DEFAULT 'oncourt';

  -- 4. Add new constraint allowing our values
  ALTER TABLE public.player_hand_reference ADD CONSTRAINT player_hand_reference_source_check
    CHECK (source IS NULL OR source IN ('oncourt', 'oncourt_categories', 'manual', 'categories_atp', 'atp', 'import', 'script'));
EXCEPTION
  WHEN duplicate_object THEN NULL;  -- constraint already exists, ignore
END $$;
