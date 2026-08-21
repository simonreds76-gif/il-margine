import "server-only";

export const TELEGRAM_CLICK_TABLE = "telegram_clicks";

export function sanitizeTelegramClickSource(value: string | null): string {
  return value?.toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 64) || "unknown";
}

export function utcDayKey(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}
