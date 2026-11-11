import "server-only";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { readCornersLiveFile } from "@/lib/corners-live-files";
import { propsBreakdowns, footballModel } from "@/lib/monitor-breakdowns";
import { readTeamShotsLiveFile } from "@/lib/team-shots-live-files";
import { modelRows, obj, savedSelections } from "@/lib/admin-model-summary";
import { compactHistory, reconciledHistory, type ProfitHistory } from "@/lib/model-profit-history";

/** Authenticated, read-only, compact hosted queries. Canonical football reader reused; no background refresh or model execution. */
export async function readAdminModels() {
  if (!await isAdminSession()) throw new Error("Unauthorized");
  const read = async (key: string, select: string) => {
    try {
      const { data, error } = await getSupabaseAdmin().from("goalscorer_live_snapshot")
        .select(select).eq("snapshot_key", key).abortSignal(AbortSignal.timeout(8000)).maybeSingle();
      return error ? null : obj(data);
    } catch { return null; }
  };
  const [tennis, football, gkLedger, gkReport, shotsLedger, countsRaw, cornersLedger, opponentRaw, opponentLedger] = await Promise.all([
    read("tennis_evidence_v1", 'generated_at:payload->>generated_at,sections:payload->sections,props_ledger:payload->admin_files->>"props-record",histories:payload->admin_profit_histories'),
    read("corners_state", 'generated_at:payload->>generated_at,report:payload->files->"data/football-form/weekly-research-report.json",corners_ledger:payload->files->"data/football-form/corners-v3-shadow-clv.csv"'),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv").catch(() => null),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-shadow-report.json").catch(() => null),
    readTeamShotsLiveFile("data/football-form/team-shots-v4-shadow-clv.csv").catch(() => null),
    readTeamShotsLiveFile("data/football-form/football-counts-vnext-gate.json").catch(() => null),
    readCornersLiveFile("data/football-form/corners-v3-shadow-clv.csv").catch(() => null),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-status.json").catch(() => null),
    readTeamShotsLiveFile("data/football-form/team-shots-opponent-shadow.csv").catch(() => null),
  ]);
  let report: unknown = null;
  try {
    const content = obj(football?.report).content;
    if (typeof content === "string") report = JSON.parse(content);
  } catch { /* Display unavailable; never invent a zero record. */ }
  let keeper: Record<string, unknown> = {};
  try { keeper = obj(JSON.parse(gkReport || "{}")); } catch { /* Keep existing summary on an unavailable source. */ }
  const parse = (raw: string | null) => { try { return obj(JSON.parse(raw || "{}")); } catch { return {}; } };
  const counts = parse(countsRaw), opponent = parse(opponentRaw);
  const rows = modelRows(tennis?.sections, report).filter(r => !r.id.startsWith("props-"));
  const gk = rows.find(r=>r.id==="gk"), evidence=obj(keeper.evidence);
  if (gk && typeof evidence.settled==="number" && typeof evidence.pnl_units==="number") {
    gk.settled=evidence.settled; gk.profit=evidence.pnl_units;
    gk.roi=typeof evidence.roi==="number" ? evidence.roi*100 : null;
    gk.pending=typeof evidence.pending==="number" ? evidence.pending : null;
    gk.date=typeof keeper.generated_at==="string" ? keeper.generated_at : gk.date;
    const quoteReviews=typeof evidence.quote_quarantined==="number" ? evidence.quote_quarantined : 0;
    gk.note=`Canonical scheduled goalkeeper record. ${quoteReviews>0?`${quoteReviews} captured quotes held for review. `:''}Disputed quotes, duplicates and voids excluded from settled betting profit.`;
  }
  const histories: Record<string, ProfitHistory> = {};
  for (const r of rows.filter(r=>["strict","volume_200","challenger","spread_v1","provisional_hard","provisional_expansion","astra"].includes(r.id))) {
    histories[r.id]=compactHistory(obj(tennis?.histories)[r.id],r);
  }
  if (gk) histories.gk = reconciledHistory(gkLedger, "gk", gk);
  for (const [id, name, raw, generated, ledger, note] of [
    ["team_shots_v4", "Team Shots v4", obj(counts.team_shots_v4).prospective, counts.generated_at, shotsLedger, "Current Team Shots selection model; still collecting. Forward paper only, warm-up results excluded."],
    ["corners_v3", "Corners v3", obj(counts.corners_v3).prospective, counts.generated_at, cornersLedger, "Current corners paper model. Warm-up results excluded. No approved replacement; v4 G0 failed its saved research evaluation."],
    ["team_shots_opponent", "Opponent Shots", opponent.prospective, opponent.generated_at, opponentLedger, "Separate fixed Team Shots paper model; still collecting. Not discontinued and not a replacement for v4. Zero real stake."],
  ] as const) {
    const previous = rows.findIndex(r => r.id === id);
    const fresh = footballModel(id, name, raw, generated, ledger, note);
    // Never silently fall back to an older weekly headline while plotting a newer ledger.
    if (previous >= 0) rows[previous] = fresh.row; else rows.push(fresh.row);
    histories[id] = fresh.history;
  }
  const props = rows.find(r => r.id === "props");
  if (props) {
    histories.props = reconciledHistory(tennis?.props_ledger, "props-record", props);
    const breakdown = propsBreakdowns(tennis?.props_ledger, props);
    rows.push(...breakdown.rows); Object.assign(histories, breakdown.histories);
  }
  for (const r of rows.filter(r => ["tennis_hardcourt_scout", "tennis_astrissimo", "tennis_indoor_paper", "tennis_indoor_expansion"].includes(r.id))) {
    histories[r.id] = reconciledHistory(obj(obj(tennis?.sections)[r.id]).selections, r.id, r);
  }
  return { rows, histories, selections: savedSelections(tennis?.sections), sisal5050: obj(tennis?.sections).tennis_sisal_5050, breakpointC: obj(tennis?.sections).tennis_breakpoint_c, matchShape: obj(tennis?.sections).tennis_match_shape,
    sources: [{name: "Tennis snapshot", date: tennis?.generated_at, available: !!tennis?.sections},
      {name: "Football capture", date: counts.generated_at, available: !!countsRaw},
      {name: "Weekly football review", date: obj(report).generated_at, available: !!report}], checkedAt: Date.now() };
}
