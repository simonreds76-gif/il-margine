export type TennisRefreshCommand = {
  request_id?: string;
  state?: string;
  error?: string;
  phase?: string;
  progress_message?: string;
  telegram_new_signals?: number;
  requested_at?: string;
  oncourt_database_updated_at?: string;
  oncourt_extracted_at?: string;
  odds_not_before?: string;
  signal_generation_completed_at?: string;
  completed_at?: string;
  telegram_status?: string;
  telegram_dispatched_at?: string;
  // Derived from the hosted snapshot on GET; never saved in the request record.
  monitor_upload_recovered_at?: string;
};

export type MonitorSnapshotMetadata = {
  updated_at?: unknown;
  generated_at?: unknown;
  payload_hash?: unknown;
  source?: unknown;
  schema_version?: unknown;
  file_count?: unknown;
};

export function isMonitorUploadFailure(command: TennisRefreshCommand | null): boolean {
  return command?.state === "failed" && command.error === "Private Monitor upload failed.";
}

export function reconcileMonitorUpload(
  command: TennisRefreshCommand,
  snapshot: MonitorSnapshotMetadata | null,
  now = Date.now(),
): TennisRefreshCommand {
  // Never carry an earlier derived recovery into a different request or outage.
  const current = { ...command };
  delete current.monitor_upload_recovered_at;
  if (!isMonitorUploadFailure(current) || !current.request_id || !snapshot) return current;
  if (snapshot.source !== "windows_local_tennis_pipeline" || snapshot.schema_version !== 3) return current;
  if (typeof snapshot.payload_hash !== "string" || !/^[a-f0-9]{64}$/i.test(snapshot.payload_hash)) return current;
  if (typeof snapshot.file_count !== "number" || snapshot.file_count <= 0) return current;
  const failedAt = Date.parse(current.completed_at || "");
  const generatedAt = typeof snapshot.generated_at === "string" ? Date.parse(snapshot.generated_at) : NaN;
  const uploadedAt = typeof snapshot.updated_at === "string" ? Date.parse(snapshot.updated_at) : NaN;
  if (![failedAt, generatedAt, uploadedAt].every(Number.isFinite)) return current;
  // The publisher writes updated_at = generated_at after validating the payload.
  // This proves a later saved snapshot exists, not that the failed run completed
  // or that every underlying input / betting price is up to date.
  if (generatedAt <= failedAt || uploadedAt !== generatedAt || generatedAt > now + 60_000) return current;
  return { ...current, monitor_upload_recovered_at: snapshot.generated_at as string };
}

export function tennisRefreshStatusType(command: TennisRefreshCommand): "success" | "error" | "info" {
  if (isMonitorUploadFailure(command) && command.monitor_upload_recovered_at) return "info";
  return command.state === "failed" ? "error" : "success";
}

export function tennisRefreshIsActive(command: TennisRefreshCommand | null): boolean {
  return ["pending", "waiting", "dispatching", "started"].includes(command?.state || "");
}

export function tennisRefreshStatusMessage(command: TennisRefreshCommand): string {
  if (isMonitorUploadFailure(command) && command.monitor_upload_recovered_at) {
    return "Monitor upload recovered: a newer saved snapshot is available. The earlier refresh remains recorded as failed. This confirms the upload only, not fresh prices or Telegram delivery.";
  }
  if (command.state === "failed") return command.error || "Fair-odds refresh failed.";
  if (command.state === "completed") {
    // signal_count in older receipts is the day's notification history, not
    // the number of selections still eligible after this refresh.
    const delivery = command.telegram_status === "relay_queued"
      ? " Telegram relay queued; this is not confirmation of delivery."
      : command.telegram_status === "checked_no_new"
        ? " No new qualifying selections to send; earlier alerts were not repeated."
        : " Check the signals in Monitor for the latest selections.";
    return `Refresh completed. Fair prices and qualifying selections checked.${delivery}`;
  }
  if (command.progress_message && tennisRefreshIsActive(command)) return command.progress_message;
  if (command.state === "waiting") return "Waiting for shared input access. Historical reporting yields between operations so this refresh can run next.";
  if (command.state === "started") return "Refreshing saved OnCourt inputs, prices and selections on the laptop. Historical reports run separately; you can leave this page and return.";
  return "Queued for the laptop. Keep it on and connected; pickup normally takes under two minutes.";
}

export function refreshTime(value?: string): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not recorded";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    timeZone: "Europe/London", timeZoneName: "short",
  }).format(new Date(value));
}
