import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
import ClubPenaltyLatestUpdates from "@/components/ClubPenaltyLatestUpdates";
import ClubPenaltyTeamFinder from "@/components/ClubPenaltyTeamFinder";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import {
  CLUB_LEAGUES,
  CLUB_PENALTY_PREVIOUS_SEASON,
  CLUB_PENALTY_SEASON,
  buildClubPenaltyCardSummary,
  clubPenaltyLeagueUrl,
  getClubPenaltyLeague,
  getLatestClubPenaltyNews,
  type ClubPenaltyTeam,
} from "@/lib/club-penalty-takers";

export const revalidate = 43200;

type PageProps = { params: Promise<{ leagueSlug: string }> };

const STATUS_LABELS: Record<ClubPenaltyTeam["hierarchyStatus"], string> = {
  confirmed: "Confirmed",
  probable: "Probable",
  conditional: "Conditional",
  disputed: "Disputed",
  unknown: "Not verified",
};

const STATUS_STYLES: Record<ClubPenaltyTeam["hierarchyStatus"], string> = {
  confirmed: "border-emerald-300/30 bg-emerald-400/12 text-emerald-100",
  probable: "border-cyan-300/30 bg-cyan-400/10 text-cyan-100",
  conditional: "border-amber-300/30 bg-amber-400/10 text-amber-100",
  disputed: "border-rose-300/30 bg-rose-400/10 text-rose-100",
  unknown: "border-slate-500/50 bg-slate-700/30 text-slate-200",
};

