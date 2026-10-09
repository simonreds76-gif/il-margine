import 'server-only';
import history from '@/data/tennis-matchday-history.json';
import { buildTennisMatchday } from './tennis-matchday.mjs';

// Two small cached database reads reuse the existing capture, never a bookmaker API.
// Only schedule fields and the paired public match prices are projected.
export async function getTennisMatchday() {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const read = async (params: Record<string, string>) => {
    if (!base || !key) throw new Error('Schedule unavailable');
    const url = new URL('/rest/v1/bookmaker_odds_history', base);
    for (const [name, value] of Object.entries(params)) url.searchParams.set(name, value);
    const response = await fetch(url, { headers: { apikey: key, Authorization: `Bearer ${key}` }, next: { revalidate: 3600 }, signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error('Schedule unavailable');
    return response.json() as Promise<Record<string, unknown>[]>;
  };
  try {
    const common = { bookmaker: 'eq.Pinnacle', league: 'in.(ATP,Challenger)' };
    const latest = await read({ ...common, select: 'captured_at', order: 'captured_at.desc', limit: '1' });
    if (typeof latest[0]?.captured_at !== 'string' || !Number.isFinite(Date.parse(latest[0].captured_at))) throw new Error('Schedule unavailable');
    const rows = await read({ ...common, captured_at: `eq.${latest[0].captured_at}`,
      select: 'captured_at,league,league_name,player1_name,player2_name,match_date,kickoff_iso,odds1,odds2', limit: '250' });
    if (rows.length >= 250 || rows.some(row => row.captured_at !== latest[0].captured_at)) throw new Error('Incomplete schedule');
    return buildTennisMatchday(rows, history);
  } catch {
    // Do not substitute old fixtures, invented times or example matches for a failed feed.
    return buildTennisMatchday([], history);
  }
}
