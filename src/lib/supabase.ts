import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

function createSupabaseClient(): SupabaseClient | null {
  if (supabaseUrl && supabaseAnonKey) return createClient(supabaseUrl, supabaseAnonKey);
  return null;
}

const _client = createSupabaseClient();

const noEnvStub = new Proxy({} as SupabaseClient, {
  get() {
    throw new Error(
      'NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are required. Set them in Vercel (Settings → Environment Variables) or .env.local.'
    );
  },
});

/** Supabase client. Throws at first use if env vars are missing (build still succeeds). */
export const supabase: SupabaseClient = _client ?? noEnvStub;

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
  match_date: string | null; // Date when match is played (YYYY-MM-DD)
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
  total_stake?: number; // sum of stake for won+lost (actual units in play)
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
  total_stake?: number; // sum of stake for won+lost (actual units in play)
}
