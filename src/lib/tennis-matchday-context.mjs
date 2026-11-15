// One validated dated snapshot, never an invented current timestamp.
export function validContext(value, now = new Date()) {
  if (!value || value.schema !== 1 || !/^[a-f0-9]{24}$/.test(value.version || '') || !/^\d{4}-\d{2}-\d{2}$/.test(value.asOf || '')) return false;
  const updated = Date.parse(value.sourceUpdatedAt);
  if (!Number.isFinite(updated) || updated > now.getTime()+300000 || value.sourceUpdatedAt.slice(0,10) !== value.asOf) return false;
  const results=value.results;
  if (!results || results.before !== value.asOf || !Array.isArray(results.matches) || !value.recent?.players || !value.supplement?.pairs || !value.pairHistory) return false;
  if (results.matches.some(r => !r.id || !['ATP','Challenger'].includes(r.tour) || !['completed','retired','walkover'].includes(r.status) || r.players?.length !== 2 || r.winner !== 0 || r.date < results.from || r.date >= results.before)) return false;
  return true;
}
export function chooseContext(remote, bundled, now = new Date()) {
  const candidates=[remote,bundled].filter(v=>validContext(v,now));
  candidates.sort((a,b)=>b.sourceUpdatedAt.localeCompare(a.sourceUpdatedAt));
  return candidates[0] ?? null;
}
