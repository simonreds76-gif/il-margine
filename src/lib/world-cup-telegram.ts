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

type TelegramMessageEntity = { type: "bold"; offset: number; length: number };

type TelegramMessagePayload = {
  text: string;
  entities: TelegramMessageEntity[];
};

function utf16Length(value: string): number {
  return Array.from(value).reduce((total, char) => total + (char.codePointAt(0)! > 0xffff ? 2 : 1), 0);
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

function renderWorldCupTipPayload(tip: WorldCupTelegramTip): TelegramMessagePayload {
  const url = worldCupTipUrl(tip);
  const event = tip.event || "World Cup";
  const player = truncate(tip.player || "", 80);
  const selection = truncate(tip.selection || "Selection", 120);
  const pickLine = player ? `${player} - ${selection}` : selection;
  const bookmaker = bookmakerLabel(tip);
  const notes = truncate(tip.notes || "", 260);

  let text = "";
  const entities: TelegramMessageEntity[] = [];
  const append = (value: string) => {
    text += value;
  };
  const appendBold = (value: string) => {
    const offset = utf16Length(text);
    append(value);
    entities.push({ type: "bold", offset, length: utf16Length(value) });
  };
  const newline = (count = 1) => append("\n".repeat(count));

  appendBold("Il Margine WC Pick");
  newline(2);
  appendBold(event);
  newline();
  append(pickLine);
  newline(2);
  append("Odds: ");
  appendBold(displayOdds(tip.odds));
  newline();
  append("Stake: ");
  appendBold(displayStake(tip.stake));
  newline();

  if (bookmaker) {
    append("Bookmaker: ");
    appendBold(bookmaker);
    newline();
  }
  if (tip.match_date) {
    append("Match date: ");
    appendBold(formatMatchDate(tip.match_date));
    newline();
  }
  if (notes) {
    newline();
    appendBold("Reasoning:");
    append(` ${notes}`);
    newline();
  }

  newline();
  append("Model-driven World Cup player props and market value.");
  newline(2);
  append(`Full pick: ${url}`);

  return { text, entities };
}

function worldCupTipCardUrl(tip: WorldCupTelegramTip): string {
  const bookmaker = bookmakerLabel(tip);
  const params = new URLSearchParams({
    event: tip.event || "World Cup",
    player: tip.player || "",
    selection: tip.selection || "Selection",
    odds: displayOdds(tip.odds),
    stake: displayStake(tip.stake),
    bookmaker: bookmaker || "Bookmaker",
    date: tip.match_date ? formatMatchDate(tip.match_date) : "",
  });

  return `${BASE_URL}/api/telegram/wc-tip-card?${params.toString()}`;
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
    const payload = renderWorldCupTipPayload(tip);
    const response = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        photo: worldCupTipCardUrl(tip),
        caption: payload.text,
        caption_entities: payload.entities,
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
