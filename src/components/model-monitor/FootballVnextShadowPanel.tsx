import type { MonitorCsvRow } from "@/lib/monitor-csv";
import {
  cleanText,
  cn,
  formatDateTimeLabel,
  MatchLabel,
  StatusPill,
  TeamLabel,
} from "@/app/model-monitor/shared";

type Evidence = {
  signals?: number;
  settled?: number;
  pending?: number;
  pnl_units?: number;
  roi?: number | null;
  true_close_n?: number;
  true_close_coverage?: number | null;
  mean_true_close_clv?: number | null;
  side_counts?: Record<string, number>;
  dominant_side_share?: number;
};

type LatestScan = {
  state?: string;
  explanation?: string;
  scored_rows?: number;
  scored_fixtures?: number;
  eligible_rows?: number;
  eligible_fixtures?: number;
  blocked_rows?: number;
  blocker_rows?: Record<string, number>;
  edge_pass_but_warmup_blocked_fixtures?: number;
  matchday_min?: number | null;
  matchday_max?: number | null;
  next_unlock?: string | null;
};

export type FootballVnextGate = {
  count_gate?: string;
  prospective_status?: string;
  market_gate?: string;
  promotion_gate?: string;
  live_routing?: boolean;
  prospective?: Evidence;
  warmup_tracking?: Evidence;
  latest_scan?: LatestScan;
};

type SourceStatus = {
  source?: "hosted" | "local" | "missing";
  generatedAt?: string | null;
};

function numeric(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function pct(value: number | null | undefined, scale = 100): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  const amount = value * scale;
  return `${amount > 0 ? "+" : ""}${amount.toFixed(1)}%`;
}

