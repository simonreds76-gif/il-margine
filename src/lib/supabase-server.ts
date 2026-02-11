import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

/** Server-only Supabase client with service role (bypasses RLS). Use in API routes only. */
export function getSupabaseAdmin() {
  if (!url || !serviceRoleKey) throw new Error("SUPABASE_SERVICE_ROLE_KEY and NEXT_PUBLIC_SUPABASE_URL required for admin API.");
  return createClient(url, serviceRoleKey);
}