export function generateStaticParams() {
  return CLUB_LEAGUES.map((league) => ({ leagueSlug: league.key }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { leagueSlug } = await params;
  const league = await getClubPenaltyLeague(leagueSlug);
  if (!league) return { title: "League penalty takers" };

  const title = `${league.label} Penalty Takers ${CLUB_PENALTY_SEASON}: Every Club's Order`;
  const description = `${league.label} penalty takers for ${CLUB_PENALTY_SEASON}: first choice, backups, confidence and verification status for every current club.`;
  const url = clubPenaltyLeagueUrl(league.key);
  return {
    title,
    description,
    alternates: { canonical: url },
    keywords: [
      `${league.label.toLowerCase()} penalty takers ${CLUB_PENALTY_SEASON}`,
      `${league.label.toLowerCase()} penalty taker list`,
      `who takes penalties in the ${league.label.toLowerCase()}`,
    ],
    openGraph: {
      type: "website",
      url,
      title: `${title} | Il Margine`,
      description,
      siteName: "Il Margine",
      images: [{ url: `${BASE_URL}/penalty-takers/opengraph-image`, width: 1200, height: 630, alt: `${league.label} penalty takers ${CLUB_PENALTY_SEASON}` }],
    },
    twitter: { card: "summary_large_image", title: `${title} | Il Margine`, description, images: [`${BASE_URL}/penalty-takers/opengraph-image`] },
    robots: { index: true, follow: true },
  };
}

function TeamCrest({ team }: { team: ClubPenaltyTeam }) {
  return (
    <span className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-slate-700/80 bg-white shadow-[0_8px_24px_rgba(0,0,0,0.2)]">
      {team.logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={team.logoPath} alt={`${team.team} crest`} className="h-8 w-8 object-contain" />
      ) : (
        <span className="font-mono text-xs font-bold text-slate-700">{team.initials}</span>
      )}
    </span>
  );
}

function TeamCard({ team }: { team: ClubPenaltyTeam }) {
  const unknown = team.hierarchyStatus === "unknown";
  const cardId = `club-${team.slug}`;
  return (
    <article
      id={cardId}
      tabIndex={-1}
      aria-labelledby={`${cardId}-title`}
      className="group relative scroll-mt-24 overflow-hidden rounded-3xl border border-slate-700/70 bg-[linear-gradient(145deg,rgba(15,23,42,0.94),rgba(7,12,22,0.98))] p-4 shadow-[0_18px_42px_rgba(0,0,0,0.24)] transition duration-300 target:border-emerald-400/60 target:ring-2 target:ring-emerald-400/20 hover:-translate-y-0.5 hover:border-emerald-400/30 hover:shadow-[0_22px_55px_rgba(0,0,0,0.32)] focus:outline-none focus-visible:border-emerald-300 focus-visible:ring-2 focus-visible:ring-emerald-400/30 sm:p-5"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-300/45 to-transparent opacity-60 transition group-hover:opacity-100" />
      <div className="flex items-start gap-3">
        <TeamCrest team={team} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id={`${cardId}-title`} className="text-lg font-semibold text-slate-100">{team.team}</h2>
            <span className={`rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.15em] ${STATUS_STYLES[team.hierarchyStatus]}`}>
              {STATUS_LABELS[team.hierarchyStatus]}
            </span>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{buildClubPenaltyCardSummary(team)}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {[["First choice", team.primary], ["Second choice", team.secondary], ["Third choice", team.tertiary || "Under review"]].map(([label, value], index) => (
          <div key={label} className="min-w-0 rounded-xl border border-slate-700/70 bg-slate-950/65 px-3 py-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-slate-400">{index + 1}. {label}</div>
            <div title={value} className={`mt-1.5 break-words text-sm font-semibold leading-5 ${index === 0 && !unknown ? "text-emerald-200" : "text-slate-100"}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-3 border-t border-slate-700/60 pt-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs leading-5">
          <span className="text-slate-300">
            <span className="text-slate-500">Evidence verified</span>{" "}
            {team.isCarryover ? CLUB_PENALTY_PREVIOUS_SEASON : team.lastUpdatedLabel || "Awaiting direct evidence"}
          </span>
          <span className="text-emerald-200">
            <span className="text-slate-500">League review run</span>{" "}
            {team.leagueCheckedLabel || "Pending"}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <a href="#club-finder" className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 transition hover:text-slate-200">
            Find another club <span aria-hidden="true">&uarr;</span>
          </a>
          <Link href={team.relativeUrl} className="inline-flex shrink-0 items-center gap-2 text-sm font-semibold text-emerald-300 transition group-hover:text-emerald-200">
            Full evidence <span aria-hidden="true">-&gt;</span>
          </Link>
        </div>
      </div>
    </article>
  );
}

export default async function ClubPenaltyLeaguePage({ params }: PageProps) {
  const { leagueSlug } = await params;
  const league = await getClubPenaltyLeague(leagueSlug);
  if (!league) notFound();

  const url = clubPenaltyLeagueUrl(league.key);
  const title = `${league.label} Penalty Takers ${CLUB_PENALTY_SEASON}`;
  const latestNews = getLatestClubPenaltyNews([league], 6);
  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Penalty Takers", item: `${BASE_URL}/penalty-takers` },
      { "@type": "ListItem", position: 3, name: league.label, item: url },
    ],
  };
  const collectionData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: title,
    url,
    dateModified: league.publicUpdatedAt,
    mainEntity: {
      "@type": "ItemList",
      numberOfItems: league.teams.length,
      itemListElement: league.teams.map((team, index) => ({ "@type": "ListItem", position: index + 1, name: `${team.team} penalty taker`, url: team.absoluteUrl })),
    },
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionData) }} />
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6 pb-10">
          <PageHomeLink className="mb-7" />
          <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-400">
            <Link href="/penalty-takers" className="hover:text-slate-100">Penalty Takers</Link><span>/</span><span className="text-slate-200">{league.label}</span>
          </div>
          <div className={`relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-gradient-to-br ${league.surface} p-6 sm:p-9`}>
            <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
              <span className="flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={league.logoPath} alt={`${league.label} logo`} className="h-14 w-14 object-contain" />
              </span>
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.25em] text-emerald-300">{CLUB_PENALTY_SEASON} penalty intelligence</div>
                <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-100 sm:text-5xl">{league.label} penalty takers</h1>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">{league.copy}</p>
              </div>
            </div>
          </div>
        </section>

        <ClubPenaltyTeamFinder
          leagueLabel={league.label}
          teams={league.teams.map((team) => ({ name: team.team, slug: team.slug, logoPath: team.logoPath, initials: team.initials }))}
        />

        <div className="mt-8">
          <ClubPenaltyLatestUpdates
            items={latestNews}
            eyebrow={`${league.label} live evidence`}
            description={`The latest competitive penalty events reviewed for ${league.label}, linked to each club's current order and evidence file.`}
          />
        </div>

        <section className="mt-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">Current league</div>
              <h2 className="mt-2 text-2xl font-semibold text-slate-100">All {league.teams.length} clubs</h2>
            </div>
            <div className="max-w-xl rounded-2xl border border-emerald-400/20 bg-emerald-400/8 px-4 py-3 text-xs leading-5 text-slate-300">
              <span className="font-semibold text-emerald-200">Board checked {league.boardCheckedLabel || "pending"}.</span>{" "}
              Evidence dates change only when a hierarchy receives new supporting information.
            </div>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">{league.teams.map((team) => <TeamCard key={team.relativeUrl} team={team} />)}</div>
        </section>

        {league.archivedTeams.length ? (
          <section className="mt-10 rounded-3xl border border-slate-800 bg-slate-900/45 p-5 sm:p-6">
            <div className="font-mono text-xs uppercase tracking-[0.22em] text-slate-500">Archived {league.archivedTeams[0].seasonLabel}</div>
            <h2 className="mt-2 text-xl font-semibold text-slate-100">Relegated club records</h2>
            <p className="mt-2 text-sm text-slate-400">Kept accessible for search continuity and historical reference; these are not current {league.label} calls.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {league.archivedTeams.map((team) => <Link key={team.relativeUrl} href={team.relativeUrl} className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100">{team.team} archive</Link>)}
            </div>
          </section>
        ) : null}

        <nav aria-label="Other penalty taker leagues" className="mt-10 flex flex-wrap gap-2">
          <Link href="/penalty-takers/methodology" className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-100">How we verify penalty takers</Link>
          {CLUB_LEAGUES.filter((item) => item.key !== league.key).map((item) => <Link key={item.key} href={`/penalty-takers/${item.key}`} className="rounded-full border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300 hover:border-emerald-400/30 hover:text-emerald-200">{item.label}</Link>)}
          <Link href="/penalty-takers/world-cup-2026" className="rounded-full border border-amber-300/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">World Cup 2026 archive</Link>
        </nav>
      </main>
      <Footer />
    </div>
  );
}
