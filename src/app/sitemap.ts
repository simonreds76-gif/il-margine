import { MetadataRoute } from 'next';
import { BASE_URL, BOOKMAKERS_INDEXABLE, FAIR_ODDS_INDEXABLE } from '@/lib/config';
import { readWorldCupData, worldCupTeamUrl, WORLD_CUP_PENALTIES_URL } from '@/lib/world-cup-penalties';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const worldCupData = await readWorldCupData().catch(() => null);
  const worldCupLastModified = worldCupData?.last_verified
    ? new Date(`${worldCupData.last_verified}T12:00:00Z`)
    : new Date();
  const showFairOddsLabPage =
    process.env.NODE_ENV !== 'production' ||
    process.env.GOALSCORER_PAGE_PUBLIC === '1' ||
    process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === '1';
  const entries: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${BASE_URL}/tennis-tips`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/player-props`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/penalty-takers`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.85,
    },
    ...(worldCupData
      ? [
          {
            url: WORLD_CUP_PENALTIES_URL,
            lastModified: worldCupLastModified,
            changeFrequency: 'weekly' as const,
            priority: 0.9,
          },
          ...worldCupData.teams.map((team) => ({
            url: worldCupTeamUrl(team.team),
            lastModified: worldCupLastModified,
            changeFrequency: 'weekly' as const,
            priority: 0.65,
          })),
        ]
      : []),
    ...(showFairOddsLabPage
      ? [{
          url: `${BASE_URL}/fair-odds-lab`,
          lastModified: new Date(),
          changeFrequency: 'weekly' as const,
          priority: 0.8,
        }]
      : []),
    {
      url: `${BASE_URL}/bet-builders`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.8,
    },
    ...(BOOKMAKERS_INDEXABLE
      ? [{
          url: `${BASE_URL}/bookmakers`,
          lastModified: new Date(),
          changeFrequency: 'monthly' as const,
          priority: 0.7,
        }]
      : []),
    {
      url: `${BASE_URL}/calculator`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    ...(FAIR_ODDS_INDEXABLE
      ? [{
          url: `${BASE_URL}/fair-odds`,
          lastModified: new Date(),
          changeFrequency: 'daily' as const,
          priority: 0.8,
        }]
      : []),
    {
      url: `${BASE_URL}/the-edge`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/track-record`,
      lastModified: new Date(),
      changeFrequency: 'daily' as const,
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/disclaimer`,
      lastModified: new Date(),
      changeFrequency: 'yearly',
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/privacy-policy`,
      lastModified: new Date(),
      changeFrequency: 'yearly',
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/cookies-policy`,
      lastModified: new Date(),
      changeFrequency: 'yearly',
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/contact`,
      lastModified: new Date(),
      changeFrequency: 'yearly',
      priority: 0.5,
    },
    {
      url: `${BASE_URL}/llms.txt`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.4,
    },
    {
      url: `${BASE_URL}/llms-full.txt`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/faq`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/atp-tennis`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.6,
    },
    {
      url: `${BASE_URL}/resources`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/resources/closing-line-value`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/resources/kelly-criterion-sports-betting`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/resources/roger`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.85,
    },
  ];

  return entries;
}
