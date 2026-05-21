import { MetadataRoute } from "next";
import { BASE_URL, FAIR_ODDS_INDEXABLE } from "@/lib/config";
import { RESOURCES } from "@/lib/resources";
import { readAllClubPenaltyTeams } from "@/lib/club-penalty-takers";
import { readWorldCupData, worldCupTeamUrl, WORLD_CUP_PENALTIES_URL } from "@/lib/world-cup-penalties";

const STATIC_LAST_MODIFIED = new Date("2026-05-12T00:00:00Z");

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const worldCupData = await readWorldCupData().catch(() => null);
  const worldCupLastModified = worldCupData?.last_verified
    ? new Date(`${worldCupData.last_verified}T12:00:00Z`)
    : STATIC_LAST_MODIFIED;
  const clubPenaltyTeams = await readAllClubPenaltyTeams().catch(() => []);

  const entries: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 1 },
    { url: `${BASE_URL}/tennis-tips`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.9 },
    { url: `${BASE_URL}/player-props`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.9 },
    { url: `${BASE_URL}/player-props/world-cup-2026`, lastModified: worldCupLastModified, changeFrequency: "weekly", priority: 0.82 },
    { url: `${BASE_URL}/track-record`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE_URL}/fair-odds-lab`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/anytime-goalscorer`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE_URL}/penalty-takers`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "weekly", priority: 0.8 },
    ...clubPenaltyTeams.map((team) => ({
      url: team.absoluteUrl,
      lastModified: team.lastUpdated ? new Date(`${team.lastUpdated}T12:00:00Z`) : STATIC_LAST_MODIFIED,
      changeFrequency: "weekly" as const,
      priority: 0.62,
    })),
    ...(worldCupData
      ? [
          { url: WORLD_CUP_PENALTIES_URL, lastModified: worldCupLastModified, changeFrequency: "weekly" as const, priority: 0.9 },
          ...worldCupData.teams.map((team) => ({
            url: worldCupTeamUrl(team.team),
            lastModified: worldCupLastModified,
            changeFrequency: "weekly" as const,
            priority: 0.65,
          })),
        ]
      : []),
    { url: `${BASE_URL}/resources`, lastModified: STATIC_LAST_MODIFIED, changeFrequency: "monthly", priority: 0.7 },
    ...RESOURCES.filter((resource) => resource.href.startsWith("/resources/")).map((resource) => ({
      url: `${BASE_URL}${resource.href}`,
      lastModified: STATIC_LAST_MODIFIED,
      changeFrequency: "monthly" as const,
      priority: 0.75,
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
