/** Compact display adapter only. Never recalculates selections or combines cohorts. */
type Obj = Record<string, unknown>;
export const obj = (v: unknown): Obj => v && typeof v === "object" && !Array.isArray(v) ? v as Obj : {};
const num = (v: unknown): number | null => typeof v === "number" && Number.isFinite(v) ? v : null;
const str = (v: unknown): string | null => typeof v === "string" && v.length > 0 ? v : null;
export type ModelRow = {
  id: string; name: string; group: string; cohort: string; note: string;
  date: string | null; settled: number | null; pending: number | null;
  wins: number | null; losses: number | null; stake: number | null;
  profit: number | null; roi: number | null; status: string | null;
};
export function row(id: string, name: string, group: string, cohort: string, raw: unknown, date: unknown, note = "", ratio = false): ModelRow {
  const r = obj(raw), record = obj(r.record);
  const roi = num(r.roi_pct) ?? (ratio && num(r.roi) !== null ? Number(r.roi) * 100 : null);
  return { id, name, group, cohort, note, date: str(date), status: str(r.status),
    settled: num(r.settled), pending: num(r.pending), wins: num(r.wins) ?? num(record.wins),
    losses: num(r.losses) ?? num(record.losses), stake: num(r.stake_units) ?? num(r.staked_units),
    profit: num(r.pnl_units), roi: num(r.settled) === 0 ? null : roi };
}
export function snapshotAge(date: string | null, now: number): "Recent" | "Stale" | "Date unavailable" {
  const t = Date.parse(date ?? "");
  if (!Number.isFinite(t) || t > now + 300000) return "Date unavailable";
  return now - t > 48 * 3600000 ? "Stale" : "Recent";
}
export function modelRows(sections: unknown, football: unknown): ModelRow[] {
  const s = obj(sections), f = obj(football), evidence = obj(s.tennis_model_evidence), lanes = obj(evidence.lanes);
  const rows: ModelRow[] = [];
  for (const [id, name] of [["strict", "Tennis Strict"], ["volume_200", "Tennis Volume 200"], ["challenger", "Challenger"], ["spread_v1", "Tennis handicaps v1"], ["provisional_hard", "Provisional Hard"], ["provisional_expansion", "Provisional Expansion"]]) {
    const r = obj(lanes[id]);
    const reconstructed = id.startsWith("provisional");
    rows.push(row(id, name, "Tennis match markets", reconstructed ? "Reconstructed selections" : "Model selection ledger", r, r.generated_at,
      reconstructed ? "First recorded price, 0.5u per fixture. This record does not verify Telegram delivery or actual bets placed." : "Recorded model selections and original stakes. This is not a verified account of bets placed."));
  }
  const context = obj(s.tennis_context_forward);
  rows.push(row("astra", "Astra Volume", "Tennis research", "Forward paper", context.candidate, context.generated_at,
    "Current corrected inputs only. Historical replay and earlier inputs are excluded."));
  for (const [key, name] of [["tennis_astrissimo", "Astrissimo"], ["tennis_hardcourt_scout", "Hardcourt Scout"]]) {
    const r = obj(s[key]);
    rows.push(row(key, name, "Tennis research", "Forward paper", r, r.generated_at, "Recorded paper selections only. Historical backtests are excluded; no real stake."));
  }
  const props = obj(s.tennis_props_shadow_decision);
  rows.push(row("props", "Aces & double faults", "Tennis props", "Canonical paper ledger", props, props.generated_at,
    "Full retained signal record, including earlier input versions. Multiple lines from one match can be correlated."));
  for (const r of Array.isArray(props.by_market) ? props.by_market : []) {
    const m = obj(r);
    rows.push(row(`props-${m.market}`, m.market === "aces" ? "Aces" : "Double faults", "Tennis props", "Market breakdown", m, props.generated_at,
      "Subset of the combined props record above. Missing fields are not supplied by the compact report."));
  }
  const v4 = obj(s.tennis_props_v4);
  rows.push(row("aces-v4", "Aces v4", "Tennis props", "Calibration research", {settled: v4.signals_settled, status: v4.status}, v4.generated_at,
    `Collecting calibration observations (${num(v4.rows_settled) ?? "unknown"} settled rows). Observations are not qualifying bet selections.`));
  const counts = obj(f.football_counts_vnext);
  for (const [key, name] of [["team_shots_v4", "Team Shots v4"], ["corners_v3", "Corners v3"]]) {
    const c = obj(counts[key]);
    rows.push(row(key, name, "Football research", "Forward paper", c.prospective, counts.generated_at,
      "Prospective record only; warm up results excluded. Report date is not the latest signal date.", true));
  }
  rows.push(row("gk", "Goalkeeper Saves v1", "Football research", "Forward paper", f.goalkeeper_saves_v1, f.generated_at,
    "Saved weekly report. Detailed stakes, wins and losses are not included in this compact source.", true));
  return rows;
}

export type Selection = { model: string; player: string; opponent: string; status: string; kickoff: string | null; odds: number | null; profit: number | null };
export function savedSelections(sections: unknown): Selection[] {
  const s = obj(sections), result: Selection[] = [];
  for (const [key, name] of [["tennis_hardcourt_scout", "Hardcourt Scout"], ["tennis_astrissimo", "Astrissimo"]]) {
    const entries = obj(s[key]).selections;
    if (!Array.isArray(entries)) continue;
    for (const entry of entries) {
      const r = obj(entry);
      result.push({model: name, player: str(r.player) ?? "Unknown player", opponent: str(r.opponent) ?? "Unknown opponent",
        status: str(r.status) ?? "Unknown", kickoff: str(r.kickoff), odds: num(r.odds), profit: num(r.pnl_units)});
    }
  }
  return result.sort((a, b) => (b.kickoff ?? "").localeCompare(a.kickoff ?? "")).slice(0, 30);
}
