import type { MonitorCsvRow } from "@/lib/monitor-csv";
import {
  cleanText,
  cn,
  formatDateTimeLabel,
  MatchLabel,
  StatusPill,
  TeamLabel,
} from "@/app/model-monitor/shared";

export type GoalkeeperReport = {
  status?: string;
  generated_at?: string;
  selection_rule?: string;
  count_model?: string;
  live_routing?: boolean;
  current?: {
    priced_lines?: number;
    eligible_lines?: number;
    value_ladder_lines?: number;
    provisional_lines?: number;
    signals_added?: number;
    blocker_counts?: Record<string, number>;
  };
  evidence?: {
    signals?: number;
    settled?: number;
    pending?: number;
    pnl_units?: number;
    roi?: number | null;
    clv?: number | null;
    clv_matched?: number;
    true_close_coverage?: number | null;
  };
  promotion?: {
    status?: string;
    settled_required?: number;
    true_close_coverage_required?: number;
    mean_true_close_clv_required?: number;
  };
};

export type GoalkeeperCaptureStatus = {
  status?: string;
  generated_at?: string;
  events?: number;
  rows?: number;
  events_selected?: number;
  events_with_lines?: number;
  rows_added?: number;
  message?: string;
};

export type GoalkeeperSettlementStatus = {
  status?: string;
  generated_at?: string;
  pending_total?: number;
  pending_due?: number;
  deferred_not_due?: number;
  settled?: number;
  requests_used?: number;
  max_requests?: number;
  reason_counts?: Record<string, number>;
  api_errors?: string[];
};

