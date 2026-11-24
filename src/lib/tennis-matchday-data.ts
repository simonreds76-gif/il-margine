import 'server-only';
import history from '@/data/tennis-matchday-history.json';
import context from '@/data/tennis-matchday-context.json';
import { chooseContext } from './tennis-matchday-context.mjs';
import { buildTennisMatchday } from './tennis-matchday.mjs';

// Two small cached database reads reuse the existing capture, never a bookmaker API.
// Only schedule fields and the paired public match prices are projected.
export async function getTennisMatchday() {
  // Static data published with the existing daily archive release. Preview and
  // production share this hourly cache, without extra odds or model workloads.
  let remote: unknown = null;
  try {
    const response = await fetch('https://ilmargine.bet/tennis-matchday/context.json', { next: { revalidate: 3600 }, signal: AbortSignal.timeout(8000) });
    if (response.ok) remote = await response.json();
  } catch { /* Retain the dated, validated bundled snapshot. */ }
  const latest = chooseContext(remote, context);
  const matchHistory = { ...history, matchdaySupplement: latest?.supplement, matchdayRecent: latest?.recent,
    matchdayPairs: latest?.pairHistory, resultsUpdatedAt: latest?.sourceUpdatedAt,
    matchdayResults: latest?.results, contextVersion: latest?.version };

  const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const now = new Date();
  const day = new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/London', year:'numeric', month:'2-digit', day:'2-digit'}).format(now);
  const programme = (async () => {
    if (!base || !key) return null;
    const path = '/storage/v1/object/authenticated/tennis-price-moves-private/matchday/davis/' + day + '/programme.json';
    try {
      const response = await fetch(new URL(path, base), { headers: { apikey:key, Authorization:'Bearer ' + key }, next:{revalidate:300}, signal:AbortSignal.timeout(5000) });
      return response.ok ? await response.json() : null;
    } catch { return null; }
  })();
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
    return buildTennisMatchday(rows, matchHistory, now, await programme);
  } catch {
    // Do not substitute old fixtures, invented times or example matches for a failed feed.
    return buildTennisMatchday([], matchHistory, now, await programme);
  }
}
