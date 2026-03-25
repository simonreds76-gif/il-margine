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

const REVIEW_PACKS = {
  goalscorer: [
    "scripts/fotmob-fetch-lineups.py",
    "scripts/goalscorer_penalty_utils.py",
    "scripts/goalscorer-live-compare.py",
    "scripts/goalscorer-model.py",
    "scripts/goalscorer-penalty-review.py",
    "scripts/goalscorer-live-penalty-review.py",
    "scripts/run-goalscorer-pipeline.py",
    "scripts/build-penalty-baseline-evidence.py",
    "scripts/goalscorer-shadow-tracker.py",
    "src/lib/goalscorer-live-files.ts",
    "src/app/model-monitor/goalscorer/page.tsx",
  ],
  tennis: [
    "src/lib/tennis_prob.py",
    "scripts/oncourt-compute-fair-odds.py",
    "scripts/compute-handicap-values.py",
    "scripts/shrinkage_v2.py",
  ],
} as const;

type ReviewPackName = keyof typeof REVIEW_PACKS;

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

function getRequestedPack(request: Request): ReviewPackName {
  const url = new URL(request.url);
  const requested = (url.searchParams.get("pack")?.trim().toLowerCase() || "goalscorer") as ReviewPackName;
  return requested in REVIEW_PACKS ? requested : "goalscorer";
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

  const pack = getRequestedPack(request);
  const reviewFiles = REVIEW_PACKS[pack];
  const files: ReviewPackFile[] = [];

  for (const relativePath of reviewFiles) {
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
      pack,
      available_packs: Object.keys(REVIEW_PACKS),
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
