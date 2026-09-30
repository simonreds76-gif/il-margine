import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { unstable_cache } from "next/cache";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { object, type EvidenceObject } from "@/lib/tennis-monitor-overview";

const hosted = unstable_cache(async (): Promise<EvidenceObject | null> => {
  try {
    const { data, error } = await getSupabaseAdmin().from("goalscorer_live_snapshot")
      .select("generated_at:payload->>generated_at,sections:payload->sections")
      .eq("snapshot_key", "tennis_evidence_v1").abortSignal(AbortSignal.timeout(5000)).maybeSingle();
    if (!error && data && object(data).sections) return object(data);
  } catch { /* The UI explicitly reports unavailable evidence. */ }
  return null;
}, ["tennis-monitor-evidence-v1"], { revalidate: 300 });

async function readSnapshot(): Promise<EvidenceObject | null> {
  if (!process.env.VERCEL) {
    try {
      return object(JSON.parse(await readFile(path.join(process.cwd(), "data/tennis-props/tennis-evidence-snapshot.json"), "utf8")));
    } catch { /* Hosted snapshot is the next source, never a zero-result fallback. */ }
  }
  return hosted();
}

export async function readTennisEvidence() {
  const snapshot = await readSnapshot();
  return { snapshot, checkedAt: Date.now() };
}
