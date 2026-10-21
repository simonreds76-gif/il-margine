import news from "@/data/penalty-news.json";

export type PenaltyArticle = {
  id: string; slug: string; matchId: string; eventId: string; date: string; kickoff: string;
  league: string; leagueLabel: string; round: string; player: string; playerId: number;
  portrait: string; club: string; clubSlug: string; clubUrl: string; crest: string; opponent: string;
  home: string; away: string; homeScore: number; awayScore: number; minute: string;
  outcome: string; title: string; sentences: string[]; cause: string | null;
  paragraphs: string[];
  incident: { type: string; wonBy: string | null; concededBy: string; sentence: string; evidenceIds: string[]; method: string } | null;
  stats: { minutes: number | null; goals: number | null; shots: number | null; onTarget: number | null; chances: number | null };
  keeper: string | null; moment: { before: number[]; after: number[] } | null;
  sourceUrl: string; sourceHash: string; publishedAt: string; updatedAt: string;
};
export const penaltyNews = news as { schemaVersion: number; generatedAt: string; coverageStart: string; checkedThrough: string; matchesChecked: number; articles: PenaltyArticle[] };
export const newsLeagues = [
  { key: "epl", label: "Premier League" }, { key: "serie-a", label: "Serie A" },
  { key: "la-liga", label: "La Liga" }, { key: "bundesliga", label: "Bundesliga" }, { key: "ligue-1", label: "Ligue 1" },
];
export const outcomeLabel: Record<string, string> = { scored: "Scored", saved: "Saved", missed: "Missed", woodwork: "Woodwork" };
export function newsDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
}
