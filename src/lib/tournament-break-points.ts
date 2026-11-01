type Row = Record<string, unknown>;
const str = (v: unknown) => typeof v === 'string' || typeof v === 'number' ? String(v) : '';
const count = (v: unknown): number | null => {
  if (v === null || v === undefined || typeof v === 'boolean' || !str(v).trim()) return null;
  const n = Number(v);
  return Number.isInteger(n) && n >= 0 ? n : null;
};
export type BreakPointRound = {
  date: string; round: string; opponent: string; result: string; partial: boolean;
  created: number | null; converted: number | null; faced: number | null;
  matchChances: number | null; valid: boolean; key: string; roundOrder: number;
};

export function breakPointHistory(row: Row) {
  let source: unknown = row.break_point_history;
  try { if (typeof source === 'string') source = JSON.parse(source); } catch { source = null; }
  const data = source && typeof source === 'object' && !Array.isArray(source) ? source as Row : null;
  const cutoff = str(row.date).slice(0, 10);
  const available = Boolean(data?.version === 'tournament-break-points-v1'
    && str(data.player_id) === str(row.player_id).replace(/^oc:/, '')
    && str(data.tour_id) === str(row.tour_id) && str(data.before_date) === cutoff
    && (!row.tour || str(row.tour).toUpperCase() === str(data.tour)) && Array.isArray(data.logs));
  const logs: BreakPointRound[] = [];
  const seen = new Set<string>();
  // Draw sizes differ: native round codes alone do not establish R32/R64 or
  // the number of qualifying rounds. Do not manufacture those labels.
  const rounds: Record<string,string> = {'1':'Qualifying','2':'Qualifying','3':'Qualifying',
    '4':'Main draw','5':'Main draw','6':'Main draw','7':'Main draw','9':'QF','10':'SF','12':'Final'};
  if (available) for (const item of data!.logs as unknown[]) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const r = item as Row, key = str(r.source_key), day = str(r.date);
    if (!key || seen.has(key) || !/^\d{4}-\d{2}-\d{2}$/.test(day) || day >= cutoff || !str(r.opponent)) continue;
    seen.add(key);
    const created = count(r.created), converted = count(r.converted), faced = count(r.faced), saved = count(r.saved);
    const valid = r.stats_status === 'verified' && !r.issue && created !== null && converted !== null
      && faced !== null && saved !== null && converted <= created && saved <= faced;
    logs.push({key, date: day, roundOrder: count(r.round_id) ?? 99, round: rounds[str(r.round_id)] || 'Recorded match',
      opponent: str(r.opponent), result: str(r.result), partial: r.status !== 'completed', valid,
      created: valid ? created : null, converted: valid ? converted : null, faced: valid ? faced : null,
      matchChances: valid ? created! + faced! : null});
  }
  logs.sort((a,b) => a.date.localeCompare(b.date) || a.roundOrder - b.roundOrder || a.key.localeCompare(b.key));
  const completed = logs.filter(r => !r.partial), covered = completed.filter(r => r.valid);
  const sum = (field: 'created' | 'converted' | 'faced') => covered.length ? covered.reduce((n,r) => n + r[field]!, 0) : null;
  return {available, cutoff, logs, completed: completed.length, covered: covered.length,
    partial: logs.length - completed.length, created: sum('created'), converted: sum('converted'), faced: sum('faced')};
}
