import "server-only";
import { unstable_cache } from "next/cache";
import { getSupabaseAdmin, hasSupabaseAdminConfig } from "@/lib/supabase-server";
import type { PenaltyState, PenaltyEditorial, EditorialOverride } from "@/lib/penalty-editorial";
export const PENALTY_EDITORIAL_TAG = "penalty-editorial";
export async function readPenaltyEditorial(): Promise<PenaltyState> {
  const {data, error} = await getSupabaseAdmin().from("admin_penalty_state").select("revision,payload").eq("id", "editorial").abortSignal(AbortSignal.timeout(8000)).single();
  if (error || !data || !Number.isInteger(data.revision) || !data.payload?.tickets || !data.payload?.clubs || !Array.isArray(data.payload?.audit)) throw new Error("Private review storage is unavailable. No change was saved.");
  return data as PenaltyState;
}
export async function savePenaltyEditorial(revision: number, payload: PenaltyEditorial) {
  const {data, error} = await getSupabaseAdmin().from("admin_penalty_state").update({revision: revision + 1, payload, updated_at: new Date().toISOString()}).eq("id", "editorial").eq("revision", revision).select("revision").abortSignal(AbortSignal.timeout(8000)).maybeSingle();
  if (error) throw new Error("Save was not confirmed. Reload before retrying.");
  if (!data) throw new Error("CONFLICT: The review changed in another tab. Reload before saving.");
  return data.revision as number;
}
// Shared server cache, invalidated only after an editorial save. Never fetch per visitor.
export const readPenaltyOverrides = unstable_cache(async (): Promise<Record<string, EditorialOverride>> => {
  if (!hasSupabaseAdminConfig()) {
    if (process.env.VERCEL) throw new Error("Hosted editorial storage is not configured");
    return {};
  }
  const {data, error} = await getSupabaseAdmin().from("admin_penalty_state").select("clubs:payload->clubs").eq("id", "editorial").abortSignal(AbortSignal.timeout(8000)).single();
  // Throw on outage so ISR retains the last successful page, rather than reverting saved orders.
  if (error || !data?.clubs || typeof data.clubs !== "object") throw new Error("Unable to load saved penalty orders");
  return data.clubs as Record<string, EditorialOverride>;
}, ["penalty-editorial-orders-v1"], {revalidate: 43200, tags: [PENALTY_EDITORIAL_TAG]});