function numeric(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function units(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function resultFor(row: MonitorCsvRow): string {
  return cleanText(row.result || row.status || "pending").toLowerCase();
}

function isSettled(row: MonitorCsvRow): boolean {
  return ["won", "lost", "push", "void"].includes(resultFor(row));
}

function resultTone(result: string): string {
  if (result === "won") return "text-emerald-300";
  if (result === "lost") return "text-rose-300";
  if (result === "pending") return "text-amber-200";
  return "text-slate-300";
}

function metricTone(value: number | null): string {
  if (value === null || value === 0) return "text-slate-100";
  return value > 0 ? "text-emerald-300" : "text-rose-300";
}

function plain(value?: string | null): string {
  const labels: Record<string, string> = {
    goalkeeper_team_unresolved: "Goalkeeper team unresolved",
    missing_lineup: "Lineup not published",
    missing_priced_edge: "No model-priced edge",
    player_not_starting_goalkeeper: "Player not starting goalkeeper",
  };
  return cleanText(value)
    .split("|")
    .map((part) => labels[part] ?? part.replaceAll("_", " "))
    .filter(Boolean)
    .join(" / ");
}

function Metric({ label, value, detail, tone }: { label: string; value: string; detail: string; tone?: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.13em] text-slate-500">{label}</div>
      <div className={cn("mt-1 font-mono text-lg font-semibold tabular-nums text-slate-100", tone)}>{value}</div>
      <div className="mt-1 truncate text-[11px] text-slate-500" title={detail}>{detail}</div>
    </div>
  );
}

function GkLedgerCards({ rows }: { rows: MonitorCsvRow[] }) {
  return (
    <ul className="grid gap-2 md:hidden">
      {rows.map((row, index) => {
        const result = resultFor(row);
        const edge = numeric(row.edge);
        return (
          <li key={row.signal_id || `${row.event_id}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/45 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] text-slate-500">{formatDateTimeLabel(row.kickoff_at || row.match_date)}</div>
                <MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="mt-1 w-full" textClassName="text-sm font-semibold text-slate-100" />
              </div>
              <span className={cn("shrink-0 text-xs font-bold uppercase", resultTone(result))}>{result}</span>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
              <TeamLabel league={row.league} team={row.team} detail={`${cleanText(row.goalkeeper)} / ${cleanText(row.side)} ${cleanText(row.line)}`} teamClassName="text-sm text-slate-200" detailClassName="text-[11px] text-slate-500" />
              <div className="grid shrink-0 grid-cols-3 gap-3 text-right text-xs tabular-nums">
                <div><span className="block text-[11px] text-slate-600">Market</span>{numeric(row.odds_decimal)?.toFixed(2) ?? "-"}</div>
                <div><span className="block text-[11px] text-slate-600">Fair</span>{numeric(row.fair_odds)?.toFixed(2) ?? "-"}</div>
                <div className={metricTone(edge)}><span className="block text-[11px] text-slate-600">Edge</span>{pct(edge)}</div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-900/60 px-3 py-2 text-xs">
              <div><span className="block text-[11px] text-slate-500">Stake</span>{(numeric(row.stake_units) ?? 0.5).toFixed(1)}u</div>
              <div><span className="block text-[11px] text-slate-500">Actual saves</span>{cleanText(row.actual_saves) || "-"}</div>
              <div className={cn("text-right font-mono", resultTone(result))}><span className="block text-[11px] text-slate-500">P/L</span>{isSettled(row) ? units(numeric(row.pnl_units)) : "-"}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export default function GoalkeeperSavesPanel({
  report,
  capture,
  settlement,
  signals,
  candidates,
  provisional,
  source,
}: {
  report: GoalkeeperReport | null;
  capture: GoalkeeperCaptureStatus | null;
  settlement: GoalkeeperSettlementStatus | null;
  signals: MonitorCsvRow[];
  candidates: MonitorCsvRow[];
  provisional: MonitorCsvRow[];
  source?: "hosted" | "local" | "missing";
}) {
  const ledger = [...signals].sort((a, b) => String(b.kickoff_at || b.match_date).localeCompare(String(a.kickoff_at || a.match_date)));
  const settled = ledger.filter(isSettled);
  const pending = ledger.filter((row) => !isSettled(row));
  const won = settled.filter((row) => resultFor(row) === "won").length;
  const lost = settled.filter((row) => resultFor(row) === "lost").length;
  const pushed = settled.length - won - lost;
  const staked = settled.reduce((sum, row) => sum + (numeric(row.stake_units) ?? 0.5), 0);
  const pnl = settled.reduce((sum, row) => sum + (numeric(row.pnl_units) ?? 0), 0);
  const roi = staked > 0 ? pnl / staked : null;
  const clvValues = settled.map((row) => numeric(row.clv)).filter((value): value is number => value !== null);
  const meanClv = clvValues.length ? clvValues.reduce((sum, value) => sum + value, 0) / clvValues.length : null;
  const topTwoPnl = settled.map((row) => numeric(row.pnl_units) ?? 0).sort((a, b) => b - a).slice(0, 2).reduce((sum, value) => sum + value, 0);
  const board = [...candidates, ...provisional].sort((a, b) => String(a.kickoff_at || a.match_date).localeCompare(String(b.kickoff_at || b.match_date)) || (numeric(b.edge) ?? -999) - (numeric(a.edge) ?? -999));
  const promotion = cleanText(report?.promotion?.status || "BLOCKED").replaceAll("_", " ");
  const captureRows = capture?.rows ?? capture?.rows_added ?? 0;
  const captureEvents = capture?.events ?? capture?.events_with_lines ?? 0;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.98),rgba(8,12,20,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.22)]">
      <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold tracking-tight text-white">Goalkeeper Saves v1 evidence ledger</h2>
              <StatusPill label="Tracked research" tone="border-violet-400/30 bg-violet-400/10 text-violet-200" />
              <StatusPill label={`Promotion ${promotion}`} tone="border-rose-400/30 bg-rose-400/10 text-rose-200" />
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Registered and settled for evidence. Positive-EV ladders remain visible, but exactly one qualifying line per fixture enters P/L.</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs leading-5 text-slate-400">
            <div>Source <strong className="uppercase text-slate-200">{source ?? "unknown"}</strong></div>
            <div>Generated <strong className="text-slate-200">{formatDateTimeLabel(report?.generated_at)}</strong></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4 xl:grid-cols-8 sm:p-5">
        <Metric label="Tracked" value={String(ledger.length)} detail={`${report?.evidence?.signals ?? ledger.length} in report`} />
        <Metric label="Settled" value={String(settled.length)} detail={`${won}-${lost}-${pushed} W-L-P`} />
        <Metric label="Pending" value={String(pending.length)} detail="awaiting settlement" tone={pending.length ? "text-amber-200" : undefined} />
        <Metric label="Total staked" value={`${staked.toFixed(1)}u`} detail="settled denominator" />
        <Metric label="P/L" value={units(pnl)} detail={`top two wins ${units(topTwoPnl)}`} tone={metricTone(pnl)} />
        <Metric label="ROI" value={pct(roi)} detail={`${units(pnl)} / ${staked.toFixed(1)}u`} tone={metricTone(roi)} />
        <Metric label="Mean CLV" value={meanClv === null ? "-" : pct(meanClv)} detail={`CLV matched ${clvValues.length} of ${settled.length}`} tone={metricTone(meanClv)} />
        <Metric label="Side skew" value={`${ledger.filter((row) => cleanText(row.side).toLowerCase() === "over").length}/${ledger.length}`} detail="over selections" />
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-4 text-sm leading-6 text-slate-400">
            <div className="flex items-center justify-between gap-3"><strong className="text-slate-200">Price capture</strong><StatusPill label={plain(capture?.status || report?.status || "not run")} tone={captureRows ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-amber-400/25 bg-amber-400/10 text-amber-200"} /></div>
            <p className="mt-2">{captureRows} rows across {captureEvents} events in the latest capture. {cleanText(capture?.message)}</p>
            <p className="mt-1 text-xs text-slate-500">Generated {formatDateTimeLabel(capture?.generated_at)}</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-4 text-sm leading-6 text-slate-400">
            <div className="flex items-center justify-between gap-3"><strong className="text-slate-200">Promotion gate</strong><StatusPill label={promotion} tone="border-rose-400/25 bg-rose-400/10 text-rose-200" /></div>
            <p className="mt-2">Needs {report?.promotion?.settled_required ?? 150} settled selections and {((report?.promotion?.true_close_coverage_required ?? 0.7) * 100).toFixed(0)}% true-close coverage. Current verified coverage: {report?.evidence?.true_close_coverage === null || report?.evidence?.true_close_coverage === undefined ? "not reported" : pct(report.evidence.true_close_coverage)}. Live routing is {report?.live_routing ? "on" : "off"}.</p>
            <p className="mt-1 text-xs text-slate-500">Settlement: {plain(settlement?.status || "not reported")} / {settlement?.pending_due ?? 0} due</p>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div><h3 className="text-base font-semibold text-white">Registered 2026/27 evidence</h3><p className="mt-1 text-xs text-slate-500">One counted selection per fixture. All settled rows remain visible.</p></div>
          <span className="font-mono text-xs text-slate-400">{ledger.length} rows</span>
        </div>
        {ledger.length === 0 ? <div className="rounded-xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">No registered goalkeeper-save selection yet.</div> : <>
          <GkLedgerCards rows={ledger} />
          <div className="hidden overflow-x-auto rounded-xl border border-slate-800 md:block">
            <table className="w-full min-w-[1120px] text-left text-xs">
              <thead className="bg-slate-950/95 text-[11px] uppercase tracking-[0.11em] text-slate-500"><tr><th className="px-3 py-3">Date</th><th className="px-3 py-3">Match</th><th className="px-3 py-3">Goalkeeper / selection</th><th className="px-3 py-3 text-right">Stake</th><th className="px-3 py-3 text-right">Market odds</th><th className="px-3 py-3 text-right">Fair odds</th><th className="px-3 py-3 text-right">Edge</th><th className="px-3 py-3 text-right">Actual saves</th><th className="px-3 py-3">Status</th><th className="px-3 py-3 text-right">P/L</th><th className="px-3 py-3 text-right">CLV</th></tr></thead>
              <tbody>{ledger.map((row, index) => { const result = resultFor(row); const clv = numeric(row.clv); return <tr key={row.signal_id || `${row.event_id}-${index}`} className="border-t border-slate-800/80"><td className="whitespace-nowrap px-3 py-3 text-slate-400">{formatDateTimeLabel(row.kickoff_at || row.match_date)}</td><td className="max-w-[260px] px-3 py-3"><MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="w-full" textClassName="font-medium text-slate-200" /></td><td className="px-3 py-3"><TeamLabel league={row.league} team={row.team} detail={`${cleanText(row.goalkeeper)} / ${cleanText(row.side)} ${cleanText(row.line)}`} teamClassName="text-slate-200" detailClassName="text-[11px] text-slate-500" /></td><td className="px-3 py-3 text-right font-mono">{(numeric(row.stake_units) ?? 0.5).toFixed(1)}u</td><td className="px-3 py-3 text-right font-mono">{numeric(row.odds_decimal)?.toFixed(2) ?? "-"}</td><td className="px-3 py-3 text-right font-mono">{numeric(row.fair_odds)?.toFixed(2) ?? "-"}</td><td className={cn("px-3 py-3 text-right font-mono", metricTone(numeric(row.edge)))}>{pct(numeric(row.edge))}</td><td className="px-3 py-3 text-right font-mono">{cleanText(row.actual_saves) || "-"}</td><td className={cn("px-3 py-3 font-semibold uppercase", resultTone(result))}>{result}</td><td className={cn("px-3 py-3 text-right font-mono", resultTone(result))}>{isSettled(row) ? units(numeric(row.pnl_units)) : "-"}</td><td className={cn("px-3 py-3 text-right font-mono", metricTone(clv))}>{clv === null ? "-" : pct(clv)}</td></tr>; })}</tbody>
            </table>
          </div>
        </>}
      </div>

      <details className="border-t border-slate-800 px-4 py-4 sm:px-5" open={board.length > 0}>
        <summary className="cursor-pointer text-sm font-semibold text-slate-300">Current candidates and value ladders ({board.length})</summary>
        {board.length === 0 ? <div className="mt-3 rounded-xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">No current priced candidates. The latest capture retained no named goalkeeper-save O/U line.</div> : <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{board.map((row, index) => <div key={`${row.event_id}-${row.goalkeeper}-${row.line}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/45 p-3 text-xs"><div className="text-[11px] text-slate-500">{formatDateTimeLabel(row.kickoff_at || row.match_date)}</div><MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="mt-1 w-full" textClassName="font-medium text-slate-200" /><div className="mt-3 flex items-center justify-between gap-3"><span className="text-slate-200">{cleanText(row.goalkeeper)} / {cleanText(row.side)} {cleanText(row.line)}</span><span className="font-mono text-white">{numeric(row.odds_decimal)?.toFixed(2) ?? "-"}</span></div><div className="mt-2 leading-5 text-amber-200">{plain(row.blockers) || plain(row.candidate_status) || "Awaiting model price"}</div></div>)}</div>}
      </details>
    </section>
  );
}
