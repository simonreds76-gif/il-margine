import type { Circuit } from "./types";

export function boardUrl(circuit: Circuit, historyDay?: string, record?: string | null) {
  const query = new URLSearchParams({ tour: circuit.toLowerCase() });
  if (historyDay) {
    query.set("view", "history");
    query.set("day", historyDay);
  }
  if (record === "30d" || record === "sent30") query.set("record", record);
  return "/drop-shot-desk?" + query.toString();
}
