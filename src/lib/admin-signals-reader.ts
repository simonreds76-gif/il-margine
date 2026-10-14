import "server-only";
import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import catalog from "../../config/admin-monitor-catalog.json";
export {catalog};
export async function readAdminSignalFile(id: string | null) {
  if (!await isAdminSession()) throw new Error("Unauthorized");
  if (id && !catalog.some(v=>v.id===id)) throw new Error("Unknown model view");
  const selection = id ? `generated_at:payload->>generated_at,manifest:payload->admin_manifest,content:payload->admin_files->>"${id}"` : "generated_at:payload->>generated_at,manifest:payload->admin_manifest";
  const {data,error}=await getSupabaseAdmin().from("goalscorer_live_snapshot").select(selection).eq("snapshot_key","tennis_evidence_v1").abortSignal(AbortSignal.timeout(10000)).single();
  if(error || !data) throw new Error("Private model snapshot unavailable.");
  return data as unknown as {generated_at:string;manifest:Array<{id:string;available:boolean;modified_at?:string;error?:string}>;content?:string};
}
