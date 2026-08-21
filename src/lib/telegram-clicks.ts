import "server-only";

import { createHmac } from "node:crypto";

export const TELEGRAM_CLICK_TABLE = "telegram_clicks";

export function sanitizeTelegramClickSource(value: string | null): string {
  return value?.toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 64) || "unknown";
}

export type TelegramClickMetadata = {
  visitor_hash: string | null;
  country_code: string | null;
  device_type: "mobile" | "tablet" | "desktop" | "other";
  browser_family: "Chrome" | "Edge" | "Firefox" | "Opera" | "Safari" | "Samsung Internet" | "Other";
};

function firstForwardedAddress(headers: Headers): string {
  const forwarded =
    headers.get("x-vercel-forwarded-for") ||
    headers.get("x-forwarded-for") ||
    headers.get("x-real-ip") ||
    "";
  return forwarded.split(",", 1)[0]?.trim().slice(0, 128) || "";
}

function classifyDevice(userAgent: string): TelegramClickMetadata["device_type"] {
  if (/ipad|tablet|kindle|silk|android(?!.*mobile)/i.test(userAgent)) return "tablet";
  if (/mobile|iphone|ipod|android|windows phone/i.test(userAgent)) return "mobile";
  if (/windows|macintosh|cros|x11|linux/i.test(userAgent)) return "desktop";
  return "other";
}

function classifyBrowser(userAgent: string): TelegramClickMetadata["browser_family"] {
  if (/samsungbrowser/i.test(userAgent)) return "Samsung Internet";
  if (/edg(?:e|a|ios)?\//i.test(userAgent)) return "Edge";
  if (/opr\/|opera/i.test(userAgent)) return "Opera";
  if (/firefox\/|fxios\//i.test(userAgent)) return "Firefox";
  if (/chrome\/|crios\//i.test(userAgent)) return "Chrome";
  if (/safari\//i.test(userAgent)) return "Safari";
  return "Other";
}

function sanitizeCountryCode(value: string | null): string | null {
  const code = value?.trim().toUpperCase() || "";
  return /^[A-Z]{2}$/.test(code) ? code : null;
}

export function getTelegramClickMetadata(headers: Headers): TelegramClickMetadata {
  const userAgent = (headers.get("user-agent") || "").slice(0, 512);
  const address = firstForwardedAddress(headers);
  // A dedicated salt is preferred. The service-role key is a stable server-only fallback,
  // and is never included in the digest or response.
  const hashSecret = process.env.TELEGRAM_CLICK_HASH_SALT || process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  const visitorHash = hashSecret && (address || userAgent)
    ? createHmac("sha256", hashSecret)
        .update(`telegram-click-v1\n${address || "unknown-address"}\n${userAgent || "unknown-agent"}`)
        .digest("hex")
    : null;

  return {
    visitor_hash: visitorHash,
    country_code: sanitizeCountryCode(headers.get("x-vercel-ip-country")),
    device_type: classifyDevice(userAgent),
    browser_family: classifyBrowser(userAgent),
  };
}

export function utcDayKey(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}
