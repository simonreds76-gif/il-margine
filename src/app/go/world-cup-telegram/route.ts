import { NextResponse } from "next/server";
import { WORLD_CUP_TELEGRAM_URL } from "@/lib/config";

export const dynamic = "force-static";

export async function GET() {
  const response = NextResponse.redirect(WORLD_CUP_TELEGRAM_URL, 302);
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  return response;
}
