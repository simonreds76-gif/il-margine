export type PenaltyArticle = {
  id: string; slug: string; matchId: string; eventId: string; date: string; kickoff: string;
  league: string; leagueLabel: string; round: string; player: string; playerId: number;
  portrait: string; club: string; clubSlug: string; clubUrl: string; crest: string; opponent: string;
  home: string; away: string; homeScore: number; awayScore: number; minute: string;
  outcome: string; title: string; sentences: string[]; cause: string | null;
  paragraphs: string[];
  stats: { minutes: number | null; goals: number | null; shots: number | null; onTarget: number | null; chances: number | null };
  keeper: string | null; moment: { before: number[]; after: number[] } | null;
  publishedAt: string; updatedAt: string;
};
export const newsLeagues = [
  { key: "epl", label: "Premier League" }, { key: "serie-a", label: "Serie A" },
  { key: "la-liga", label: "La Liga" }, { key: "bundesliga", label: "Bundesliga" }, { key: "ligue-1", label: "Ligue 1" },
];
export const outcomeLabel: Record<string, string> = { scored: "Scored", saved: "Saved", missed: "Missed", woodwork: "Woodwork" };
export const NEWS_PAGE_SIZE = 12;
export function newsPagePath(page: number) {
  return page <= 1 ? "/penalty-news" : `/penalty-news/page/${page}`;
}
export function newsImageUrl(slug = "index") {
  return `https://ilmargine.bet/penalty-news/share/${slug}`;
}
// Presentation only: preserve the saved report, incident IDs and publication dates.
export function distinctNewsTitle(article: PenaltyArticle, articles: PenaltyArticle[]) {
  const repeated = articles.filter(a => a.matchId === article.matchId && a.title === article.title);
  if (repeated.length < 2) return article.title;
  if (/^\d+(?:\+\d+)?$/.test(article.minute) && repeated.filter(a => a.minute === article.minute).length === 1) {
    return `${article.title} (${article.minute}′ penalty)`;
  }
  // Ordinals are only used for the known incidents, never inferred from a hierarchy.
  const ordered = [...repeated].sort((a, b) => a.eventId.localeCompare(b.eventId, "en", { numeric: true }));
  return `${article.title} (report ${ordered.findIndex(a => a.id === article.id) + 1})`;
}
export function newsDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
}
