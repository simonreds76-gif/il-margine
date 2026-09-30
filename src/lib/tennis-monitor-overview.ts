export type EvidenceObject = Record<string, unknown>;
export const object = (value: unknown): EvidenceObject => value && typeof value === "object" && !Array.isArray(value) ? value as EvidenceObject : {};
const numeric = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;
export type TennisOverviewRow = {
  id: string; name: string; group: "tracked" | "research" | "blocked";
  status: string; note: string; settled: number | null; pending: number | null;
  wins: number | null; losses: number | null; roi: number | null; pnl: number | null;
  stake: number | null; closes: number | null; date: string | null; fixtures: number | null;
  reportDate: string | null; cohort: string | null;
  overdue: number | null; recentPending: number | null; latestSignal: string | null;
};
export function tennisOverviewRows(snapshot: EvidenceObject): TennisOverviewRow[] {
  const sections = object(snapshot.sections);
  const lanes = object(object(sections.tennis_model_evidence).lanes);
  const integrity = object(object(sections.tennis_monitor_integrity).lanes);
  function row(id: string, name: string, data: EvidenceObject, group: TennisOverviewRow["group"], status: string, note: string): TennisOverviewRow {
    const record = object(data.record);
    const laneHealth = object(integrity[id]);
    return { id, name, group, status, note,
      settled: numeric(data.settled), pending: numeric(data.pending),
      wins: numeric(data.wins ?? record.wins), losses: numeric(data.losses ?? record.losses),
      roi: numeric(data.settled) === 0 ? null : numeric(data.roi_pct), pnl: numeric(data.pnl_units), stake: numeric(data.staked_units),
      closes: numeric(object(data.clv).rows ?? data.clv_rows ?? data.clv_coverage), date: typeof data.as_of_date === "string" ? data.as_of_date : null,
      reportDate: typeof data.generated_at === "string" ? data.generated_at : null,
      cohort: typeof data.evidence_period === "string" ? data.evidence_period : null,
      overdue: numeric(laneHealth.overdue), recentPending: numeric(laneHealth.recent_pending),
      latestSignal: typeof laneHealth.latest_signal_date === "string" ? laneHealth.latest_signal_date : null,
      fixtures: numeric(data.independent_fixtures) };
  }
  const result = [
    row("strict", "Strict policy", object(lanes.strict), "tracked", "Hard-court Masters", "High-confidence hard-court Masters selections. The record includes eligible moneyline and handicap bets. An old last-selection date does not mean the daily refresh failed."),
    row("volume_200", "Volume 200", object(lanes.volume_200), "research", "ATP moneyline research", "Current ATP moneyline research policy, reported separately from Strict. Price coverage and probability accuracy must support any claim of an edge."),
    row("challenger", "Challenger ML v2", object(lanes.challenger), "research", "Research only", "Hypothetical one-unit results. Real stake is zero. The rejected original batch is excluded."),
    row("spread_v1", "Spread v1", object(lanes.spread_v1), "research", "Research only", "Handicap selections are a separate record from moneyline bets."),
    row("aces_dfs", "Aces and double faults", object(sections.tennis_props_shadow_decision), "research", "Research only", `Price coverage: ${String(object(object(sections.tennis_props_shadow_decision).feed).state ?? "unavailable").replaceAll("_", " ").toLowerCase()}.`),
  ];
  const rateReport = object(sections.tennis_rate_trend);
  const rates = object(rateReport.markets);
  for (const [market, name] of [["aces", "Astra Aces"], ["double_faults", "Astra Double Faults"]]) {
    const evidence = object(rates[market]); const candidate = object(evidence.candidate); const control = object(evidence.control);
    const baseline = numeric(control.roi_pct);
    const r = row(market, name, { ...evidence, ...candidate, generated_at: rateReport.generated_at, settled: candidate.bets }, "research", "Paired experiment",
      `Candidate versus baseline on the same fixtures, with different selections possible. Baseline ROI: ${baseline === null ? "unavailable" : `${baseline.toFixed(2)}%`}. Pending counts cover all tracked contracts. Multiple lines from one match are related observations.`);
    result.push(r);
  }
  result.push(row("venue", "Venue ace adjustment", object(sections.tennis_venue_ace_factor_v1), "research", "Research only", "Venue experiment. Its recorded selection ROI alone does not measure improvement over the baseline."));
  const mostAces = object(sections.tennis_most_aces_forecast);
  result.push(row("most_aces", "Most aces", { pending: mostAces.rows_pending, generated_at: mostAces.generated_at_utc }, "blocked", "Integrity review", `Forecast observations settled: ${numeric(mostAces.rows_settled) ?? "unavailable"}; quarantined: ${numeric(mostAces.rows_quarantined) ?? "unavailable"}. These are not priced model bets and do not establish ROI.`));
  result.push(row("astra_volume", "Astra Volume", {}, "blocked", "Tracking not connected", "The 69-bet replay is historical research. No forward ROI is available until the frozen collector is connected."));
  const v3 = object(sections.tennis_props_v3);
  result.push(row("props_v3", "Aces v3", { ...object(v3.evidence), generated_at: v3.generated_at }, "blocked", "Needs review", "Inspect the saved report date, capture and settlement before restarting this experiment."));
  const v4 = object(sections.tennis_props_v4);
  result.push(row("props_v4", "Aces v4", { settled: v4.signals_settled, roi_pct: v4.roi_pct, generated_at: v4.generated_at }, "blocked", String(v4.status ?? "Status unavailable").replaceAll("_", " ").toLowerCase(), `Pre-fit observations settled: ${numeric(v4.rows_settled) ?? "unavailable"}. These observations are separate from model bets.`));
  const health = object(sections.tennis_props_pipeline_health);
  result.push(row("breaks", "Service breaks", { generated_at: health.generated_at }, "blocked", String(health.break_state ?? "Status unavailable").replaceAll("_", " ").toLowerCase(), `Matched price rows: ${numeric(health.break_matched_rows) ?? "unavailable"}. Strict eligible rows: ${numeric(health.break_strict_rows) ?? "unavailable"}. Full result diagnostics remain in the props monitor; this snapshot does not provide a betting ROI.`));
  return result;
}
