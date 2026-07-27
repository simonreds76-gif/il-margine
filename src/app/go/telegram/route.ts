import { type NextRequest, NextResponse } from "next/server";
import { WORLD_CUP_TELEGRAM_URL } from "@/lib/config";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const rawSource = request.nextUrl.searchParams.get("source") ?? "unknown";
  const source = rawSource.toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 64) || "unknown";
  console.info(`[telegram-redirect] source=${source}`);
  const response = NextResponse.redirect(WORLD_CUP_TELEGRAM_URL, 302);
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  response.headers.set("Cache-Control", "no-store");
  return response;
}
