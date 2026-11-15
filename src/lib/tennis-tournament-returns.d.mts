import type { TennisFixture } from './tennis-matchday.mjs';
import type { TournamentReturnsSummary, ReturnCounts, SideReturn } from '../app/tennis-matchday/TournamentReturns';
export type ReturnProjection = {byTournament:Record<string,TournamentReturnsSummary>;examples:TournamentReturnsSummary[]};
export function reconciles(c:ReturnCounts,f:SideReturn|null,u:SideReturn|null):boolean;
export function summaryForFamily(data:unknown,family:unknown):TournamentReturnsSummary;
export function familyForFixture(data:unknown,fixture:TennisFixture):unknown;
export function projectTournamentReturns(data:unknown,fixtures:TennisFixture[]):ReturnProjection;
