export type PenaltyOrder = { primary: string; secondary: string; tertiary: string };
export type TicketDecision = { status: "ignored" | "applied" | "deferred" | "active" | "accepted"; updated_at: string };
export type EditorialOverride = { order: PenaltyOrder; season: string; at: string; reason: string; source: string };
export type PenaltyEditorial = {
  tickets: Record<string, TicketDecision>;
  clubs: Record<string, EditorialOverride>;
  audit: Array<{id: string; at: string; action: string; ticket: string; club: string; before: PenaltyOrder | null; after: PenaltyOrder | null; reason: string}>;
};
export type PenaltyState = {revision: number; payload: PenaltyEditorial};
export const penaltyKey = (league: string, team: string) => `${league}|${team.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "")}`;
export function validOrder(raw: unknown): PenaltyOrder {
  if (!raw || typeof raw !== "object") throw new Error("Enter the penalty taker order.");
  const r = raw as Record<string, unknown>;
  const order = Object.fromEntries(["primary", "secondary", "tertiary"].map(k => {
    if (typeof r[k] !== "string" || r[k].length > 120 || /[\u0000-\u001f<>]/.test(r[k])) throw new Error("Invalid player name.");
    return [k, r[k].trim().replace(/\s+/g, " ")];
  })) as PenaltyOrder;
  if (!order.primary || (!order.secondary && order.tertiary)) throw new Error("Enter a first choice and fill the order without gaps.");
  const names = Object.values(order).filter(Boolean).map(n => penaltyKey("", n));
  if (new Set(names).size !== names.length) throw new Error("A player cannot appear twice in the order.");
  return order;
}
export function editorialChange(state: PenaltyState, command: {action: "done" | "defer" | "reopen" | "save"; ticket: string; club: string; order?: unknown; reason?: string; source?: string}, before: PenaltyOrder | null, season: string, at: string, id: string): PenaltyEditorial {
  const next: PenaltyEditorial = structuredClone(state.payload);
  let after: PenaltyOrder | null = null;
  if (command.action === "save") {
    after = validOrder(command.order);
    const reason = command.reason?.trim() ?? "";
    if (reason.length < 5 || reason.length > 1200) throw new Error("Add a short explanation for the public hierarchy.");
    const source = command.source?.trim() ?? "";
    if (source) { let url: URL; try {url = new URL(source);} catch {throw new Error("Enter a valid source URL.");} if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || source.length > 1500) throw new Error("Enter a public http or https source URL."); }
    next.clubs[command.club] = {order: after, reason, source, season, at};
  }
  if (command.ticket) next.tickets[command.ticket] = {status: command.action === "done" ? "ignored" : command.action === "save" ? "applied" : command.action === "defer" ? "deferred" : "active", updated_at: at};
  next.audit.push({id, at, action: command.action, ticket: command.ticket, club: command.club, before, after, reason: command.action === "save" ? command.reason!.trim() : command.action === "done" ? "Reviewed; keep current order" : command.action});
  return next;
}
