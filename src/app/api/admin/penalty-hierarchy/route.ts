import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";
import { revalidatePath } from "next/cache";
import { isAdminSession } from "@/lib/admin-auth";
import { clubPenaltySlug } from "@/lib/club-penalty-takers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const execute = promisify(execFile);
const ACTIONS = new Set(["override", "lock", "unlock", "release", "revert"]);

function localAuthority(request: Request) {
  const host = new URL(request.url).hostname;
  return !process.env.VERCEL && (host === "localhost" || host === "127.0.0.1" || host === "[::1]");
}

async function invoke(args: string[]) {
  const executable = process.env.PYTHON_EXECUTABLE || (process.platform === "win32" ? "python" : "python3");
  const command = [path.join(process.cwd(), "scripts/club-penalty-hierarchy-review.py"), ...args];
  try {
    const { stdout } = await execute(executable, command, { cwd: process.cwd(), timeout: 30_000, maxBuffer: 8 * 1024 * 1024, windowsHide: true });
    return { body: JSON.parse(stdout), status: 200 };
  } catch (error) {
    const stdout = typeof error === "object" && error && "stdout" in error ? String(error.stdout) : "";
    if (stdout) {
      try {
        const body = JSON.parse(stdout);
        return { body, status: body.conflict ? 409 : 400 };
      } catch { /* Process failures do not become a successful save. */ }
    }
    return { body: { ok: false, error: "The local hierarchy worker failed. No successful save was confirmed; reload the review before retrying." }, status: 503 };
  }
}

export async function GET(request: Request) {
  if (!(await isAdminSession())) return NextResponse.json({ ok: false, error: "Sign in to the admin account." }, { status: 401 });
  if (!localAuthority(request)) return NextResponse.json({ ok: false, error: "Hierarchy controls use the durable local repository. Open the local admin monitor; this hosted process cannot save repository changes." }, { status: 503 });
  const result = await invoke(["--inspect"]);
  return NextResponse.json(result.body, { status: result.status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: Request) {
  if (!(await isAdminSession())) return NextResponse.json({ ok: false, error: "Sign in to the admin account." }, { status: 401 });
  if (!localAuthority(request)) return NextResponse.json({ ok: false, error: "Hosted hierarchy writes are unavailable. Use the local admin monitor; no remote or temporary save was made." }, { status: 503 });
  if (request.headers.get("origin") !== new URL(request.url).origin) return NextResponse.json({ ok: false, error: "Same-origin admin request required." }, { status: 403 });
  try {
    const raw = await request.text();
    if (raw.length > 12_000) return NextResponse.json({ ok: false, error: "Change request is too large." }, { status: 413 });
    const payload = JSON.parse(raw);
    if (!payload || typeof payload !== "object" || !ACTIONS.has(payload.action)
      || typeof payload.id !== "string" || !Number.isInteger(payload.expected_revision)
      || typeof payload.expected_entry_hash !== "string" || typeof payload.reason !== "string") {
      return NextResponse.json({ ok: false, error: "Invalid hierarchy change request." }, { status: 400 });
    }
    // Fixed executable/script, fixed arguments, no shell or user-supplied paths.
    const result = await invoke(["--command-json", JSON.stringify(payload)]);
    if (result.status === 200 && result.body.ok) {
      const [league, club] = payload.id.split("|");
      revalidatePath("/penalty-takers");
      revalidatePath(`/penalty-takers/${league}`);
      revalidatePath(`/penalty-takers/${league}/${clubPenaltySlug(club)}`);
    }
    return NextResponse.json(result.body, { status: result.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ ok: false, error: "Unable to parse hierarchy change request." }, { status: 400 });
  }
}