function units(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function resultFor(row: MonitorCsvRow): string {
  return cleanText(row.result || "pending").toLowerCase();
}

function isSettled(row: MonitorCsvRow): boolean {
  return ["won", "lost", "push", "void"].includes(resultFor(row));
}

function rowStake(row: MonitorCsvRow): number {
  return numeric(row.stake_units || row.stake) ?? 1;
}

function resultTone(result: string): string {
  if (result === "won") return "text-emerald-300";
  if (result === "lost") return "text-rose-300";
  if (result === "push" || result === "void") return "text-slate-300";
  return "text-amber-200";
}

function plainReason(value?: string | null): string {
  const labels: Record<string, string> = {
    matchdays_1_to_3: "Matchday 1-3 safety lock",
    edge_below_3pct: "Edge below 3%",
    missing_two_way_market: "No paired two-way price",
    goalkeeper_team_unresolved: "Goalkeeper team unresolved",
    missing_lineup: "Lineup not published",
    player_not_starting_goalkeeper: "Player not starting goalkeeper",
    missing_priced_edge: "No model-priced edge",
  };
  return cleanText(value)
    .split(/[|,;]/)
    .map((part) => labels[part.trim()] ?? part.trim().replaceAll("_", " "))
    .filter(Boolean)
    .join(" / ");
}

function priceFor(row: MonitorCsvRow): number | null {
  return numeric(row.book_price_at_publication || row.pinnacle_price_at_publication || row.book_odds || row.odds_decimal);
}

function actualFor(model: "team_shots_v4" | "corners_v3", row: MonitorCsvRow): string {
  return cleanText(model === "team_shots_v4" ? row.actual_team_shots : row.actual_total_corners) || "-";
}

function metricTone(value: number | null): string {
  if (value === null || value === 0) return "text-slate-100";
  return value > 0 ? "text-emerald-300" : "text-rose-300";
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

function LedgerCards({ model, rows }: { model: "team_shots_v4" | "corners_v3"; rows: MonitorCsvRow[] }) {
  return (
    <ul className="grid gap-2 md:hidden">
      {rows.map((row, index) => {
        const result = resultFor(row);
        const edge = numeric(row.edge);
        return (
          <li key={row.pick_id || `${row.match}-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/45 p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] text-slate-500">{formatDateTimeLabel(row.kickoff_utc || row.match_date)}</div>
                <MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="mt-1 w-full" textClassName="text-sm font-semibold text-slate-100" />
              </div>
              <span className={cn("shrink-0 text-xs font-bold uppercase", resultTone(result))}>{result}</span>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-slate-200">{cleanText(row.selection) || `${cleanText(row.side)} ${cleanText(row.line)}`}</div>
                <div className="mt-0.5 text-[11px] text-slate-500">{cleanText(row.signal_status).replaceAll("_", " ") || "tracked research"}</div>
              </div>
              <div className="grid shrink-0 grid-cols-3 gap-3 text-right text-xs tabular-nums">
                <div><span className="block text-[11px] text-slate-600">Market</span>{priceFor(row)?.toFixed(2) ?? "-"}</div>
                <div><span className="block text-[11px] text-slate-600">Fair</span>{numeric(row.model_fair_odds)?.toFixed(2) ?? "-"}</div>
                <div className={metricTone(edge)}><span className="block text-[11px] text-slate-600">Edge</span>{pct(edge)}</div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-900/60 px-3 py-2 text-xs">
              <div><span className="block text-[11px] text-slate-500">Stake</span>{rowStake(row).toFixed(1)}u</div>
              <div><span className="block text-[11px] text-slate-500">Actual count</span>{actualFor(model, row)}</div>
              <div className={cn("text-right font-mono", resultTone(result))}><span className="block text-[11px] text-slate-500">P/L</span>{isSettled(row) ? units(numeric(row.pnl_units)) : "-"}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function CandidateCards({ rows }: { rows: MonitorCsvRow[] }) {
  return (
    <ul className="grid gap-2 md:hidden">
      {rows.map((row, index) => (
        <li key={row.pick_id || `${row.match}-${index}`} className="rounded-xl border border-amber-400/15 bg-amber-400/[0.03] p-3">
          <div className="text-[11px] text-slate-500">{formatDateTimeLabel(row.kickoff_utc || row.match_date)}</div>
          <MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="mt-1 w-full" textClassName="text-sm font-semibold text-slate-100" />
          <div className="mt-3 flex items-center justify-between gap-3 text-sm">
            <span className="font-medium text-amber-100">{cleanText(row.selection)}</span>
            <span className="font-mono text-emerald-300">{pct(numeric(row.edge))}</span>
          </div>
          <div className="mt-2 text-xs leading-5 text-slate-400"><strong className="text-slate-300">Why not registered:</strong> {plainReason(row.blocked_reason) || "Gate not passed"}</div>
        </li>
      ))}
    </ul>
  );
}

function strongestPerFixture(rows: MonitorCsvRow[], model: string): MonitorCsvRow[] {
  const byFixture = new Map<string, MonitorCsvRow>();
  for (const row of rows) {
    if ((row.model || "").trim() !== model) continue;
    const key = row.match_id || `${row.match_date}|${row.league}|${row.match}`;
    const current = byFixture.get(key);
    if (!current || (numeric(row.edge) ?? -999) > (numeric(current.edge) ?? -999)) byFixture.set(key, row);
  }
  return [...byFixture.values()].sort((a, b) => String(a.kickoff_utc || a.match_date).localeCompare(String(b.kickoff_utc || b.match_date)));
}

export default function FootballVnextShadowPanel({
  title,
  model,
  rows,
  candidates,
  gate,
  source,
}: {
  title: string;
  model: "team_shots_v4" | "corners_v3";
  rows: MonitorCsvRow[];
  candidates: MonitorCsvRow[];
  gate: FootballVnextGate | null;
  source?: SourceStatus;
}) {
  const ledger = [...rows].sort((a, b) => String(b.kickoff_utc || b.match_date).localeCompare(String(a.kickoff_utc || a.match_date)));
  const settled = ledger.filter(isSettled);
  const pending = ledger.filter((row) => !isSettled(row));
  const won = settled.filter((row) => resultFor(row) === "won").length;
  const lost = settled.filter((row) => resultFor(row) === "lost").length;
  const pushed = settled.filter((row) => ["push", "void"].includes(resultFor(row))).length;
  const staked = settled.reduce((sum, row) => sum + rowStake(row), 0);
  const pnl = settled.reduce((sum, row) => sum + (numeric(row.pnl_units) ?? 0), 0);
  const roi = staked > 0 ? pnl / staked : null;
  const trueCloseRows = settled.filter((row) => cleanText(row.true_close).toLowerCase() === "true");
  const clvValues = trueCloseRows.map((row) => numeric(row.published_to_close_clv)).filter((value): value is number => value !== null);
  const meanClv = clvValues.length ? clvValues.reduce((sum, value) => sum + value, 0) / clvValues.length : null;
  const sideCounts = ledger.reduce<Record<string, number>>((acc, row) => {
    const side = cleanText(row.side).toLowerCase() || "unknown";
    acc[side] = (acc[side] ?? 0) + 1;
    return acc;
  }, {});
  const dominantSide = Object.entries(sideCounts).sort((a, b) => b[1] - a[1])[0];
  const usesWarmupEvidence = Boolean(gate?.warmup_tracking);
  const evidence = gate?.warmup_tracking ?? gate?.prospective;
  const currentCandidates = strongestPerFixture(candidates, model);
  const gateStatus = cleanText(gate?.promotion_gate || "BLOCKED").replaceAll("_", " ");
  const generatedAt = source?.generatedAt || undefined;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.98),rgba(8,12,20,0.98))] shadow-[0_18px_60px_rgba(0,0,0,0.22)]">
      <div className="border-b border-slate-800 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold tracking-tight text-white">{title}</h2>
              <StatusPill label="Tracked research" tone="border-violet-400/30 bg-violet-400/10 text-violet-200" />
              <StatusPill label={`Promotion ${gateStatus}`} tone="border-rose-400/30 bg-rose-400/10 text-rose-200" />
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Registered and settled for evidence. Not a betting authorization.</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs leading-5 text-slate-400">
            <div>Source <strong className="uppercase text-slate-200">{source?.source ?? "unknown"}</strong></div>
            <div>Generated <strong className="text-slate-200">{formatDateTimeLabel(generatedAt)}</strong></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4 xl:grid-cols-8 sm:p-5">
        <Metric label="Tracked" value={String(ledger.length)} detail={`${evidence?.signals ?? ledger.length} in ${usesWarmupEvidence ? "warm-up" : "prospective"} report`} />
        <Metric label="Settled" value={String(settled.length)} detail={`${won}-${lost}-${pushed} W-L-P`} />
        <Metric label="Pending" value={String(pending.length)} detail="awaiting settlement" tone={pending.length ? "text-amber-200" : undefined} />
        <Metric label="Total staked" value={`${staked.toFixed(1)}u`} detail="settled denominator" />
        <Metric label="P/L" value={units(pnl)} detail="current 2026/27 ledger" tone={metricTone(pnl)} />
        <Metric label="ROI" value={pct(roi)} detail={`${units(pnl)} / ${staked.toFixed(1)}u`} tone={metricTone(roi)} />
        <Metric label="Mean CLV" value={meanClv === null ? "-" : pct(meanClv)} detail={`true close ${clvValues.length} of ${settled.length}`} tone={metricTone(meanClv)} />
        <Metric label="Side skew" value={dominantSide ? `${dominantSide[1]}/${ledger.length}` : "-"} detail={dominantSide ? `${dominantSide[0]} selections` : "no evidence"} />
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="grid gap-3 rounded-xl border border-slate-800 bg-slate-950/45 p-4 lg:grid-cols-[auto_1fr] lg:items-center">
          <div className="flex flex-wrap gap-2">
            <StatusPill label={`Count ${cleanText(gate?.count_gate || "unknown")}`} tone="border-emerald-400/25 bg-emerald-400/10 text-emerald-200" />
            <StatusPill label={`Market ${cleanText(gate?.market_gate || "blocked").replaceAll("_", " ")}`} tone="border-amber-400/25 bg-amber-400/10 text-amber-200" />
            <StatusPill label={`Live routing ${gate?.live_routing ? "on" : "off"}`} tone="border-slate-600 bg-slate-800/70 text-slate-300" />
          </div>
          <p className="text-sm leading-5 text-slate-400 lg:text-right">
            {gate?.latest_scan?.next_unlock ? `Next operational unlock: ${plainReason(gate.latest_scan.next_unlock)}.` : "Promotion remains evidence-gated."}
            {gate?.latest_scan?.explanation ? ` ${cleanText(gate.latest_scan.explanation)}` : ""}
          </p>
        </div>
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-white">Current market scan</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">Strongest priced candidate per fixture. Blocked rows are shown for evaluation and are not betting selections.</p>
          </div>
          <span className="text-xs text-slate-500">{gate?.latest_scan?.scored_rows ?? candidates.filter((row) => row.model === model).length} rows / {gate?.latest_scan?.scored_fixtures ?? currentCandidates.length} fixtures scored</span>
        </div>
        {currentCandidates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/30 px-4 py-5 text-sm leading-6 text-slate-400">
            No current priced candidates. {cleanText(gate?.latest_scan?.explanation) || "The latest capture did not contain a paired market for this lane."}
          </div>
        ) : (
          <>
            <CandidateCards rows={currentCandidates} />
            <div className="hidden overflow-x-auto rounded-xl border border-slate-800 md:block">
              <table className="w-full min-w-[920px] text-left text-xs">
                <thead className="bg-slate-950/85 text-[11px] uppercase tracking-[0.11em] text-slate-500"><tr><th className="px-3 py-3">Kickoff</th><th className="px-3 py-3">Match</th><th className="px-3 py-3">Closest candidate</th><th className="px-3 py-3 text-right">Market odds</th><th className="px-3 py-3 text-right">Fair odds</th><th className="px-3 py-3 text-right">Edge</th><th className="px-3 py-3">Why not registered</th></tr></thead>
                <tbody>{currentCandidates.map((row, index) => <tr key={row.pick_id || `${row.match}-${index}`} className="border-t border-slate-800/80"><td className="whitespace-nowrap px-3 py-3 text-slate-400">{formatDateTimeLabel(row.kickoff_utc || row.match_date)}</td><td className="max-w-[280px] px-3 py-3"><MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="w-full" textClassName="font-medium text-slate-200" /></td><td className="px-3 py-3 text-amber-100">{cleanText(row.selection)}</td><td className="px-3 py-3 text-right font-mono">{priceFor(row)?.toFixed(2) ?? "-"}</td><td className="px-3 py-3 text-right font-mono">{numeric(row.model_fair_odds)?.toFixed(2) ?? "-"}</td><td className={cn("px-3 py-3 text-right font-mono", metricTone(numeric(row.edge)))}>{pct(numeric(row.edge))}</td><td className="max-w-[260px] px-3 py-3 leading-5 text-slate-400">{plainReason(row.blocked_reason) || "Gate not passed"}</td></tr>)}</tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="border-t border-slate-800 px-4 py-4 sm:px-5">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-white">Registered 2026/27 evidence</h3>
            <p className="mt-1 text-xs text-slate-500">Every row below counts toward prospective P/L and ROI, including matchday 1-3 tracking.</p>
          </div>
          <span className="font-mono text-xs text-slate-400">{ledger.length} rows</span>
        </div>
        {ledger.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">No registered selection yet. This lane is at gate stage; see the gate status above.</div>
        ) : (
          <>
            <LedgerCards model={model} rows={ledger} />
            <div className="hidden overflow-x-auto rounded-xl border border-slate-800 md:block">
              <table className="w-full min-w-[1120px] text-left text-xs">
                <thead className="bg-slate-950/95 text-[11px] uppercase tracking-[0.11em] text-slate-500"><tr><th className="px-3 py-3">Date</th><th className="px-3 py-3">Match</th><th className="px-3 py-3">Selection</th><th className="px-3 py-3 text-right">Stake</th><th className="px-3 py-3 text-right">Market odds</th><th className="px-3 py-3 text-right">Fair odds</th><th className="px-3 py-3 text-right">Edge</th><th className="px-3 py-3 text-right">Actual count</th><th className="px-3 py-3">Status</th><th className="px-3 py-3 text-right">P/L</th><th className="px-3 py-3 text-right">CLV</th></tr></thead>
                <tbody>{ledger.map((row, index) => { const result = resultFor(row); const clv = numeric(row.published_to_close_clv); return <tr key={row.pick_id || `${row.match}-${index}`} className="border-t border-slate-800/80"><td className="whitespace-nowrap px-3 py-3 text-slate-400">{formatDateTimeLabel(row.kickoff_utc || row.match_date)}</td><td className="max-w-[260px] px-3 py-3"><MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} className="w-full" textClassName="font-medium text-slate-200" /></td><td className="px-3 py-3"><TeamLabel league={row.league} team={row.team} detail={cleanText(row.selection)} teamClassName="text-slate-200" detailClassName="text-[11px] text-slate-500" /></td><td className="px-3 py-3 text-right font-mono">{rowStake(row).toFixed(1)}u</td><td className="px-3 py-3 text-right font-mono">{priceFor(row)?.toFixed(2) ?? "-"}</td><td className="px-3 py-3 text-right font-mono">{numeric(row.model_fair_odds)?.toFixed(2) ?? "-"}</td><td className={cn("px-3 py-3 text-right font-mono", metricTone(numeric(row.edge)))}>{pct(numeric(row.edge))}</td><td className="px-3 py-3 text-right font-mono">{actualFor(model, row)}</td><td className={cn("px-3 py-3 font-semibold uppercase", resultTone(result))}>{result}<div className="mt-0.5 text-[11px] font-normal normal-case text-slate-600">{cleanText(row.signal_status).replaceAll("_", " ")}</div></td><td className={cn("px-3 py-3 text-right font-mono", resultTone(result))}>{isSettled(row) ? units(numeric(row.pnl_units)) : "-"}</td><td className={cn("px-3 py-3 text-right font-mono", metricTone(clv))}>{clv === null ? "-" : pct(clv)}</td></tr>; })}</tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
