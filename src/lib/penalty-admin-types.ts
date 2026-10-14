import type { PenaltyOrder, PenaltyEditorial, TicketDecision } from "./penalty-editorial";
export type ReviewClub = {id: string; team: string; league: string; leagueKey: string; url: string; order: PenaltyOrder; note: string};
export type ReviewTicket = {id: string; clubId: string | null; team: string; league: string; date: string; match: string; taker: string; result: string; reason: string; priority: string; evidence: string[]; status: TicketDecision["status"]};
export type PenaltyAdminReport = {revision: number; generatedAt: string; clubs: ReviewClub[]; tickets: ReviewTicket[]; audit: PenaltyEditorial["audit"]};
