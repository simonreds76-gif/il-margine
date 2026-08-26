import type { MonitorCsvRow } from "@/lib/monitor-csv";

type GoalkeeperReport = {
  status?: string;
  generated_at?: string;
  selection_rule?: string;
  count_model?: string;
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
  };
  promotion?: { status?: string; settled_required?: number };
};

type CaptureStatus = {
  status?: string;
  generated_at?: string;
  events?: number;
  rows?: number;
  message?: string;
};

type SettlementStatus = {
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

function numberValue(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function units(value: number | null | undefined): string {
  const amount = value ?? 0;
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(2)}u`;
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/55 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-lg tabular-nums text-slate-100">{value}</div>
      <div className="mt-1 text-[11px] text-slate-500">{detail}</div>
    </div>
  );
}

export default function GoalkeeperSavesPanel({
  report,
  capture,
  settlement,
  signals,
  candidates,
  provisional,
}: {
  report: GoalkeeperReport | null;
  capture: CaptureStatus | null;
  settlement: SettlementStatus | null;
  signals: MonitorCsvRow[];
  candidates: MonitorCsvRow[];
  provisional: MonitorCsvRow[];
}) {
  const settled = signals.filter((row) => ["won", "lost", "push", "void"].includes((row.result ?? "").toLowerCase()));
  const pending = signals.filter((row) => !row.result || row.result.toLowerCase() === "pending");
  const evidence = report?.evidence;
  const ledger = [...signals].sort((a, b) => String(b.kickoff_at || b.match_date || "").localeCompare(String(a.kickoff_at || a.match_date || "")));
  const board = [...candidates, ...provisional]
    .sort((a, b) => (numberValue(b.edge) ?? -999) - (numberValue(a.edge) ?? -999));

  return (
    <section id="goalkeeper-saves" className="overflow-hidden rounded-2xl border border-violet-400/25 bg-[linear-gradient(135deg,rgba(76,29,149,.16),rgba(2,6,23,.92)_45%,rgba(15,23,42,.86))]">
      <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-white">Goalkeeper Saves v1</h2>
              <span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-violet-200">Tracked research</span>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-400">
              Every positive-EV line stays visible as a correlated value ladder. Exactly one robust line per fixture enters settlement, P/L, ROI and closing-line evidence, preventing duplicate counting.
            </p>
          </div>
          <div className="text-right text-[11px] text-slate-500">
            <div>Count model <span className="font-semibold text-emerald-300">{report?.count_model ?? "-"}</span></div>
            <div>Promotion <span className="font-semibold text-amber-300">{report?.promotion?.status ?? "BLOCKED"}</span></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4 xl:grid-cols-8 sm:p-5">
        <Metric label="Priced lines" value={String(report?.current?.priced_lines ?? 0)} detail={`${report?.current?.eligible_lines ?? 0} primary eligible`} />
        <Metric label="Tracked open" value={String(pending.length)} detail={`${evidence?.pending ?? pending.length} pending`} />
        <Metric label="Settled" value={String(settled.length)} detail={`${evidence?.settled ?? settled.length} in report`} />
        <Metric label="P/L" value={units(evidence?.pnl_units)} detail="current v1 ledger" />
        <Metric label="ROI" value={pct(evidence?.roi)} detail="P/L / units staked" />
        <Metric label="Mean CLV" value={pct(evidence?.clv)} detail={`matched n=${evidence?.clv_matched ?? 0}`} />
        <Metric label="Captured rows" value={String(capture?.rows ?? 0)} detail={`${capture?.events ?? 0} events`} />
        <Metric label="Board rows" value={String(board.length)} detail={`${report?.current?.value_ladder_lines ?? 0} extra value lines`} />
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="grid gap-2 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-4 py-3 text-xs text-slate-400">
            <div className="font-semibold text-slate-200">Capture: {(capture?.status ?? report?.status ?? "NOT RUN").replaceAll("_", " ")}</div>
            <div className="mt-1">{capture?.message ?? report?.selection_rule ?? "Awaiting a current goalkeeper-save O/U price feed."}</div>
            <div className="mt-1 text-[11px] text-slate-600">Generated {capture?.generated_at ?? report?.generated_at ?? "-"}</div>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-4 py-3 text-xs text-slate-400">
            <div className="font-semibold text-slate-200">Settlement: {(settlement?.status ?? "NOT REPORTED").replaceAll("_", " ")}</div>
            <div className="mt-1">{settlement ? `${settlement.settled ?? 0} settled · ${settlement.pending_due ?? 0} due · ${settlement.deferred_not_due ?? 0} not due · ${settlement.requests_used ?? 0}/${settlement.max_requests ?? 0} API calls` : "The next daily settlement run will publish reason-coded diagnostics."}</div>
            {settlement?.reason_counts && Object.keys(settlement.reason_counts).length > 0 ? <div className="mt-2 flex flex-wrap gap-1.5">{Object.entries(settlement.reason_counts).map(([reason, count]) => <span key={reason} className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-300">{reason.replaceAll("_", " ")} {count}</span>)}</div> : null}
            <div className="mt-1 text-[11px] text-slate-600">Generated {settlement?.generated_at ?? "-"}</div>
          </div>
        </div>
      </div>

      <details className="border-t border-slate-800 px-4 py-3 sm:px-5" open={ledger.length > 0}>
        <summary className="cursor-pointer text-xs font-semibold text-slate-300">Tracked signal ledger ({ledger.length})</summary>
        {ledger.length === 0 ? (
          <div className="mt-3 rounded-xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-500">No registered goalkeeper-save signal yet.</div>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full min-w-[980px] text-left text-xs">
              <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.12em] text-slate-500"><tr><th className="px-3 py-2">Date</th><th className="px-3 py-2">Match</th><th className="px-3 py-2">Goalkeeper</th><th className="px-3 py-2">Pick</th><th className="px-3 py-2 text-right">Price</th><th className="px-3 py-2 text-right">Fair</th><th className="px-3 py-2 text-right">Edge</th><th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">P/L</th></tr></thead>
              <tbody>{ledger.map((row, index) => {
                const result = (row.result || row.status || "pending").toLowerCase();
                const resultClass = result === "won" ? "text-emerald-300" : result === "lost" ? "text-rose-300" : "text-amber-200";
                return <tr key={`${row.signal_id || row.event_id}-${index}`} className="border-t border-slate-800"><td className="px-3 py-2 text-slate-400">{row.match_date || "-"}</td><td className="px-3 py-2 text-slate-200">{row.home_team} vs {row.away_team}</td><td className="px-3 py-2 text-violet-100">{row.goalkeeper || "-"}</td><td className="px-3 py-2 capitalize">{row.side} {row.line}</td><td className="px-3 py-2 text-right font-mono">{row.odds_decimal || "-"}</td><td className="px-3 py-2 text-right font-mono">{row.fair_odds || "-"}</td><td className="px-3 py-2 text-right font-mono text-emerald-300">{pct(numberValue(row.edge))}</td><td className={`px-3 py-2 font-semibold uppercase ${resultClass}`}><div>{result}</div>{row.selection_policy ? <div className="mt-1 text-[9px] font-normal normal-case tracking-normal text-slate-500">{row.selection_policy.replaceAll("_", " ")}</div> : null}</td><td className="px-3 py-2 text-right font-mono">{row.pnl_units || "-"}</td></tr>;
              })}</tbody>
            </table>
          </div>
        )}
      </details>

      <details className="border-t border-slate-800 px-4 py-3 sm:px-5" open={board.length > 0}>
        <summary className="cursor-pointer text-xs font-semibold text-slate-300">Current candidate board and value ladders ({board.length})</summary>
        {board.length === 0 ? (
          <div className="mt-3 rounded-xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-500">No current priced candidates. Tracking begins automatically when the capture contains named goalkeeper-save O/U lines.</div>
        ) : (
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full min-w-[900px] text-left text-xs">
              <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.12em] text-slate-500"><tr><th className="px-3 py-2">Kickoff</th><th className="px-3 py-2">Match</th><th className="px-3 py-2">Goalkeeper</th><th className="px-3 py-2">Selection</th><th className="px-3 py-2 text-right">Price</th><th className="px-3 py-2 text-right">Fair</th><th className="px-3 py-2 text-right">Edge</th><th className="px-3 py-2">Status</th></tr></thead>
              <tbody>{board.map((row, index) => <tr key={`${row.event_id}-${row.goalkeeper}-${row.line}-${row.side}-${index}`} className="border-t border-slate-800"><td className="px-3 py-2 text-slate-400">{(row.kickoff_at || row.match_date || "-").replace("T", " ").slice(0, 16)}</td><td className="px-3 py-2 text-slate-200">{row.home_team} vs {row.away_team}</td><td className="px-3 py-2 text-violet-100">{row.goalkeeper || "-"}</td><td className="px-3 py-2">{row.side} {row.line}</td><td className="px-3 py-2 text-right font-mono">{row.odds_decimal || "-"}</td><td className="px-3 py-2 text-right font-mono">{row.fair_odds || "-"}</td><td className="px-3 py-2 text-right font-mono text-emerald-300">{pct(numberValue(row.edge))}</td><td className="px-3 py-2 text-slate-400"><div>{row.candidate_status || (row.research_only ? "provisional" : "candidate")}</div>{row.selection_policy ? <div className="mt-1 text-[9px] text-slate-600">{row.selection_policy.replaceAll("_", " ")}</div> : null}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </details>
    </section>
  );
}
