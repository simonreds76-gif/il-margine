import type { TennisFixture } from './tennis-matchday.mjs';
export type BrowseState = { view: string; resultDay: string; filter: string; tour: string; tournament: string; search: string; qualifying: boolean; order: string };
export type Tournament = { key:string; label:string; displayName:string; tour:string; round:string; surface:string };
export function tournamentOf(f:TennisFixture):Tournament;
export function isQualifying(f:TennisFixture):boolean;
export const surfaceNames:Record<string,string>;
export function readBrowseState(search:string):BrowseState;
export function browseQuery(state:BrowseState,search?:string):string;

export function displayDay(filter:string, fixtures:TennisFixture[], now:Date):string;
