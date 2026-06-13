import "server-only";

import { BASE_URL } from "@/lib/config";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { slugifyTip } from "@/lib/slugify";
import { isWorldCupPropsTip } from "@/lib/world-cup-tips";

type BookmakerShape = {
  name?: string | null;
  short_name?: string | null;
};

export type WorldCupTelegramTip = {
  id: number;
  market?: string | null;
  category?: string | null;
  event?: string | null;
  player?: string | null;
  selection?: string | null;
  odds?: number | string | null;
  stake?: number | string | null;
  match_date?: string | null;
  notes?: string | null;
  bookmaker?: BookmakerShape | BookmakerShape[] | null;
};

export type TelegramPostResult =
  | { status: "posted"; url: string }
  | { status: "skipped"; reason: "not_worldcup_props" | "disabled" | "missing_config"; url?: string }
  | { status: "failed"; reason: string; url?: string };

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function truncate(value: string, maxLength: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function firstBookmaker(bookmaker: WorldCupTelegramTip["bookmaker"]): BookmakerShape | null {
  if (!bookmaker) return null;
  if (Array.isArray(bookmaker)) return bookmaker[0] ?? null;
  return bookmaker;
}

function bookmakerLabel(tip: WorldCupTelegramTip): string | null {
  const bookmaker = firstBookmaker(tip.bookmaker);
  return bookmaker?.short_name || bookmaker?.name || null;
}

export function worldCupTipUrl(tip: Pick<WorldCupTelegramTip, "id" | "event">): string {
  return `${BASE_URL}/tips/${slugifyTip(tip.event || "world-cup-tip", tip.id)}`;
}

function displayOdds(value: WorldCupTelegramTip["odds"]): string {
  if (value === null || value === undefined || value === "") return "-";
  return formatOdds(value);
}

function displayStake(value: WorldCupTelegramTip["stake"]): string {
  if (value === null || value === undefined || value === "") return "-";
  return `${formatStake(value)}u`;
}

function renderWorldCupTipMessage(tip: WorldCupTelegramTip): string {
  const url = worldCupTipUrl(tip);
  const event = escapeHtml(tip.event || "World Cup");
  const player = truncate(tip.player || "", 80);
  const selection = truncate(tip.selection || "Selection", 120);
  const pickLine = player ? `${escapeHtml(player)} - ${escapeHtml(selection)}` : escapeHtml(selection);
  const bookmaker = bookmakerLabel(tip);
  const notes = truncate(tip.notes || "", 260);

  const lines = [
    "<b>Il Margine WC Pick</b>",
    "",
    `<b>${event}</b>`,
    pickLine,
    "",
    `Odds: <b>${escapeHtml(displayOdds(tip.odds))}</b>`,
    `Stake: <b>${escapeHtml(displayStake(tip.stake))}</b>`,
  ];

  if (bookmaker) lines.push(`Bookmaker: <b>${escapeHtml(bookmaker)}</b>`);
  if (tip.match_date) lines.push(`Match date: <b>${escapeHtml(formatMatchDate(tip.match_date))}</b>`);
  if (notes) {
    lines.push("");
    lines.push(`<b>Reasoning:</b> ${escapeHtml(notes)}`);
  }

  lines.push("");
  lines.push("Model-driven World Cup player props and market value.");
  lines.push("");
  lines.push(`Full pick: ${url}`);

  return lines.join("\n");
}

export async function postWorldCupTipToTelegram(tip: WorldCupTelegramTip): Promise<TelegramPostResult> {
  const url = worldCupTipUrl(tip);
  if (!isWorldCupPropsTip(tip)) return { status: "skipped", reason: "not_worldcup_props", url };

  if (process.env.WC_TELEGRAM_POSTING_ENABLED !== "true") {
    return { status: "skipped", reason: "disabled", url };
  }

  const token = process.env.WC_TELEGRAM_BOT_TOKEN?.trim();
  const chatId = process.env.WC_TELEGRAM_CHAT_ID?.trim();
  if (!token || !chatId) return { status: "skipped", reason: "missing_config", url };

  try {
    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: renderWorldCupTipMessage(tip),
        parse_mode: "HTML",
        disable_web_page_preview: false,
      }),
    });

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      return {
        status: "failed",
        reason: `telegram_http_${response.status}${body ? `: ${truncate(body, 180)}` : ""}`,
        url,
      };
    }

    return { status: "posted", url };
  } catch (error) {
    return {
      status: "failed",
      reason: error instanceof Error ? error.message : "telegram_request_failed",
      url,
    };
  }
}
