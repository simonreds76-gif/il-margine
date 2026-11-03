import "server-only";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { modelRows, obj, savedSelections } from "@/lib/admin-model-summary";
import { reconciledHistory, type ProfitHistory } from "@/lib/model-profit-history";

/** Authenticated, read-only, compact hosted queries. No disk/GitHub fallback or background refresh. */
export async function readAdminModels() {
  if (!await isAdminSession()) throw new Error("Unauthorized");
  const read = async (key: string, select: string) => {
    try {
      const { data, error } = await getSupabaseAdmin().from("goalscorer_live_snapshot")
        .select(select).eq("snapshot_key", key).abortSignal(AbortSignal.timeout(8000)).maybeSingle();
      return error ? null : obj(data);
    } catch { return null; }
  };
  const [tennis, football] = await Promise.all([
    read("tennis_evidence_v1", 'generated_at:payload->>generated_at,sections:payload->sections,props_ledger:payload->admin_files->>"props-record"'),
    read("corners_state", 'generated_at:payload->>generated_at,report:payload->files->"data/football-form/weekly-research-report.json"'),
  ]);
  let report: unknown = null;
  try {
    const content = obj(football?.report).content;
    if (typeof content === "string") report = JSON.parse(content);
  } catch { /* Display unavailable; never invent a zero record. */ }
  const rows = modelRows(tennis?.sections, report);
  const histories: Record<string, ProfitHistory> = {};
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
