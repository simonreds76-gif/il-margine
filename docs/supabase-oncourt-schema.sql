-- Phase 1.2: OnCourt tables for fair odds pipeline
-- Run in Supabase SQL Editor: Dashboard → SQL Editor → New query

-- Courts (surfaces): Hard, Clay, Grass, etc.
CREATE TABLE IF NOT EXISTS oncourt_courts (
  id INTEGER PRIMARY KEY,
  name TEXT
);

-- Players
CREATE TABLE IF NOT EXISTS oncourt_players (
  id INTEGER PRIMARY KEY,
  name TEXT,
  birthdate DATE,
  country TEXT
);

-- Tours (tournaments) - links to court for surface
CREATE TABLE IF NOT EXISTS oncourt_tours (
  id INTEGER PRIMARY KEY,
  name TEXT,
  court_id INTEGER REFERENCES oncourt_courts(id),
  date DATE,
  rank INTEGER,
  country TEXT
);

-- Matches
CREATE TABLE IF NOT EXISTS oncourt_games (
  winner_id INTEGER REFERENCES oncourt_players(id),
  loser_id INTEGER REFERENCES oncourt_players(id),
  tour_id INTEGER REFERENCES oncourt_tours(id),
  round_id INTEGER,
  result TEXT,
  date DATE,
  PRIMARY KEY (winner_id, loser_id, tour_id, round_id)
);

CREATE INDEX IF NOT EXISTS idx_games_winner ON oncourt_games(winner_id);
CREATE INDEX IF NOT EXISTS idx_games_loser ON oncourt_games(loser_id);
CREATE INDEX IF NOT EXISTS idx_games_tour ON oncourt_games(tour_id);
CREATE INDEX IF NOT EXISTS idx_games_date ON oncourt_games(date);

-- Match stats (serve/return)
CREATE TABLE IF NOT EXISTS oncourt_stat (
  winner_id INTEGER,
  loser_id INTEGER,
  tour_id INTEGER,
  round_id INTEGER,
  w_fs INTEGER, w_fsof INTEGER, w_w1s INTEGER, w_w1sof INTEGER, w_w2s INTEGER, w_w2sof INTEGER, w_rpw INTEGER, w_rpwof INTEGER,
  l_fs INTEGER, l_fsof INTEGER, l_w1s INTEGER, l_w1sof INTEGER, l_w2s INTEGER, l_w2sof INTEGER, l_rpw INTEGER, l_rpwof INTEGER,
  PRIMARY KEY (winner_id, loser_id, tour_id, round_id)
);

CREATE INDEX IF NOT EXISTS idx_stat_winner ON oncourt_stat(winner_id);
CREATE INDEX IF NOT EXISTS idx_stat_loser ON oncourt_stat(loser_id);

-- Today's fixtures
CREATE TABLE IF NOT EXISTS oncourt_today (
  tour_id INTEGER,
  player1_id INTEGER,
  player2_id INTEGER,
  round_id INTEGER,
  draw INTEGER,
  result TEXT
);

-- Note: Run this schema before loading. RLS is off by default for SQL-created tables.
