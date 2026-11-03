import { signalCsv } from "./admin-signal-format";
import { pick, selectionCard, text, visibleRows, type SignalRow } from "./admin-monitor-display";

export type ProfitDay = { date: string; profit: number; cumulative: number; settled: number };
export type ProfitHistory = { days: ProfitDay[]; settled: number; profit: number; omitted: number; message?: string };
const round = (value: number) => Math.round(value * 1e6) / 1e6;
const day = (value: unknown) => {
  const date = text(value).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(date)) && new Date(date).toISOString().slice(0, 10) === date ? date : null;
};

/** Display only: retain the ledger's P/L, exclude unresolved/excluded rows, never regrade bets. */
export function profitHistory(rows: SignalRow[], view: string, model = "reference"): ProfitHistory {
  const grouped = new Map<string, { profit: number; settled: number }>();
  let omitted = 0;
  const ids = new Set<string>();
  for (const row of visibleRows(rows, view, model)) {
    const card = selectionCard(row, view);
    if (!["Won", "Lost", "Push", "Half win", "Half loss", "Settled"].includes(card.outcome)) continue;
    const id = text(pick(row, ["signal_id", "pick_id"]));
    // Ambiguous duplicate IDs must not create a misleading curve, even if totals happen to match.
    if (id && ids.has(id)) { omitted++; continue; }
    if (id) ids.add(id);
    const date = day(pick(row, ["match_date", "match_start_utc", "scheduled_start_utc", "kickoff_at", "kickoff_utc", "kickoff", "date"]));
    if (!date || card.profit === null) { omitted++; continue; }
    const old = grouped.get(date) ?? { profit: 0, settled: 0 };
    grouped.set(date, { profit: old.profit + card.profit, settled: old.settled + 1 });
  }
  let cumulative = 0;
  const days = [...grouped].sort(([a], [b]) => a.localeCompare(b)).map(([date, value]) => {
    cumulative += value.profit;
    return { date, profit: round(value.profit), cumulative: round(cumulative), settled: value.settled };
  });
  return { days, profit: round(cumulative), settled: days.reduce((sum, p) => sum + p.settled, 0), omitted };
}

/** A headline chart is shown only when the complete plotted cohort reconciles to that headline. */
export function reconciledHistory(content: unknown, view: string, expected: { settled: number | null; profit: number | null }, market?: string): ProfitHistory {
  const unavailable = (message: string): ProfitHistory => ({ days: [], settled: 0, profit: 0, omitted: 0, message });
  if (typeof content !== "string" && !Array.isArray(content)) return unavailable("Dated results are not available in this snapshot yet.");
  try {
    let rows: SignalRow[] = typeof content === "string" ? signalCsv(content) : content.filter((r): r is SignalRow => !!r && typeof r === "object" && !Array.isArray(r));
    if (market) rows = rows.filter(r => text(r.market).trim().toLowerCase() === market);
    const result = profitHistory(rows, view, "props");
    if (result.omitted || expected.settled === null || expected.profit === null || result.settled !== expected.settled || Math.abs(result.profit - expected.profit) > 0.011) {
      return unavailable("Chart withheld: dated results do not yet reconcile with this report. Existing figures are unchanged.");
    }
    return result;
  } catch { return unavailable("The dated result file could not be read."); }
}

export function profitWindow(history: ProfitHistory, windowDays: number | null): { days: ProfitDay[]; opening: number; change: number; drawdown: number; from: string | null } {
  const last = history.days.at(-1);
  if (!last) return { days: [], opening: 0, change: 0, drawdown: 0, from: null };
  const from = windowDays === null ? history.days[0].date : new Date(Date.parse(last.date) - (windowDays - 1) * 86400000).toISOString().slice(0, 10);
  const days = history.days.filter(d => d.date >= from);
  const opening = round(days[0].cumulative - days[0].profit);
  let peak = opening, drawdown = 0;
  for (const d of days) { peak = Math.max(peak, d.cumulative); drawdown = Math.max(drawdown, peak - d.cumulative); }
  return { days, opening, change: round(last.cumulative - opening), drawdown: round(drawdown), from };
}
