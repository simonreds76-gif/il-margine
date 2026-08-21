import { after, type NextRequest, NextResponse } from "next/server";
import { WORLD_CUP_TELEGRAM_URL } from "@/lib/config";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import {
  getTelegramClickMetadata,
  sanitizeTelegramClickSource,
  TELEGRAM_CLICK_TABLE,
} from "@/lib/telegram-clicks";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BOT_USER_AGENT = /bot|crawler|spider|preview|slurp|facebookexternalhit|whatsapp|telegrambot|discordbot/i;

function shouldTrackClick(request: NextRequest): boolean {
  const purpose = request.headers.get("purpose") || request.headers.get("sec-purpose") || "";
  if (purpose.toLowerCase().includes("prefetch")) return false;
  if (request.headers.has("next-router-prefetch")) return false;
  return !BOT_USER_AGENT.test(request.headers.get("user-agent") || "");
}

export async function GET(request: NextRequest) {
  const source = sanitizeTelegramClickSource(request.nextUrl.searchParams.get("source"));
  const metadata = getTelegramClickMetadata(request.headers);

  if (shouldTrackClick(request)) {
    after(async () => {
      try {
        const supabase = getSupabaseAdmin();
        const { error } = await supabase.from(TELEGRAM_CLICK_TABLE).insert({ source, ...metadata });
        // Keep total click tracking alive during a rolling deploy if the analytics
        // columns have not reached the database yet.
        if (error?.code === "PGRST204" || /column .* does not exist/i.test(error?.message || "")) {
          const { error: legacyError } = await supabase.from(TELEGRAM_CLICK_TABLE).insert({ source });
          if (legacyError) {
            console.warn(`[telegram-redirect] tracking_failed source=${source} error=${legacyError.message}`);
          }
          return;
        }
        if (error) console.warn(`[telegram-redirect] tracking_failed source=${source} error=${error.message}`);
      } catch (error) {
        const message = error instanceof Error ? error.message : "unknown_error";
        console.warn(`[telegram-redirect] tracking_failed source=${source} error=${message}`);
      }
    });
  }

  const response = NextResponse.redirect(WORLD_CUP_TELEGRAM_URL, 302);
  response.headers.set("X-Robots-Tag", "noindex, nofollow");
  response.headers.set("Cache-Control", "no-store");
  return response;
}
