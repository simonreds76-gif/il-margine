import "server-only";

import { BASE_URL } from "@/lib/config";
import { formatMatchDate, formatOdds, formatStake } from "@/lib/format";
import { publicTipPath } from "@/lib/tip-seo";
import { isWorldCupPropsTip } from "@/lib/world-cup-tips";
import { telegramBookmakerPartner } from "@/lib/telegram-bookmakers";
import { resolveBookmakerLogo } from "@/lib/bookmaker-logos";

type BookmakerShape = {
  name?: string | null;
  short_name?: string | null;
};

export type PlayerPropsTelegramTip = {
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
  | { status: "posted"; url: string; mode?: "photo" | "text_fallback" }
  | { status: "skipped"; reason: "not_player_props" | "disabled" | "missing_config"; url?: string }
  | { status: "failed"; reason: string; url?: string };

type TelegramMessageEntity = { type: "bold" | "text_link"; offset: number; length: number; url?: string };

type TelegramMessagePayload = {
  text: string;
  html: string;
  entities: TelegramMessageEntity[];
  reply_markup: { inline_keyboard: { text: string; url: string }[][] };
};

type TelegramAttempt = { ok: true } | { ok: false; reason: string };

function utf16Length(value: string): number {
  return Array.from(value).reduce((total, char) => total + (char.codePointAt(0)! > 0xffff ? 2 : 1), 0);
}

function truncate(value: string, maxLength: number): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trimEnd()}...`;
}

function firstBookmaker(bookmaker: PlayerPropsTelegramTip["bookmaker"]): BookmakerShape | null {
  if (!bookmaker) return null;
  if (Array.isArray(bookmaker)) return bookmaker[0] ?? null;
  return bookmaker;
}

function bookmakerLabel(tip: PlayerPropsTelegramTip): string | null {
  const bookmaker = firstBookmaker(tip.bookmaker);
  return resolveBookmakerLogo(bookmaker)?.displayName || bookmaker?.short_name || bookmaker?.name || null;
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// The builder emits disjoint spans. Serialize before multipart normalizes LF to
// CRLF: Telegram parses tags against the received caption, so offsets cannot drift.
function telegramHtml(text: string, entities: TelegramMessageEntity[]): string {
  let html = "";
  let cursor = 0;
  for (const entity of entities) {
    html += escapeHtml(text.slice(cursor, entity.offset));
    const label = escapeHtml(text.slice(entity.offset, entity.offset + entity.length));
    html += entity.type === "bold" ? `<b>${label}</b>` : `<a href="${escapeHtml(entity.url!)}">${label}</a>`;
    cursor = entity.offset + entity.length;
  }
  return html + escapeHtml(text.slice(cursor));
}

export function playerPropsTipUrl(tip: PlayerPropsTelegramTip): string {
  return `${BASE_URL}${publicTipPath(tip)}`;
}

function displayOdds(value: PlayerPropsTelegramTip["odds"]): string {
  if (value === null || value === undefined || value === "") return "-";
  return formatOdds(value);
}

function displayStake(value: PlayerPropsTelegramTip["stake"]): string {
  if (value === null || value === undefined || value === "") return "-";
  return `${formatStake(value)}u`;
}

export function renderPlayerPropsTipPayload(tip: PlayerPropsTelegramTip): TelegramMessagePayload {
  const url = playerPropsTipUrl(tip);
  const worldCup = isWorldCupPropsTip(tip);
  const event = truncate(tip.event || "Player props", 90);
  const player = truncate(tip.player || "", 80);
  const selection = truncate(tip.selection || "Selection", 120);
  const pickLine = player ? `${player} - ${selection}` : selection;
  const bookmaker = truncate(bookmakerLabel(tip) || "", 35);
  const partner = telegramBookmakerPartner(bookmaker, BASE_URL);
  const notes = truncate(tip.notes || "", 200);

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
  const appendLink = (value: string, target: string) => {
    const offset = utf16Length(text);
    append(value);
    entities.push({ type: "text_link", offset, length: utf16Length(value), url: target });
  };

  appendBold(worldCup ? "Il Margine WC Pick" : "Il Margine Player Prop");
  newline(2);
  appendBold(event);
  newline();
  appendBold(pickLine);
  newline(2);
  append("Odds: ");
  appendBold(displayOdds(tip.odds));
  append("  |  Stake: ");
  appendBold(displayStake(tip.stake));
  newline();

  if (bookmaker) {
    append("Bookmaker: ");
    if (partner) appendLink(partner.name, partner.url);
    else append(bookmaker);
    newline();
  }
  if (tip.match_date) {
    append("Match: ");
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
  appendLink("Full pick & tracked results", url);
  newline();
  append("Odds recorded at publication; availability can change.");
  if (partner) { newline(); append("Bookmaker link is an affiliate link."); }

  return { text, html: telegramHtml(text, entities), entities, reply_markup: { inline_keyboard: [
    ...(partner ? [[{ text: `Open ${partner.name} ↗`, url: partner.url }]] : []),
    [{ text: "Full pick & results", url }],
  ] } };
}

function playerPropsTipCardUrl(tip: PlayerPropsTelegramTip): string {
  const bookmaker = bookmakerLabel(tip);
  const params = new URLSearchParams({
    v: "3",
    scope: isWorldCupPropsTip(tip) ? "worldcup" : "props",
    event: tip.event || "Player props",
    player: tip.player || "",
    selection: tip.selection || "Selection",
    odds: displayOdds(tip.odds),
    stake: displayStake(tip.stake),
    bookmaker: bookmaker || "Bookmaker",
    date: tip.match_date ? formatMatchDate(tip.match_date) : "",
  });

  return `${BASE_URL}/api/telegram/wc-tip-card?${params.toString()}`;
}

async function fetchTipCardBlob(tip: PlayerPropsTelegramTip): Promise<Blob> {
  const cardUrl = playerPropsTipCardUrl(tip);
  const response = await fetch(cardUrl, { cache: "no-store" });
  const contentType = response.headers.get("content-type") || "";

  if (!response.ok || !contentType.toLowerCase().includes("image/")) {
    const body = await response.text().catch(() => "");
    throw new Error(
      `card_http_${response.status}${contentType ? `_${contentType}` : ""}${body ? `: ${truncate(body, 120)}` : ""}`,
    );
  }

  const blob = await response.blob();
  if (blob.size === 0) throw new Error("card_empty_image");
  return blob;
}

async function sendTelegramPhotoUpload(
  token: string,
  chatId: string,
  tip: PlayerPropsTelegramTip,
  payload: TelegramMessagePayload,
): Promise<TelegramAttempt> {
  try {
    const cardBlob = await fetchTipCardBlob(tip);
    const form = new FormData();
    form.append("chat_id", chatId);
    form.append("photo", cardBlob, `ilmargine-player-prop-${tip.id}.png`);
    form.append("caption", payload.html);
    form.append("parse_mode", "HTML");
    form.append("reply_markup", JSON.stringify(payload.reply_markup));

    const response = await fetch(`https://api.telegram.org/bot${token}/sendPhoto`, {
      method: "POST",
      body: form,
    });

    if (response.ok) return { ok: true };
    const body = await response.text().catch(() => "");
    return { ok: false, reason: `telegram_photo_http_${response.status}${body ? `: ${truncate(body, 180)}` : ""}` };
  } catch (error) {
    return { ok: false, reason: error instanceof Error ? error.message : "telegram_photo_failed" };
  }
}

