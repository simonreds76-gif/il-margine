type Row = Record<string, string>;

type ProspectiveGate = {
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
  prospective?: ProspectiveGate;
  latest_scan?: LatestScan;
};

function numberValue(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function percent(value: number | null, digits = 1): string {
  if (value === null) return "-";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function units(value: number | null): string {
  if (value === null) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function resultTone(result: string): string {
  if (result === "won") return "text-emerald-300";
  if (result === "lost") return "text-rose-300";
  return "text-slate-400";
}

function blockReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    matchdays_1_to_3: "MD1-3 safety block",
    edge_below_3pct: "Edge below 3%",
    canonical_only: "Canonical source required",
    confidence_guard: "Confidence guard",
  };
  return reason
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => labels[part] ?? part.replaceAll("_", " "))
    .join(" · ");
}

function Metric({ label, value, detail, tone = "text-slate-100" }: { label: string; value: string; detail?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/55 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-lg tabular-nums ${tone}`}>{value}</div>
      {detail ? <div className="mt-1 text-[11px] text-slate-500">{detail}</div> : null}
    </div>
  );
}

export default function FootballVnextShadowPanel({
  title,
  model,
  rows,
  candidates,
  gate,
}: {
  title: string;
  model: "team_shots_v4" | "corners_v3";
  rows: Row[];
  candidates: Row[];
  gate: FootballVnextGate | null;
}) {
  const active = rows.filter((row) => !(row.blocked_reason ?? "").trim() && (row.confidence_guard_applied ?? "").toLowerCase() !== "true");
  const settled = active.filter((row) => ["won", "lost", "push"].includes((row.result ?? "").toLowerCase()));
  const pending = active
    .filter((row) => !row.result || row.result.toLowerCase() === "pending")
    .sort((a, b) => (a.kickoff_utc ?? "").localeCompare(b.kickoff_utc ?? ""));
  const pnl = settled.reduce((sum, row) => sum + (numberValue(row.pnl_units) ?? 0), 0);
  const roi = settled.length > 0 ? pnl / settled.length : null;
  const trueClose = settled.filter((row) => (row.true_close ?? "").toLowerCase() === "true");
  const trueCloseClv = trueClose
    .map((row) => numberValue(row.published_to_close_clv))
    .filter((value): value is number => value !== null);
  const meanClv = trueCloseClv.length > 0
    ? trueCloseClv.reduce((sum, value) => sum + value, 0) / trueCloseClv.length
    : null;
  const modelCandidates = candidates.filter((row) => row.model === model);
  const eligibleCandidates = modelCandidates.filter((row) => row.signal_status === "eligible");
  const blockedCandidates = modelCandidates.filter(
    (row) => row.signal_status === "blocked" || Boolean((row.blocked_reason ?? "").trim()),
  );
  const strongestBlockedByFixture = new Map<string, Row>();
  for (const row of blockedCandidates) {
    const fixtureKey = row.match_id || `${row.match_date}|${row.match}`;
    const incumbent = strongestBlockedByFixture.get(fixtureKey);
    if (!incumbent || (numberValue(row.edge) ?? Number.NEGATIVE_INFINITY) > (numberValue(incumbent.edge) ?? Number.NEGATIVE_INFINITY)) {
      strongestBlockedByFixture.set(fixtureKey, row);
    }
  }
  const blockedWatchlist = [...strongestBlockedByFixture.values()]
    .sort((a, b) => (numberValue(b.edge) ?? Number.NEGATIVE_INFINITY) - (numberValue(a.edge) ?? Number.NEGATIVE_INFINITY))
    .slice(0, 8);
  const evidence = gate?.prospective;
  const latestScan = gate?.latest_scan;
  const scanIsExpectedWarmup = latestScan?.state === "EXPECTED_WARMUP_BLOCK";
  const scanIsHealthy = scanIsExpectedWarmup || latestScan?.state === "ELIGIBLE_CANDIDATES_PRESENT";
  const scanBlockers = Object.entries(latestScan?.blocker_rows ?? {})
    .map(([reason, count]) => `${blockReasonLabel(reason)} ${count}`)
    .join(" · ");

  return (
    <section className="overflow-hidden rounded-2xl border border-cyan-500/25 bg-[linear-gradient(135deg,rgba(8,47,73,.22),rgba(2,6,23,.9)_45%,rgba(15,23,42,.86))] shadow-[0_18px_70px_rgba(2,132,199,.08)]">
      <div className="border-b border-slate-800/90 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold text-white">{title}</h2>
              <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-amber-200">
                Shadow only
              </span>
              <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 font-mono text-[10px] text-cyan-200">
                {model}
              </span>
            </div>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-400">
              Automatic prospective signals from the locked model. They are settled and checked against close, but are not a proven betting lane until every promotion gate passes.
            </p>
          </div>
          <div className="text-right text-[11px] text-slate-500">
            <div>Count gate <span className="font-semibold text-emerald-300">{gate?.count_gate ?? "-"}</span></div>
            <div>Promotion <span className="font-semibold text-amber-300">{gate?.promotion_gate ?? "BLOCKED"}</span></div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-3 xl:grid-cols-6 sm:p-5">
        <Metric label="Open signals" value={String(pending.length)} detail={`${eligibleCandidates.length} eligible this scan`} tone={pending.length > 0 ? "text-cyan-200" : undefined} />
        <Metric label="Settled" value={String(settled.length)} detail={`${settled.filter((row) => row.result?.toLowerCase() === "won").length}W / ${settled.filter((row) => row.result?.toLowerCase() === "lost").length}L`} />
        <Metric label="P/L" value={units(pnl)} detail="1u shadow stake" tone={pnl > 0 ? "text-emerald-300" : pnl < 0 ? "text-rose-300" : undefined} />
        <Metric label="ROI" value={percent(roi)} detail="secondary gate" tone={roi !== null && roi > 0 ? "text-emerald-300" : roi !== null && roi < 0 ? "text-rose-300" : undefined} />
        <Metric label="True close" value={settled.length ? `${trueClose.length}/${settled.length}` : "-"} detail={evidence?.true_close_coverage != null ? `${(evidence.true_close_coverage * 100).toFixed(0)}% coverage` : "awaiting settlements"} />
        <Metric label="Mean CLV" value={percent(meanClv)} detail={`true close n=${trueCloseClv.length}`} tone={meanClv !== null && meanClv > 0 ? "text-emerald-300" : meanClv !== null && meanClv < 0 ? "text-rose-300" : undefined} />
      </div>

      <div className="border-t border-slate-800/80 px-4 py-4 sm:px-5">
        <div className={`rounded-xl border px-4 py-3 ${scanIsHealthy ? "border-cyan-400/20 bg-cyan-400/5" : "border-amber-400/20 bg-amber-400/5"}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Latest pipeline scan</div>
              <div className={`mt-1 font-mono text-sm font-semibold ${scanIsHealthy ? "text-cyan-200" : "text-amber-200"}`}>
                {(latestScan?.state ?? "NOT_RUN").replaceAll("_", " ")}
              </div>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-400">
                {latestScan?.explanation ?? "No reason-coded scan summary has been generated yet."}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-right text-[11px] text-slate-500">
              <div><span className="block font-mono text-sm text-slate-200">{latestScan?.scored_rows ?? 0}</span>rows scored</div>
              <div><span className="block font-mono text-sm text-slate-200">{latestScan?.scored_fixtures ?? 0}</span>fixtures</div>
              <div><span className="block font-mono text-sm text-amber-200">{latestScan?.edge_pass_but_warmup_blocked_fixtures ?? 0}</span>edge-pass held</div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-slate-800/70 pt-2 text-[11px] text-slate-500">
            <span>Matchday range <strong className="font-mono text-slate-300">{latestScan?.matchday_min ?? "-"}–{latestScan?.matchday_max ?? "-"}</strong></span>
            <span>Eligible rows <strong className="font-mono text-slate-300">{latestScan?.eligible_rows ?? 0}</strong></span>
            <span>Blocked rows <strong className="font-mono text-slate-300">{latestScan?.blocked_rows ?? 0}</strong></span>
            <span>Blockers <strong className="font-medium text-slate-300">{scanBlockers || "-"}</strong></span>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800/80 px-4 py-4 sm:px-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-300">Current shadow signals</h3>
          <span className="text-[11px] text-slate-500">3% minimum edge | MD1-3 blocked | one per fixture</span>
        </div>
        {pending.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-950/35 px-4 py-5 text-sm text-slate-500">
            No eligible signal at the latest scan. {modelCandidates.length > 0 ? `${modelCandidates.length} paired prices were evaluated and failed a gate.` : "No current paired two-way prices were available."}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full min-w-[850px] text-left text-xs">
              <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="px-3 py-2.5">Kickoff</th><th className="px-3 py-2.5">Match</th><th className="px-3 py-2.5">Signal</th>
                  <th className="px-3 py-2.5 text-right">Price</th><th className="px-3 py-2.5 text-right">Fair</th><th className="px-3 py-2.5 text-right">Edge</th>
                  <th className="px-3 py-2.5 text-right">MD</th><th className="px-3 py-2.5">Book</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((row) => {
                  const price = numberValue(row.book_price_at_publication || row.pinnacle_price_at_publication || row.book_odds);
                  const fair = numberValue(row.model_fair_odds);
                  const edge = numberValue(row.edge);
                  return (
                    <tr key={row.pick_id} className="border-t border-slate-800/80 bg-slate-950/30">
                      <td className="whitespace-nowrap px-3 py-3 text-slate-400">{(row.kickoff_utc || row.match_date || "-").replace("T", " ").slice(0, 16)}</td>
                      <td className="px-3 py-3 font-medium text-slate-200">{row.match || "-"}</td>
                      <td className="px-3 py-3 text-cyan-100">{row.selection || "-"}</td>
                      <td className="px-3 py-3 text-right font-mono text-white">{price?.toFixed(2) ?? "-"}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{fair?.toFixed(2) ?? "-"}</td>
                      <td className="px-3 py-3 text-right font-mono text-emerald-300">{percent(edge)}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-400">{row.matchday || "-"}</td>
                      <td className="px-3 py-3 text-slate-400">{row.bookmaker || "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {blockedWatchlist.length > 0 ? (
        <div className="border-t border-slate-800/80 px-4 py-4 sm:px-5">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-[0.15em] text-amber-200">Gate-blocked watchlist</h3>
              <p className="mt-1 text-xs text-slate-500">
                Strongest priced candidate per fixture. These are visible for evaluation only and are not official tips.
              </p>
            </div>
            <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-amber-200">
              Do not bet as model signals
            </span>
          </div>
          <div className="overflow-x-auto rounded-xl border border-amber-400/15">
            <table className="w-full min-w-[940px] text-left text-xs">
              <thead className="bg-slate-950/80 text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="px-3 py-2.5">Kickoff</th><th className="px-3 py-2.5">Match</th><th className="px-3 py-2.5">Closest candidate</th>
                  <th className="px-3 py-2.5 text-right">Price</th><th className="px-3 py-2.5 text-right">Fair</th><th className="px-3 py-2.5 text-right">Edge</th>
                  <th className="px-3 py-2.5">Why blocked</th>
                </tr>
              </thead>
              <tbody>
                {blockedWatchlist.map((row) => {
                  const price = numberValue(row.book_price_at_publication || row.pinnacle_price_at_publication || row.book_odds);
                  const fair = numberValue(row.model_fair_odds);
                  const edge = numberValue(row.edge);
                  return (
                    <tr key={`blocked-${row.pick_id}`} className="border-t border-slate-800/80 bg-amber-950/5">
                      <td className="whitespace-nowrap px-3 py-3 text-slate-400">{(row.kickoff_utc || row.match_date || "-").replace("T", " ").slice(0, 16)}</td>
                      <td className="px-3 py-3 font-medium text-slate-200">{row.match || "-"}</td>
                      <td className="px-3 py-3 text-amber-100">{row.selection || "-"}</td>
                      <td className="px-3 py-3 text-right font-mono text-white">{price?.toFixed(2) ?? "-"}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{fair?.toFixed(2) ?? "-"}</td>
                      <td className={`px-3 py-3 text-right font-mono ${edge !== null && edge > 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {percent(edge)}
                      </td>
                      <td className="px-3 py-3 text-slate-400">{blockReasonLabel(row.blocked_reason ?? "blocked")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {settled.length > 0 ? (
        <details className="border-t border-slate-800/80 px-4 py-3 sm:px-5">
          <summary className="cursor-pointer text-xs font-semibold text-slate-400 hover:text-slate-200">Recent settled shadow results</summary>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {[...settled].reverse().slice(0, 8).map((row) => (
              <div key={row.pick_id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/45 px-3 py-2 text-xs">
                <div><div className="text-slate-200">{row.match}</div><div className="text-slate-500">{row.selection}</div></div>
                <div className={`text-right font-mono ${resultTone(row.result)}`}><div>{row.result?.toUpperCase()}</div><div>{units(numberValue(row.pnl_units))}</div></div>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}
