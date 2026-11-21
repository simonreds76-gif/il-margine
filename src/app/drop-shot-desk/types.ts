export type Circuit = "ATP" | "WTA";
export function inCircuit(tour: string, circuit: Circuit) {
  return circuit === "WTA" ? tour === "WTA" || tour === "WTA 125" : tour === "ATP" || tour === "Challenger";
}
export type Quote = { time: string; price: number; other?: number; gap?: boolean };
export type Move = {
  fixtureRef?: string; market?:string; fixtureLabel?:string; profit?:number;
  activeUntil?: string; batchId?: string; batchAt?: string; alertedAt?: string;
  tour: string; league: string; player: string; opponent: string; start: string;
  before: string; after: string; old: number; new: number; quotes: Quote[];
  result: string; score?: string; notified: boolean; fourPointAlert?: boolean; chartSummary?: boolean; qualifying?: boolean;
};
export type Fixture = { activeUntil?: string; tour: string; league: string; home: string; away: string; start: string; homePrice?: number; awayPrice?: number };
