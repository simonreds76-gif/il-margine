export type Quote = { time: string; price: number; other: number; gap?: boolean };
export type Move = {
  tour: string; league: string; player: string; opponent: string; start: string;
  before: string; after: string; old: number; new: number; quotes: Quote[];
  result: string; score?: string; notified: boolean; qualifying?: boolean;
};
export type Fixture = { tour: string; league: string; home: string; away: string; start: string; homePrice: number; awayPrice: number };