async function sendTelegramText(
  token: string,
  chatId: string,
  payload: TelegramMessagePayload,
): Promise<TelegramAttempt> {
  try {
    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: payload.html,
        parse_mode: "HTML",
        reply_markup: payload.reply_markup,
        disable_web_page_preview: true,
      }),
    });

    if (response.ok) return { ok: true };
    const body = await response.text().catch(() => "");
    return { ok: false, reason: `telegram_text_http_${response.status}${body ? `: ${truncate(body, 180)}` : ""}` };
  } catch (error) {
    return { ok: false, reason: error instanceof Error ? error.message : "telegram_text_failed" };
  }
}

export async function postPlayerPropTipToTelegram(tip: PlayerPropsTelegramTip): Promise<TelegramPostResult> {
  const url = playerPropsTipUrl(tip);
  if ((tip.market || "").toLowerCase() !== "props") return { status: "skipped", reason: "not_player_props", url };

  const postingEnabled = process.env.PLAYER_PROPS_TELEGRAM_POSTING_ENABLED ?? process.env.WC_TELEGRAM_POSTING_ENABLED;
  if (postingEnabled !== "true") {
    return { status: "skipped", reason: "disabled", url };
  }

  const token = (process.env.PLAYER_PROPS_TELEGRAM_BOT_TOKEN || process.env.WC_TELEGRAM_BOT_TOKEN)?.trim();
  const chatId = (process.env.PLAYER_PROPS_TELEGRAM_CHAT_ID || process.env.WC_TELEGRAM_CHAT_ID)?.trim();
  if (!token || !chatId) return { status: "skipped", reason: "missing_config", url };

  const payload = renderPlayerPropsTipPayload(tip);
  const photoAttempt = await sendTelegramPhotoUpload(token, chatId, tip, payload);
  if (photoAttempt.ok) return { status: "posted", url, mode: "photo" };

  const textAttempt = await sendTelegramText(token, chatId, payload);
  if (textAttempt.ok) return { status: "posted", url, mode: "text_fallback" };

  return {
    status: "failed",
    reason: `${photoAttempt.reason}; fallback_${textAttempt.reason}`,
    url,
  };
}
