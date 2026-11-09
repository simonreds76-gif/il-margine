import { signalCsv } from "./admin-signal-format";
import { selectionCard, text, visibleRows, type SignalRow } from "./admin-monitor-display";
import { obj, row, type ModelRow } from "./admin-model-summary";
import { profitHistory, reconciledHistory, type ProfitHistory } from "./model-profit-history";

export const propsSegments = [
  ["aces", "Aces", "market", "aces"], ["double_faults", "Double faults", "market", "double_faults"],
  ["men", "Men", "tour", "atp"], ["women", "Women", "tour", "wta"],
] as const;
const settledOutcomes = new Set(["Won", "Lost", "Push", "Half win", "Half loss", "Settled"]);
const status = (r: SignalRow) => text(r.settlement_status || r.status).trim().toLowerCase();
const unresolved = (r: SignalRow) => ["pending", "open", "unsettled"].includes(status(r));
const eligible = (r: SignalRow) => !["Excluded", "Quote review", "Void", "Blocked"].includes(selectionCard(r, "props-record").outcome) && !["void", "cancelled", "canceled", "quarantined", "excluded", "duplicate", "blocked"].includes(status(r));

/** Same canonical ledger and flat 1u paper accounting as tennis_props_shadow_decision.
 * Require reconciliation before showing a partition; no selection, grading or model changes.
 */
export function propsBreakdowns(content: unknown, expected: ModelRow): { rows: ModelRow[]; histories: Record<string, ProfitHistory> } {
  let entries: SignalRow[] = [];
  try { if (typeof content === "string") entries = visibleRows(signalCsv(content), "props-record", "props").filter(eligible); } catch { /* fail closed below */ }
  const total = reconciledHistory(content, "props-record", expected);
  const knownTours = entries.every(r => ["atp", "wta"].includes(text(r.tour).trim().toLowerCase()));
  const histories: Record<string, ProfitHistory> = {};
  const rows = propsSegments.map(([id, name, field, value]) => {
    const subset = entries.filter(r => text(r[field]).trim().toLowerCase() === value);
    const history = profitHistory(subset, "props-record", "props");
    const unavailable = total.message || (field === "tour" && !knownTours ? "Tour breakdown unavailable: unclassified records need review." : undefined);
    const settled = subset.filter(r => !unresolved(r) && settledOutcomes.has(selectionCard(r, "props-record").outcome));
    const summary = unavailable ? {} : {settled: history.settled, pending: subset.filter(unresolved).length,
      wins: settled.filter(r => selectionCard(r, "props-record").outcome === "Won").length,
      losses: settled.filter(r => selectionCard(r, "props-record").outcome === "Lost").length,
      stake_units: history.settled, pnl_units: history.profit,
      roi_pct: history.settled ? history.profit / history.settled * 100 : null};
    const result = row(`props-${id}`, name, "Tennis props", field === "tour" ? "Aces + double faults" : "Men + women", summary, expected.date,
      "Subset of the canonical props record. Flat 1u paper stakes; voids, excluded records and unresolved results do not contribute to profit. Multiple selections can share a match.");
    histories[result.id] = unavailable ? {days: [], settled: 0, profit: 0, omitted: 0, message: unavailable} : history;
    return result;
  });
  return {rows, histories};
}

export function footballForwardRows(content: string | null): SignalRow[] | null {
  if (content === null) return null;
  try { return signalCsv(content).filter(r => !text(r.blocked_reason).trim() && !["true", "1", "yes"].includes(text(r.confidence_guard_applied).toLowerCase()) && text(r.signal_status).toLowerCase() !== "warmup_tracking"); }
  catch { return null; }
}

/** Source summary and its dated curve are reconciled together, independently of the weekly digest. */
export function footballModel(id: string, name: string, value: unknown, date: unknown, ledger: string | null, note: string) {
  const r = row(id, name, "Football research", "Forward paper", value, date, note, true);
  const reconciliation=obj(obj(value).reconciliation);
  const excluded=new Set(Array.isArray(reconciliation.excluded_pick_ids) ? reconciliation.excluded_pick_ids.filter((v): v is string => typeof v === "string") : []);
  const entries = footballForwardRows(ledger)?.filter(v=>!excluded.has(text(v.pick_id))) ?? null;
  if (excluded.size) r.note += ` ${excluded.size} verified duplicate selection excluded from accounting; both original rows remain in the audit record. Lyon–Angers: the original Pinnacle selection remains pending settlement review; the later Bet365 entry is the duplicate.`;
  const history = reconciledHistory(entries, id, r);
  if (entries && !history.message) {
    const settled = entries.filter(v => !unresolved(v) && settledOutcomes.has(selectionCard(v, id).outcome));
    r.wins = settled.filter(v => selectionCard(v, id).outcome === "Won").length;
    r.losses = settled.filter(v => selectionCard(v, id).outcome === "Lost").length;
    const stakes = settled.map(v => selectionCard(v, id).stake);
    if (stakes.every(v => v !== null)) r.stake = stakes.reduce<number>((sum, v) => sum + (v ?? 0), 0);
  }
  r.status = typeof obj(value).status === "string" ? String(obj(value).status) : r.status;
  return {row: r, history};
}

/** Accept registered input revisions by their data contract, not one old revision name. */
export function validShotsComparison(value: unknown): boolean {
  const d=obj(value), models=obj(d.models);
  return typeof d.version === "string" && d.version.startsWith("paired-market-offset-") &&
    typeof d.generated_at === "string" && Number.isFinite(Date.parse(d.generated_at)) &&
    typeof d.contracts === "number" && typeof d.paired_fixtures === "number" &&
    ["shots_market_offset_v1", "opponent", "v4", "ema20_v3"].every(id => {
      const p=obj(obj(models[id]).hypothetical_selections);
      return typeof p.settled === "number" && typeof p.pnl_units === "number" && Number.isFinite(p.pnl_units);
    });
}
