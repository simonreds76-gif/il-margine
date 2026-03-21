import { promises as fs } from "fs";
import path from "path";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";
const PREVIEW_REVIEW_PACK_OPEN = process.env.VERCEL_ENV === "preview";

const REVIEW_PACK_TOKEN =
  process.env.MODEL_MONITOR_REVIEW_PACK_TOKEN ||
  process.env.MODEL_MONITOR_REVIEW_TOKEN ||
  "";

const REVIEW_FILES = [
  "scripts/goalscorer_penalty_utils.py",
  "scripts/goalscorer-live-compare.py",
  "scripts/goalscorer-model.py",
  "src/lib/goalscorer-live-files.ts",
  "src/app/model-monitor/goalscorer/page.tsx",
] as const;

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type ReviewPackFile = {
  path: string;
  bytes: number;
  content: string;
};

function getSuppliedToken(request: Request): string {
  const url = new URL(request.url);
  return (
    url.searchParams.get("token")?.trim() ||
    request.headers.get("x-review-token")?.trim() ||
    ""
  );
}

export async function GET(request: Request) {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
    return new Response("Not found", { status: 404 });
  }

  if (!PREVIEW_REVIEW_PACK_OPEN && !REVIEW_PACK_TOKEN) {
    return Response.json(
      { error: "Review pack token is not configured." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  if (!PREVIEW_REVIEW_PACK_OPEN) {
    const suppliedToken = getSuppliedToken(request);
    if (!suppliedToken || suppliedToken !== REVIEW_PACK_TOKEN) {
      return Response.json(
        { error: "Unauthorized" },
        { status: 401, headers: { "Cache-Control": "no-store" } },
      );
    }
  }

  const files: ReviewPackFile[] = [];

  for (const relativePath of REVIEW_FILES) {
    const absolutePath = path.join(process.cwd(), relativePath);
    const content = await fs.readFile(absolutePath, "utf8");
    files.push({
      path: relativePath,
      bytes: Buffer.byteLength(content, "utf8"),
      content,
    });
  }

  return Response.json(
    {
      generated_at: new Date().toISOString(),
      file_count: files.length,
      files,
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
