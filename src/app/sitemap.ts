import { MetadataRoute } from "next";
import { BASE_URL, FAIR_ODDS_INDEXABLE } from "@/lib/config";
import { RESOURCES } from "@/lib/resources";
import {
  CLUB_LEAGUES,
  clubPenaltyLeagueUrl,
  getClubPenaltySeason,
  readAllClubPenaltyTeams,
  readClubPenaltyData,
} from "@/lib/club-penalty-takers";
import { readWorldCupData, worldCupTeamUrl, WORLD_CUP_ARCHIVE_DATE, WORLD_CUP_PENALTIES_URL } from "@/lib/world-cup-penalties";
import { fetchSeoTipSitemapState } from "@/lib/tip-seo-server";

const STATIC_LAST_MODIFIED = new Date("2026-05-12T00:00:00Z");
const RESOURCES_LAST_MODIFIED = new Date("2026-08-21T12:00:00Z");
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const worldCupData = await readWorldCupData().catch(() => null);
  const worldCupLastModified = new Date(`${WORLD_CUP_ARCHIVE_DATE}T12:00:00Z`);
  const [clubPenaltyTeams, clubPenaltyLeagues, tipSeoState] = await Promise.all([
    readAllClubPenaltyTeams().catch(() => []),
    readClubPenaltyData().catch(() => []),
    fetchSeoTipSitemapState(),
  ]);
  const clubPenaltySeason = getClubPenaltySeason();
  const clubPenaltyLastModified = new Date(`${clubPenaltySeason.published_at}T12:00:00Z`);

  const entries: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 1 },
    {
      url: `${BASE_URL}/tennis-tips`,
      lastModified: tipSeoState.latestByMarket.tennis ?? STATIC_LAST_MODIFIED,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/player-props`,
      lastModified: tipSeoState.latestByMarket.props ?? STATIC_LAST_MODIFIED,
      changeFrequency: "daily",
      priority: 0.9,
    },
    ...tipSeoState.previews.map((preview) => ({
      url: `${BASE_URL}${preview.url}`,
      lastModified: preview.lastModified,
      changeFrequency: "daily" as const,
      priority: 0.72,
    })),
    { url: `${BASE_URL}/track-record`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE_URL}/bookmakers`, lastModified: new Date("2026-08-31T12:00:00Z"), changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE_URL}/fair-odds-lab`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/anytime-goalscorer`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/penalty-takers`, lastModified: clubPenaltyLastModified, changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE_URL}/penalty-takers/methodology`, lastModified: clubPenaltyLastModified, changeFrequency: "monthly", priority: 0.5 },
    { url: `${BASE_URL}/world-cup-2026-free-picks`, lastModified: new Date("2026-07-20T12:00:00Z"), changeFrequency: "monthly", priority: 0.85 },
    ...CLUB_LEAGUES.map((leagueConfig) => {
      const league = clubPenaltyLeagues.find((candidate) => candidate.key === leagueConfig.key);
      return {
        url: clubPenaltyLeagueUrl(leagueConfig.key),
        lastModified: league?.publicUpdatedAt ? new Date(`${league.publicUpdatedAt}T12:00:00Z`) : clubPenaltyLastModified,
        changeFrequency: "weekly" as const,
        priority: 0.78,
      };
    }),
    ...clubPenaltyTeams.map((team) => ({
      url: team.absoluteUrl,
      lastModified: team.publicUpdatedAt ? new Date(`${team.publicUpdatedAt}T12:00:00Z`) : clubPenaltyLastModified,
      changeFrequency: team.isArchived ? "monthly" as const : "weekly" as const,
      priority: team.isArchived ? 0.45 : 0.62,
    })),
    ...(worldCupData
      ? [
          { url: WORLD_CUP_PENALTIES_URL, lastModified: worldCupLastModified, changeFrequency: "yearly" as const, priority: 0.9 },
          ...worldCupData.teams.map((team) => ({
            url: worldCupTeamUrl(team.team),
            lastModified: worldCupLastModified,
            changeFrequency: "yearly" as const,
            priority: 0.65,
          })),
        ]
      : []),
    { url: `${BASE_URL}/resources`, lastModified: RESOURCES_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.75 },
    ...RESOURCES.filter((resource) => resource.href.startsWith("/resources/")).map((resource) => ({
      url: `${BASE_URL}${resource.href}`,
      lastModified: resource.dateModified
        ? new Date(`${resource.dateModified}T12:00:00Z`)
        : resource.datePublished
          ? new Date(`${resource.datePublished}T12:00:00Z`)
          : STATIC_LAST_MODIFIED,
      changeFrequency: "monthly" as const,
      priority: resource.surface === "guide" ? 0.78 : 0.7,
    })),
    { url: `${BASE_URL}/calculator`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.6 },
    ...(FAIR_ODDS_INDEXABLE
      ? [{ url: `${BASE_URL}/fair-odds`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily" as const, priority: 0.8 }]
      : []),
    { url: `${BASE_URL}/the-edge`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.8 },
    { url: `${BASE_URL}/faq`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.7 },
    { url: `${BASE_URL}/contact`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "yearly", priority: 0.5 },
    { url: `${BASE_URL}/llms.txt`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.4 },
    { url: `${BASE_URL}/llms-full.txt`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.3 },
    { url: `${BASE_URL}/disclaimer`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "yearly", priority: 0.3 },
    { url: `${BASE_URL}/privacy-policy`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "yearly", priority: 0.3 },
    { url: `${BASE_URL}/cookies-policy`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "yearly", priority: 0.3 },
  ];

  return entries;
}
