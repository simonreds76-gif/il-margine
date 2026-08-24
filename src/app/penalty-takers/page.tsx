import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";
import {
  CLUB_PENALTY_SEASON,
  clubPenaltyLeagueUrl,
  getClubPenaltySeason,
  getLatestClubPenaltyNews,
  readClubPenaltyData,
} from "@/lib/club-penalty-takers";
import PenaltyTakersClient from "./PenaltyTakersClient";

const PAGE_TITLE = `Penalty Takers ${CLUB_PENALTY_SEASON}: Premier League, Serie A, La Liga, Bundesliga & Ligue 1`;
const PAGE_DESCRIPTION =
  `Penalty takers ${CLUB_PENALTY_SEASON} across Europe's top five leagues. Current first-choice and backup orders, transparent evidence status and dedicated club pages.`;
const PAGE_URL = `${BASE_URL}/penalty-takers`;

export const revalidate = 43200;

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: PAGE_URL },
  keywords: [
    `penalty takers ${CLUB_PENALTY_SEASON}`,
    "premier league penalty takers",
    "serie a penalty takers",
    "la liga penalty takers",
    "bundesliga penalty takers",
    "ligue 1 penalty takers",
    "who takes penalties",
  ],
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    siteName: "Il Margine",
    images: [{ url: `${BASE_URL}/penalty-takers/opengraph-image`, width: 1200, height: 630, alt: `Penalty Takers ${CLUB_PENALTY_SEASON} | Il Margine` }],
  },
  twitter: {
    card: "summary_large_image",
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    images: [`${BASE_URL}/penalty-takers/opengraph-image`],
  },
  robots: { index: true, follow: true },
};

export default async function PenaltyTakersPage() {
  const [leagues, season] = await Promise.all([readClubPenaltyData(), Promise.resolve(getClubPenaltySeason())]);
  const totalTeams = leagues.reduce((sum, league) => sum + league.teams.length, 0);
  const latestUpdate = leagues.map((league) => league.publicUpdatedAt).sort().at(-1) ?? season.published_at;
  const latestNews = getLatestClubPenaltyNews(leagues, 6);

  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: `Penalty Takers ${CLUB_PENALTY_SEASON}`, item: PAGE_URL },
    ],
  };
  const collectionData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    url: PAGE_URL,
    inLanguage: "en-GB",
    dateModified: latestUpdate,
    hasPart: leagues.map((league) => ({ "@type": "CollectionPage", name: `${league.label} penalty takers`, url: clubPenaltyLeagueUrl(league.key) })),
  };
  const itemListData = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `${CLUB_PENALTY_SEASON} penalty takers by league`,
    numberOfItems: leagues.length,
    itemListElement: leagues.map((league, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: clubPenaltyLeagueUrl(league.key),
      name: `${league.label} penalty takers ${CLUB_PENALTY_SEASON}`,
      description: `${league.teams.length} current clubs tracked in ${league.label}.`,
    })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListData) }} />
      <PenaltyTakersClient leagues={leagues} totalTeams={totalTeams} season={season} latestNews={latestNews} />
    </>
  );
}
