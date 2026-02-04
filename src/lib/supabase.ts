import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Types for our database
export interface Bookmaker {
  id: number;
  name: string;
  short_name: string;
  affiliate_link: string | null;
  active: boolean;
}

export interface Bet {
  id: number;
  market: 'props' | 'tennis' | 'betbuilders' | 'atg';
  category: string;
  event: string;
  player: string | null;
  selection: string;
  odds: number;
  bookmaker_id: number;
  stake: number;
  status: 'pending' | 'won' | 'lost' | 'void';
  profit_loss: number | null;
  posted_at: string;
  settled_at: string | null;
  notes: string | null;
  // Joined data
  bookmaker?: Bookmaker;
}

export interface MarketStats {
  market: string;
  total_bets: number;
  wins: number;
  losses: number;
  pending: number;
  win_rate: number;
  total_profit: number;
  roi: number;
  avg_odds: number;
  avg_stake: number;
}

export interface CategoryStats {
  market: string;
  category: string;
  total_bets: number;
  wins: number;
  losses: number;
  pending: number;
  win_rate: number;
  total_profit: number;
  roi: number;
  avg_odds: number;
}
