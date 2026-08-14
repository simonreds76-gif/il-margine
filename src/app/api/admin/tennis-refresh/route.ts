import { execFile } from "node:child_process";
import { createHmac } from "node:crypto";
import { promisify } from "node:util";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;
const COOKIE_NAME = "admin_session";
const AM_TASK = "IlMargine-Daily-AM";
const NIGHT_TASK = "IlMargine-Daily";
const execFileAsync = promisify(execFile);

function getSignedToken(): string {
  if (!ADMIN_PASSWORD) return "";
  return createHmac("sha256", ADMIN_PASSWORD).update("admin_session").digest("base64url");
}

async function isAdmin(): Promise<boolean> {
  if (!ADMIN_PASSWORD) return false;
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_NAME)?.value === getSignedToken();
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

export async function POST(req: Request) {
  if (!(await isAdmin())) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isLocalWindowsRequest(req)) {
    return NextResponse.json(
      { error: "Manual fair-odds refresh is available only from Admin on localhost." },
      { status: 400 },
    );
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
    task: AM_TASK,
    started_at: new Date().toISOString(),
    telegram: "The existing digest sends new alerts after signal generation completes.",
  });
}
