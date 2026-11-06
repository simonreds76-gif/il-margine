import "server-only";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { signalCsv } from "@/lib/admin-signal-format";
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
  const [tennis, football, gkLedger, gkReport, shotsLedger] = await Promise.all([
    read("tennis_evidence_v1", 'generated_at:payload->>generated_at,sections:payload->sections,props_ledger:payload->admin_files->>"props-record",histories:payload->admin_profit_histories'),
    read("corners_state", 'generated_at:payload->>generated_at,report:payload->files->"data/football-form/weekly-research-report.json",corners_ledger:payload->files->"data/football-form/corners-v3-shadow-clv.csv"'),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv").catch(() => null),
    readTeamShotsLiveFile("data/goalkeeper-saves/gk-saves-v1-shadow-report.json").catch(() => null),
    readTeamShotsLiveFile("data/football-form/team-shots-v4-shadow-clv.csv").catch(() => null),
  ]);
  let report: unknown = null;
  try {
    const content = obj(football?.report).content;
    if (typeof content === "string") report = JSON.parse(content);
  } catch { /* Display unavailable; never invent a zero record. */ }
  let keeper: Record<string, unknown> = {};
  try { keeper = obj(JSON.parse(gkReport || "{}")); } catch { /* Keep existing summary on an unavailable source. */ }
  const rows = modelRows(tennis?.sections, report);
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
  for (const r of rows.filter(r=>["gk","team_shots_v4","corners_v3"].includes(r.id))) {
    const raw=r.id==="gk" ? gkLedger : r.id==="team_shots_v4" ? shotsLedger : obj(football?.corners_ledger).content;
    let content: unknown=raw;
    if(typeof raw==="string" && r.id!=="gk") {
      content=signalCsv(raw).filter(v=>!String(v.blocked_reason||"").trim() && !["true","1","yes"].includes(String(v.confidence_guard_applied).toLowerCase()) && String(v.signal_status).toLowerCase()!=="warmup_tracking");
    }
    histories[r.id]=reconciledHistory(content,r.id,r);
  }
  for (const r of rows.filter(r => r.id === "props" || r.id.startsWith("props-"))) {
    histories[r.id] = reconciledHistory(tennis?.props_ledger, "props-record", r, r.id.startsWith("props-") ? r.id.slice(6) : undefined);
  }
  for (const r of rows.filter(r => ["tennis_hardcourt_scout", "tennis_astrissimo", "tennis_indoor_paper"].includes(r.id))) {
    histories[r.id] = reconciledHistory(obj(obj(tennis?.sections)[r.id]).selections, r.id, r);
  }
  return { rows, histories, selections: savedSelections(tennis?.sections), sisal5050: obj(tennis?.sections).tennis_sisal_5050, breakpointC: obj(tennis?.sections).tennis_breakpoint_c, matchShape: obj(tennis?.sections).tennis_match_shape,
    sources: [{name: "Tennis snapshot", date: tennis?.generated_at, available: !!tennis?.sections},
      {name: "Football report", date: obj(report).generated_at, available: !!report}], checkedAt: Date.now() };
}
