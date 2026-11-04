import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";

import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { isMonitorUploadFailure, reconcileMonitorUpload, type TennisRefreshCommand } from "@/lib/tennis-refresh-status";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COMMAND_KEY = "automation.tennis_fair_odds_request";
const ACTIVE_COMMAND_STATES = new Set(["pending", "waiting", "dispatching", "started"]);
const ACTIVE_COMMAND_MAX_AGE_MS = 3 * 60 * 60 * 1000;

type RefreshCommand = TennisRefreshCommand & {
  [key: string]: unknown;
};

function parseCommand(value: unknown): RefreshCommand | null {
  if (value && typeof value === "object" && !Array.isArray(value)) return value as RefreshCommand;
  if (typeof value !== "string") return null;
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as RefreshCommand) : null;
  } catch {
    return null;
  }
}

function commandIsActive(command: RefreshCommand | null): boolean {
  if (!command?.state || !ACTIVE_COMMAND_STATES.has(command.state)) return false;
  const requestedAt = Date.parse(command.requested_at || "");
  return Number.isFinite(requestedAt) && Date.now() - requestedAt < ACTIVE_COMMAND_MAX_AGE_MS;
}

async function readCommand(): Promise<RefreshCommand | null> {
  const supabase = getSupabaseAdmin();
  const { data: currentRow, error: readError } = await supabase
    .from("site_settings")
    .select("value")
    .eq("key", COMMAND_KEY)
    .maybeSingle();
  if (readError) throw new Error(`Unable to read refresh queue: ${readError.message}`);
  return parseCommand(currentRow?.value);
}

async function withMonitorUploadRecovery(command: RefreshCommand | null): Promise<TennisRefreshCommand | null> {
  if (!command) return null;
  const unchanged = reconcileMonitorUpload(command, null);
  if (!isMonitorUploadFailure(unchanged)) return unchanged;
  try {
    // A compact authenticated read, only for upload failures; no reports, queue
    // writes, model runs or Telegram calls. Keep the original failed receipt.
    const { data, error } = await getSupabaseAdmin()
      .from("goalscorer_live_snapshot")
      .select("updated_at,generated_at:payload->>generated_at,payload_hash:payload->>payload_hash,source:payload->>source,schema_version:payload->schema_version,file_count:payload->monitor_bundle->file_count")
      .eq("snapshot_key", "tennis_evidence_v1")
      .abortSignal(AbortSignal.timeout(8_000))
      .maybeSingle();
    return error ? unchanged : reconcileMonitorUpload(unchanged, data);
  } catch {
    // A failed metadata check must never mask the original upload failure.
    return unchanged;
  }
}

async function queueRefresh(req: Request) {
  const supabase = getSupabaseAdmin();
  const current = await readCommand();

  if (commandIsActive(current)) {
    return NextResponse.json(
      {
        error: "A fair-odds refresh is already queued or running. No duplicate request was created.",
        command: current,
      },
      { status: 409 },
    );
  }

  const requestedAt = new Date().toISOString();
  const command: RefreshCommand = {
    request_id: randomUUID(),
    requested_at: requestedAt,
    requested_from: new URL(req.url).hostname === "localhost" ? "localhost_admin" : "production_admin",
    state: "pending",
  };
  const { error: writeError } = await supabase
    .from("site_settings")
    .upsert({ key: COMMAND_KEY, value: JSON.stringify(command) }, { onConflict: "key" });
  if (writeError) throw new Error(`Unable to queue refresh: ${writeError.message}`);

  return NextResponse.json({
    ok: true,
    mode: "queued",
    command,
    message: "Refresh queued. Keep the laptop on after updating OnCourt. This panel shows the saved database time and completed pricing check; the full run can take 30 minutes or longer.",
  });
}

export async function POST(req: Request) {
  if (!(await isAdminSession())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    return await queueRefresh(req);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to queue fair-odds refresh";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET(req: Request) {
  if (!(await isAdminSession())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const command = await readCommand();
    const requestedId = new URL(req.url).searchParams.get("request_id");
    if (requestedId && command?.request_id !== requestedId) {
      return NextResponse.json({ error: "This refresh request is no longer the active queue record." }, { status: 404 });
    }
    return NextResponse.json({ ok: true, command: await withMonitorUploadRecovery(command) });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to read fair-odds refresh status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
