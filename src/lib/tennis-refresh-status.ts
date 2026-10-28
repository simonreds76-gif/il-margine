export type TennisRefreshCommand = {
  request_id?: string;
  state?: string;
  error?: string;
  requested_at?: string;
  oncourt_database_updated_at?: string;
  oncourt_extracted_at?: string;
  odds_not_before?: string;
  signal_generation_completed_at?: string;
  completed_at?: string;
  telegram_status?: string;
  telegram_dispatched_at?: string;
};

export function tennisRefreshIsActive(command: TennisRefreshCommand | null): boolean {
  return ["pending", "waiting", "dispatching", "started"].includes(command?.state || "");
}

export function tennisRefreshStatusMessage(command: TennisRefreshCommand): string {
  if (command.state === "failed") return command.error || "Fair-odds refresh failed.";
  if (command.state === "completed") {
    // signal_count in older receipts is the day's notification history, not
    // the number of selections still eligible after this refresh.
    const delivery = command.telegram_status === "relay_queued"
      ? " Telegram relay queued; this is not confirmation of delivery."
      : " Check the signals in Monitor for the latest selections.";
    return `Refresh completed. Fair prices and qualifying selections checked.${delivery}`;
  }
  if (command.state === "waiting") return "Waiting for the current tennis job to finish. This request will then use a new extraction and price check.";
  if (command.state === "started") return "Refreshing on the laptop. The full run can take 30 minutes or longer; you can leave this page and return to check its status.";
  return "Queued for the laptop. Keep it on and connected; pickup normally takes under two minutes.";
}

export function refreshTime(value?: string): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    timeZone: "Europe/London", timeZoneName: "short",
  }).format(new Date(value));
}
