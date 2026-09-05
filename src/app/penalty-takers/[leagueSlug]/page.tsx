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
    <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-white shadow-[0_8px_24px_rgba(0,0,0,0.22)]">
      {team.logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={team.logoPath} alt={`${team.team} crest`} className="h-7 w-7 object-contain" />
      ) : (
        <span className="font-mono text-xs font-bold text-slate-700">{team.initials}</span>
      )}
    </span>
  );
}

function TeamCard({ team }: { team: ClubPenaltyTeam }) {
  const cardId = `club-${team.slug}`;
  const needsContext = team.hierarchyStatus === "conditional"
    || team.hierarchyStatus === "disputed"
    || team.hierarchyStatus === "unknown"
    || team.hierarchyDepth < 3
    || team.weakEvidence;
  const context = needsContext ? buildClubPenaltyCardSummary(team) : "";
  const changedCopy = team.isCarryover
    ? `Carryover from ${CLUB_PENALTY_PREVIOUS_SEASON}`
    : team.lastUpdatedLabel
      ? team.lastUpdated === team.checkedAt
        ? "Order updated in this review"
        : `Order unchanged since ${team.lastUpdatedLabel}`
      : "Order change awaiting direct evidence";

  return (
    <article
      id={cardId}
      tabIndex={-1}
      aria-labelledby={`${cardId}-title`}
      className="group relative flex h-full scroll-mt-24 flex-col overflow-hidden rounded-3xl border border-slate-800/90 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.08),transparent_42%),#10151f] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.28)] transition duration-300 target:border-emerald-400/60 target:ring-2 target:ring-emerald-400/20 hover:border-emerald-400/35 hover:shadow-[0_22px_58px_rgba(0,0,0,0.34)] focus:outline-none focus-visible:border-emerald-300 focus-visible:ring-2 focus-visible:ring-emerald-400/30 motion-safe:hover:-translate-y-0.5 sm:p-5"
    >
      <div className="pointer-events-none absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-emerald-300/70 to-transparent opacity-75" />
      <header className="flex items-start gap-3">
        <TeamCrest team={team} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id={`${cardId}-title`} className="min-w-0 flex-1 text-base font-semibold text-slate-100 sm:text-lg">{team.team}</h3>
          </div>
        </div>
      </header>

      <ol aria-label={`${team.team} penalty hierarchy`} className="mt-4 space-y-2">
        <li className="flex min-w-0 items-center gap-3 rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.07] px-3.5 py-3">
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-300 font-mono text-sm font-bold text-slate-950">1</span>
          <div className="min-w-0">
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-emerald-300/80">First choice</span>
            <strong title={team.primary || "Open position"} className="mt-0.5 block break-words text-xl font-semibold leading-tight text-emerald-100 sm:text-2xl">
              {team.primary || "Open position"}
            </strong>
          </div>
        </li>
        <li className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {[["2", "Second choice", team.secondary], ["3", "Third choice", team.tertiary]].map(([rank, label, value]) => (
            <div key={rank} className="flex min-w-0 items-center gap-2.5 rounded-xl border border-slate-700/75 bg-slate-950/60 px-3 py-2.5">
              <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-600/80 bg-slate-900 font-mono text-[10px] font-bold text-slate-300">{rank}</span>
              <div className="min-w-0">
                <span className="font-mono text-[8px] uppercase tracking-[0.13em] text-slate-500">{label}</span>
                <strong title={value || "Open position"} className="mt-0.5 block break-words text-sm font-semibold leading-5 text-slate-100">{value || "Open position"}</strong>
              </div>
            </div>
          ))}
        </li>
      </ol>

      {context ? <p className="mt-3 line-clamp-2 min-h-10 text-xs leading-5 text-slate-300">{context}</p> : <div className="min-h-3 flex-1" />}

      <footer className="mt-auto border-t border-slate-800/90 pt-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="text-[11px] leading-5">
            <div className="font-semibold text-emerald-200">
              Checked{" "}
              {team.checkedAt ? <time dateTime={team.checkedAt}>{team.checkedLabel}</time> : "pending"}
            </div>
            <div className="text-slate-400">{changedCopy}</div>
          </div>
          <Link href={team.relativeUrl} className="inline-flex shrink-0 items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/8 px-3 py-1.5 text-xs font-semibold text-emerald-200 transition hover:border-emerald-300/45 hover:bg-emerald-400/12 hover:text-emerald-100">
            Evidence file <span aria-hidden="true">-&gt;</span>
          </Link>
        </div>
      </footer>
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
  const fullHierarchyCount = league.teams.filter((team) => team.hierarchyDepth === 3).length;
  const openCallCount = league.teams.filter((team) => team.hierarchyStatus === "conditional" || team.hierarchyStatus === "disputed" || team.hierarchyStatus === "unknown").length;
  const confirmedCount = league.teams.filter((team) => team.hierarchyStatus === "confirmed" || team.hierarchyStatus === "probable").length;
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
          <div className="relative overflow-hidden rounded-[30px] border border-emerald-400/20 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_40%),linear-gradient(145deg,#0c1514,#0b0f17_68%)] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.3)] sm:p-7">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-300/70 to-transparent" />
            <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white shadow-[0_12px_30px_rgba(0,0,0,0.3)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={league.logoPath} alt={`${league.label} logo`} className="h-11 w-11 object-contain" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-300">{CLUB_PENALTY_SEASON} live hierarchy board</div>
                <h1 className="mt-1.5 text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">{league.label} penalty takers</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">First choice, deputies and current evidence status for every club.</p>
              </div>
              <Link href="#league-board" className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-full border border-emerald-300/30 bg-emerald-300 px-4 py-2 text-sm font-bold text-slate-950 transition hover:bg-emerald-200">
                View all {league.teams.length} clubs <span aria-hidden="true" className="ml-2">&darr;</span>
              </Link>
            </div>
          </div>
        </section>

        <section aria-label={`${league.label} board status`} className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["Current clubs", String(league.teams.length)],
            ["Filed orders", String(fullHierarchyCount)],
            ["Stable / probable", String(confirmedCount)],
            ["Under review", String(openCallCount)],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-800 bg-slate-950/65 px-4 py-3">
              <div className="font-mono text-[8px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-slate-100">{value}</div>
            </div>
          ))}
        </section>

        <ClubPenaltyTeamFinder
          leagueLabel={league.label}
          teams={league.teams.map((team) => ({ name: team.team, slug: team.slug, logoPath: team.logoPath, initials: team.initials }))}
        />

        <section id="league-board" className="scroll-mt-24 mt-8">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">Penalty order ledger</div>
              <h2 className="mt-2 text-2xl font-semibold text-slate-100">All {league.teams.length} clubs</h2>
            </div>
            <div className="rounded-full border border-emerald-400/20 bg-emerald-400/8 px-3 py-2 text-xs text-slate-300">
              <span className="text-slate-500">Board checked</span>{" "}
              <strong className="text-emerald-200">{league.boardCheckedLabel || "pending"}</strong>
            </div>
          </div>
          <div className="grid items-stretch gap-4 lg:grid-cols-2">{league.teams.map((team) => <TeamCard key={team.relativeUrl} team={team} />)}</div>
          <p className="mt-4 text-xs leading-5 text-slate-500">Checked dates record the latest board review. Order dates change only when evidence changes the filed hierarchy.</p>
        </section>

        <div className="mt-12">
          <ClubPenaltyLatestUpdates
            items={latestNews}
            eyebrow={`${league.label} live evidence`}
            description={`The latest competitive penalty events reviewed for ${league.label}, linked to each club's current order and evidence file.`}
          />
        </div>

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
