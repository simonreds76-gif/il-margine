import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";

import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const COMMAND_KEY = "automation.tennis_fair_odds_request";
const ACTIVE_COMMAND_STATES = new Set(["pending", "waiting", "dispatching", "started"]);
const ACTIVE_COMMAND_MAX_AGE_MS = 3 * 60 * 60 * 1000;

type RefreshCommand = {
  request_id?: string;
  requested_at?: string;
  state?: string;
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
    message: "Fair-odds refresh queued. It normally takes 10-20 minutes; this panel will confirm signal generation and Telegram relay status.",
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
    return NextResponse.json({ ok: true, command });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to read fair-odds refresh status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
