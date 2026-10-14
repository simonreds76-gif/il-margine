import "server-only";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { readClubPenaltyData } from "@/lib/club-penalty-takers";
import { readPenaltyReviewState } from "@/lib/goalscorer-penalty-review-state";
import { readPenaltyEditorial } from "@/lib/penalty-editorial-store";
import { penaltyKey } from "@/lib/penalty-editorial";
import type { PenaltyAdminReport, ReviewTicket } from "@/lib/penalty-admin-types";
const text = (x: unknown) => typeof x === "string" ? x : "";
const normal = (x: string) => penaltyKey("", x);
const clubAlias: Record<string, string> = {"la-liga|deportivoalaves": "Alaves", "la-liga|deportivoacoruna": "Deportivo La Coruna"};
export async function penaltyAdminReport(): Promise<PenaltyAdminReport> {
  const [state, leagues, decisions, snapshot] = await Promise.all([
    readPenaltyEditorial(), readClubPenaltyData(), readPenaltyReviewState(),
    getSupabaseAdmin().from("goalscorer_live_snapshot").select("generated:payload->>generated_at,watchlist:payload->penalty_watchlist,roles:payload->preseason_role_review").eq("snapshot_key", "monitor_state").abortSignal(AbortSignal.timeout(8000)).single(),
  ]);
  if (snapshot.error || !snapshot.data?.watchlist) throw new Error("Penalty ticket snapshot unavailable. Existing decisions are preserved.");
  const clubs = leagues.flatMap(l => l.teams.map(t => ({id: penaltyKey(l.key, t.team), team: t.team, league: l.label, leagueKey: l.key, url: t.relativeUrl, order: {primary: t.primary, secondary: t.secondary, tertiary: t.tertiary}, note: t.conditionNote})));
  const raw = snapshot.data as unknown as {generated: string; watchlist: {rows?: Record<string, unknown>[]}; roles?: {rows?: Record<string, unknown>[]}};
  const rows = [...(raw.watchlist.rows ?? []), ...(raw.roles?.rows ?? [])];
  const tickets: ReviewTicket[] = rows.filter(r => text(r.row_id)).map(r => {
    const league = leagues.find(l => [l.key, l.label, l.short].some(s => normal(s) === normal(text(r.league))));
    const team = text(r.public_team) || text(r.team);
    const lookupTeam = clubAlias[penaltyKey(league?.key ?? "", team)] ?? team;
    const club = clubs.find(c => c.leagueKey === league?.key && normal(c.team) === normal(lookupTeam));
    return {id: text(r.row_id), clubId: club?.id ?? null, team, league: text(r.league), date: text(r.date) || text(r.generated_at), match: text(r.match) || [team, text(r.opponent)].filter(Boolean).join(" vs "),
      taker: text(r.actual_taker) || text(r.proposed_primary), result: text(r.event_result), reason: text(r.review_type) || text(r.reason), priority: text(r.review_priority), status: decisions[text(r.row_id)]?.status ?? "active",
      evidence: [text(r.editorial_note), ...(["primary", "secondary", "tertiary"] as const).map(slot => {const name = text(r[`${slot}_pre_match`]); return name ? `${slot}: ${name}. At the penalty: ${text(r[`${slot}_on_pitch_at_penalty`]) || "unknown"}` : "";})].filter(Boolean)};
  });
  return {revision: state.revision, generatedAt: raw.generated, clubs, tickets: [...new Map(tickets.map(t => [t.id, t])).values()], audit: state.payload.audit.slice(-100).reverse()};
}
