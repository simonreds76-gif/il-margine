import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { promisify } from "node:util";
import { NextResponse } from "next/server";

import { isAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AM_TASK = "IlMargine-Daily-AM";
const NIGHT_TASK = "IlMargine-Daily";
const COMMAND_KEY = "automation.tennis_fair_odds_request";
const ACTIVE_COMMAND_STATES = new Set(["pending", "waiting", "dispatching", "started"]);
const ACTIVE_COMMAND_MAX_AGE_MS = 3 * 60 * 60 * 1000;
const execFileAsync = promisify(execFile);

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

function isLocalWindowsRequest(req: Request): boolean {
  if (process.platform !== "win32") return false;
  const host = new URL(req.url).hostname.toLowerCase().replace(/^\[|\]$/g, "");
  return host === "localhost" || host === "127.0.0.1" || host === "::1";
}

function taskExecutable(): string {
  return `${process.env.WINDIR || "C:\\Windows"}\\System32\\schtasks.exe`;
}

async function queryTask(taskName: string): Promise<{ exists: boolean; running: boolean }> {
  try {
    const { stdout } = await execFileAsync(taskExecutable(), ["/Query", "/TN", taskName, "/FO", "LIST", "/V"], {
      windowsHide: true,
      timeout: 10_000,
    });
    return { exists: true, running: /(?:^|\r?\n)Status:\s+Running\s*(?:\r?\n|$)/i.test(stdout) };
  } catch {
    return { exists: false, running: false };
  }
}

async function queueHostedRefresh() {
  const supabase = getSupabaseAdmin();
  const { data: currentRow, error: readError } = await supabase
    .from("site_settings")
    .select("value")
    .eq("key", COMMAND_KEY)
    .maybeSingle();
  if (readError) throw new Error(`Unable to read refresh queue: ${readError.message}`);

  const current = parseCommand(currentRow?.value);
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
    requested_from: "production_admin",
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
    message: "Fair-odds refresh queued. The laptop will start it within two minutes and Telegram alerts follow signal generation.",
  });
}

export async function POST(req: Request) {
  if (!(await isAdminSession())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isLocalWindowsRequest(req)) {
    try {
      return await queueHostedRefresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to queue fair-odds refresh";
      return NextResponse.json({ error: message }, { status: 500 });
    }
  }

  const [amState, nightState] = await Promise.all([queryTask(AM_TASK), queryTask(NIGHT_TASK)]);
  if (!amState.exists) {
    return NextResponse.json(
      { error: `${AM_TASK} is not installed. Run scripts/setup-automation-tasks.ps1 once.` },
      { status: 404 },
    );
  }
  if (amState.running || nightState.running) {
    return NextResponse.json(
      { error: "A tennis fair-odds refresh is already running. No second run was started." },
      { status: 409 },
    );
  }

  try {
    await execFileAsync(taskExecutable(), ["/Run", "/TN", AM_TASK], {
      windowsHide: true,
      timeout: 10_000,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to start scheduled task";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  return NextResponse.json({
    ok: true,
    mode: "started",
    task: AM_TASK,
    started_at: new Date().toISOString(),
    message: "Fair-odds refresh started. Telegram alerts follow signal generation.",
    telegram: "The existing digest sends new alerts after signal generation completes.",
  });
}
