-- Venue average serve point win % (SPW) per tournament for expected-total-games adjustment.
-- Populate from TML or Sackmann match data: per tour_id (last 3y), venue_avg_spw = total_serve_pts_won / total_serve_pts.
-- Fair-odds uses this to adjust p_a, p_b before K-M: speed_ratio = venue_avg_spw / surface_avg_spw (clamped 0.92–1.08).
-- Minimum match_count >= 50 to use; otherwise no venue adjustment.

CREATE TABLE IF NOT EXISTS tournament_serve_profile (
  tour_id         INTEGER NOT NULL,
  surface        TEXT NOT NULL,
  venue_avg_spw   NUMERIC NOT NULL,
  match_count     INTEGER NOT NULL DEFAULT 0,
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (tour_id, surface)
);

CREATE INDEX IF NOT EXISTS idx_tournament_serve_profile_tour ON tournament_serve_profile(tour_id);

COMMENT ON TABLE tournament_serve_profile IS 'League-avg SPW at this tournament (from match data). Used to adjust p_a/p_b for expected total games.';
