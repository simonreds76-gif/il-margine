import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import {
  CONFEDERATION_ORDER,
  WORLD_CUP_PENALTIES_URL,
  readWorldCupData,
  worldCupTeamSlug,
  worldCupTeamUrl,
  flagImageUrl,
  initials,
} from "@/lib/world-cup-penalties";
import { BASE_URL } from "@/lib/config";

const PAGE_TITLE = "FIFA World Cup 2026 Penalty Takers";
const PAGE_DESCRIPTION =
  "World Cup 2026 penalty takers for every qualified team. Research-first calls, country-by-country pages, and the current lead penalty taker for Germany, France, Brazil, Japan, Curacao and the rest of the field.";

const HOSTS = ["Canada", "Mexico", "USA"];
const FEATURED_TEAMS = ["Germany", "France", "Brazil", "Argentina", "England", "Spain", "Japan", "Netherlands", "USA", "Mexico"];
const AT_GLANCE_TEAMS = [
  "Argentina",
  "Brazil",
  "England",
  "France",
  "Germany",
  "Spain",
  "Portugal",
  "Netherlands",
  "Belgium",
  "Croatia",
  "Japan",
  "Mexico",
  "USA",
  "Canada",
  "Morocco",
  "Egypt",
  "Korea Republic",
  "Senegal",
];

const CONFEDERATION_INTROS: Record<string, string> = {
  UEFA:
    "UEFA gives us the deepest evidence pool: qualifiers, Nations League and federation match reports usually make the first-choice order easier to verify.",
  CONMEBOL:
    "CONMEBOL often looks obvious on the headline sides, but the right answer still comes from actual in-match penalties, not reputation alone.",
  Concacaf:
    "Concacaf is the section where squad context matters most. Some countries are stable, others switch takers depending on availability and tournament squad strength.",
  AFC:
    "AFC needs a multilingual lens more than any other section here. Official reports exist, but the hierarchy often needs federation and local-language cross-checking.",
  CAF:
    "CAF is exactly where this kind of page can be useful. Official tournament and qualifier reports exist, but few places keep the hierarchy cleanly updated.",
  OFC:
    "OFC is small in team count, but the same rules apply: only real senior in-match penalty evidence moves a team out of research.",
};

const CONFEDERATION_STYLES: Record<
  string,
  { badge: string; panel: string; glow: string; primary: string; secondary: string; accent: string }
> = {
  UEFA: {
    badge: "border-sky-400/30 bg-sky-400/10 text-sky-200",
    panel: "from-sky-500/20 via-sky-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(56,189,248,0.08)]",
    primary: "text-sky-100",
    secondary: "text-sky-200",
    accent: "bg-sky-300",
  },
  CONMEBOL: {
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    panel: "from-emerald-500/20 via-emerald-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(16,185,129,0.08)]",
    primary: "text-emerald-100",
    secondary: "text-emerald-200",
    accent: "bg-emerald-300",
  },
  Concacaf: {
    badge: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
    panel: "from-cyan-500/20 via-cyan-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(34,211,238,0.08)]",
    primary: "text-cyan-100",
    secondary: "text-cyan-200",
    accent: "bg-cyan-300",
  },
  AFC: {
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    panel: "from-amber-500/20 via-amber-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(251,191,36,0.08)]",
    primary: "text-amber-50",
    secondary: "text-amber-200",
    accent: "bg-amber-300",
  },
  CAF: {
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    panel: "from-rose-500/20 via-rose-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(251,113,133,0.08)]",
    primary: "text-rose-100",
    secondary: "text-rose-200",
    accent: "bg-rose-300",
  },
  OFC: {
    badge: "border-violet-400/30 bg-violet-400/10 text-violet-200",
    panel: "from-violet-500/20 via-violet-400/8 to-slate-950",
    glow: "hover:shadow-[0_26px_70px_rgba(167,139,250,0.08)]",
    primary: "text-violet-100",
    secondary: "text-violet-200",
    accent: "bg-violet-300",
  },
};

export const metadata: Metadata = {
  title: `${PAGE_TITLE} | Il Margine`,
  description: PAGE_DESCRIPTION,
  alternates: {
    canonical: WORLD_CUP_PENALTIES_URL,
  },
  keywords: [
    "world cup 2026 penalty takers",
    "fifa world cup 2026 penalty takers",
    "germany penalty taker world cup 2026",
    "france penalty taker world cup 2026",
    "brazil penalty taker world cup 2026",
    "japan penalty taker world cup 2026",
    "curacao penalty taker world cup 2026",
  ],
  openGraph: {
    type: "website",
    url: WORLD_CUP_PENALTIES_URL,
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    siteName: "Il Margine",
    images: [
      {
        url: `${BASE_URL}/penalty-takers/world-cup-2026/opengraph-image`,
        width: 1200,
        height: 630,
        alt: "Il Margine World Cup 2026 penalty takers",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    images: [`${BASE_URL}/penalty-takers/world-cup-2026/opengraph-image`],
  },
  robots: {
    index: true,
    follow: true,
  },
};

function trimEvidence(value: string | undefined, limit = 88): string {
  if (!value) return "Fresh tournament-era evidence is still being added.";
  return value.length > limit ? `${value.slice(0, limit).trimEnd()}...` : value;
}

export default async function WorldCup2026PenaltyTakersPage() {
  const data = await readWorldCupData();
  const grouped = CONFEDERATION_ORDER.map((confederation) => ({
    confederation,
    intro: CONFEDERATION_INTROS[confederation] ?? "",
    teams: data.teams
      .filter((team) => team.confederation === confederation)
      .sort((left, right) => left.team.localeCompare(right.team, "en")),
  })).filter((group) => group.teams.length > 0);

  const namedChallengers = data.teams.filter((team) => team.likely_secondary?.trim()).length;
  const confederationCount = grouped.length;
  const featuredTeams = FEATURED_TEAMS.flatMap((name) => {
    const match = data.teams.find((team) => team.team === name);
    return match ? [match] : [];
  });
  const hostTeams = HOSTS.flatMap((name) => {
    const match = data.teams.find((team) => team.team === name);
    return match ? [match] : [];
  });
  const atGlanceTeams = AT_GLANCE_TEAMS.flatMap((name) => {
    const match = data.teams.find((team) => team.team === name);
    return match ? [match] : [];
  });
  const alphabeticalTeams = [...data.teams].sort((left, right) => left.team.localeCompare(right.team, "en"));

  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Penalty Takers", item: `${BASE_URL}/penalty-takers` },
      { "@type": "ListItem", position: 3, name: PAGE_TITLE, item: WORLD_CUP_PENALTIES_URL },
    ],
  };

  const collectionData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    url: WORLD_CUP_PENALTIES_URL,
    inLanguage: "en-GB",
    isPartOf: {
      "@type": "WebSite",
      name: "Il Margine",
      url: BASE_URL,
    },
  };

  const itemListData = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "World Cup 2026 national team penalty taker pages",
    itemListElement: data.teams.map((team, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: `${team.team} penalty taker`,
      url: worldCupTeamUrl(team.team),
    })),
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListData) }} />

      <main className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6 pb-12 md:pb-16">
          <PageHomeLink className="mb-8" />

          <div className="relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-[linear-gradient(160deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] p-6 shadow-[0_28px_80px_rgba(0,0,0,0.28)] sm:p-8 lg:p-10">
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -left-10 top-0 h-44 w-44 rounded-full bg-emerald-400/10 blur-3xl" />
              <div className="absolute right-0 top-10 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
              <div className="absolute bottom-0 left-1/3 h-36 w-36 rounded-full bg-amber-400/10 blur-3xl" />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/world-cup-trophy.svg"
                alt=""
                aria-hidden="true"
                className="absolute -bottom-10 right-4 hidden h-[18rem] w-auto rotate-[-8deg] opacity-[0.16] saturate-125 xl:block"
              />
            </div>

            <div className="relative grid gap-8 xl:grid-cols-[1.15fr,0.85fr] xl:items-start">
              <div className="max-w-4xl">
                <div className="mb-5 flex flex-wrap items-center gap-3">
                  <div className="flex h-16 w-16 items-center justify-center rounded-[20px] border border-amber-400/20 bg-[linear-gradient(180deg,rgba(38,30,16,0.85),rgba(14,16,24,0.9))] shadow-[0_16px_40px_rgba(0,0,0,0.24)] sm:h-20 sm:w-20 sm:rounded-[24px]">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src="/world-cup-2026-logo.png"
                      alt="Official FIFA World Cup 2026 emblem"
                      className="h-10 w-10 object-contain sm:h-12 sm:w-12"
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center rounded-full border border-white/15 bg-white px-3 py-1.5 shadow-[0_10px_24px_rgba(0,0,0,0.2)] sm:px-4 sm:py-2">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src="/fifa-logo.svg" alt="FIFA logo" className="h-3.5 w-auto object-contain" />
                    </div>
                    <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-emerald-200 sm:text-[10px] sm:tracking-[0.22em]">
                      Il Margine Intelligence
                    </span>
                    <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-300 sm:text-[10px] sm:tracking-[0.22em]">
                      11 Jun to 19 Jul 2026
                    </span>
                  </div>
                </div>

                <h1 className="text-[2.3rem] font-semibold leading-[0.96] tracking-tight text-slate-100 sm:text-6xl sm:leading-[0.98]">
                  FIFA World Cup <span className="text-emerald-400">2026</span>
                  <br />
                  penalty takers
                </h1>
                <p className="mt-5 max-w-3xl text-[15px] leading-7 text-slate-300 sm:text-lg sm:leading-8">
                  The World Cup board for the exact country query people search. Germany penalty taker,
                  France penalty taker, Brazil penalty taker, Japan penalty taker, Curacao penalty taker.
                  One hub to scan the field, then a proper page for each national team.
                </p>

                <div className="mt-6 flex flex-wrap gap-2">
                  <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Host nations
                  </span>
                  <span className="rounded-full border border-sky-400/25 bg-sky-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-200">
                    USA
                  </span>
                  <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                    Mexico
                  </span>
                  <span className="rounded-full border border-rose-400/25 bg-rose-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-rose-200">
                    Canada
                  </span>
                  <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100">
                    Qualified board live
                  </span>
                </div>


                <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-5">
                    <div className="font-mono text-3xl font-semibold text-emerald-400">{data.qualified_count}</div>
                    <div className="mt-1 text-sm text-slate-400">Confirmed teams</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-5">
                    <div className="font-mono text-3xl font-semibold text-emerald-400">{namedChallengers}</div>
                    <div className="mt-1 text-sm text-slate-400">Named challengers</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-5">
                    <div className="font-mono text-3xl font-semibold text-emerald-400">{confederationCount}</div>
                    <div className="mt-1 text-sm text-slate-400">Confederations</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-5">
                    <div className="font-mono text-xl font-semibold text-emerald-400">{data.last_verified}</div>
                    <div className="mt-1 text-sm text-slate-400">Last verified</div>
                  </div>
                </div>
              </div>

              <aside className="space-y-4">
                <div className="rounded-3xl border border-slate-800/80 bg-slate-950/55 p-5">
                  <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Most searched team pages</div>
                  <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-2">
                    {featuredTeams.map((team) => (
                      <Link
                        key={team.team}
                        href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 px-3 py-3 transition hover:border-slate-600 hover:bg-slate-900 sm:px-4"
                      >
                        <div className="truncate text-sm font-semibold text-slate-100">{team.team}</div>
                        <div className="mt-1 truncate text-xs text-slate-400">{team.likely_primary || "Board still building"}</div>
                      </Link>
                    ))}
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-800/80 bg-slate-950/55 p-5">
                  <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Host nations</div>
                  <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {hostTeams.map((team) => (
                      <Link
                        key={team.team}
                        href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                        className="rounded-2xl border border-slate-800 bg-slate-900/80 p-3 transition hover:border-slate-600 hover:bg-slate-900 sm:p-4"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-950/90 sm:h-10 sm:w-10">
                            {flagImageUrl(team.team) ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img src={flagImageUrl(team.team)} alt={`${team.team} flag`} className="h-5 w-7 rounded-[4px] object-cover sm:h-6 sm:w-8" />
                            ) : (
                              <span className="font-mono text-xs text-slate-200">{initials(team.team)}</span>
                            )}
                          </div>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-100">{team.team}</div>
                            <div className="truncate text-xs text-slate-400">{team.likely_primary || "Board still building"}</div>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </section>

        <section className="mt-2 grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">At A Glance</div>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-100">Big nations, clean first read</h2>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-400">
                  The highest-traffic World Cup penalty pages in one table. Primary first, challenger second, latest evidence alongside it.
                </p>
              </div>
              <Link
                href="/penalty-takers"
                className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              >
                Club penalty takers
              </Link>
            </div>

            <div className="mt-6 space-y-4 md:hidden">
              {atGlanceTeams.map((team) => {
                const style = CONFEDERATION_STYLES[team.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
                return (
                  <Link
                    key={`glance-mobile-${team.team}`}
                    href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                    className="block rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4 transition hover:border-slate-600 hover:bg-slate-950"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/80">
                        {flagImageUrl(team.team) ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={flagImageUrl(team.team)} alt={`${team.team} flag`} className="h-6 w-8 rounded-[4px] object-cover" />
                        ) : (
                          <span className="font-mono text-xs text-slate-200">{initials(team.team)}</span>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-base font-semibold text-slate-100">{team.team}</div>
                          <div className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${style.badge}`}>
                            {team.confederation}
                          </div>
                        </div>
                        <div className="mt-3 grid gap-3 text-sm">
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Primary</div>
                            <div className="mt-1 font-semibold text-slate-100">{team.likely_primary || "Building"}</div>
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Challenger</div>
                            <div className="mt-1 text-slate-300">{team.likely_secondary || "No named backup yet"}</div>
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Latest key evidence</div>
                            <div className="mt-1 leading-6 text-slate-400">{trimEvidence(team.last_evidence, 120)}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>

            <div className="mt-6 hidden overflow-hidden rounded-2xl border border-slate-800/80 md:block">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-800/80">
                  <thead className="bg-slate-950/80">
                    <tr className="text-left text-[10px] uppercase tracking-[0.22em] text-slate-500">
                      <th className="px-4 py-3 font-medium">Nation</th>
                      <th className="px-4 py-3 font-medium">Primary</th>
                      <th className="px-4 py-3 font-medium">Challenger</th>
                      <th className="px-4 py-3 font-medium">Latest key evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 bg-slate-900/70">
                    {atGlanceTeams.map((team) => {
                      const style = CONFEDERATION_STYLES[team.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
                      return (
                        <tr key={`glance-${team.team}`} className="align-top">
                          <td className="px-4 py-4">
                            <Link href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`} className="group flex items-center gap-3">
                              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-950/90">
                                {flagImageUrl(team.team) ? (
                                  // eslint-disable-next-line @next/next/no-img-element
                                  <img src={flagImageUrl(team.team)} alt={`${team.team} flag`} className="h-6 w-8 rounded-[4px] object-cover" />
                                ) : (
                                  <span className="font-mono text-xs text-slate-200">{initials(team.team)}</span>
                                )}
                              </div>
                              <div>
                                <div className="text-sm font-semibold text-slate-100 transition group-hover:text-emerald-300">{team.team}</div>
                                <div className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${style.badge}`}>
                                  {team.confederation}
                                </div>
                              </div>
                            </Link>
                          </td>
                          <td className="px-4 py-4 text-sm font-semibold text-slate-100">{team.likely_primary || "Building"}</td>
                          <td className="px-4 py-4 text-sm text-slate-300">{team.likely_secondary || "No named backup yet"}</td>
                          <td className="px-4 py-4 text-sm leading-6 text-slate-400">{trimEvidence(team.last_evidence)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">A-Z Index</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">All nations, one scan</h2>
            <p className="mt-2 text-sm leading-7 text-slate-400">
              Every qualified team listed alphabetically with the current primary taker. Built for quick scanning and clean internal linking.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              {grouped.map((group) => {
                const style = CONFEDERATION_STYLES[group.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
                return (
                  <a
                    key={`index-chip-${group.confederation}`}
                    href={`#${group.confederation.toLowerCase()}`}
                    className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${style.badge}`}
                  >
                    {group.confederation}
                  </a>
                );
              })}
            </div>

            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {alphabeticalTeams.map((team) => (
                <Link
                  key={`az-${team.team}`}
                  href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                  className="flex items-center gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/70 px-3 py-3 transition hover:border-slate-600 hover:bg-slate-950"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/80">
                    {flagImageUrl(team.team) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={flagImageUrl(team.team)} alt={`${team.team} flag`} className="h-5 w-7 rounded-[3px] object-cover" />
                    ) : (
                      <span className="font-mono text-[11px] text-slate-200">{initials(team.team)}</span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-100">{team.team}</div>
                    <div className="truncate text-xs text-slate-400">{team.likely_primary || "Board still being built"}</div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-6">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Confederation Index</div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">
                  Browse the field by confederation
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {grouped.map((group) => {
                  const style = CONFEDERATION_STYLES[group.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
                  return (
                    <a
                      key={`jump-${group.confederation}`}
                      href={`#${group.confederation.toLowerCase()}`}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] ${style.badge}`}
                    >
                      {group.confederation}
                    </a>
                  );
                })}
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {grouped.map((group) => {
                const style = CONFEDERATION_STYLES[group.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
                return (
                  <div key={`index-${group.confederation}`} className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className={`rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] ${style.badge}`}>
                        {group.confederation}
                      </span>
                      <span className="text-xs text-slate-500">{group.teams.length} teams</span>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {group.teams.map((team) => (
                        <Link
                          key={`index-${team.team}`}
                          href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                          className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                        >
                          {team.team}
                        </Link>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="mt-12 space-y-14">
          {grouped.map((group) => {
            const style = CONFEDERATION_STYLES[group.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
            return (
              <section key={group.confederation} id={group.confederation.toLowerCase()} className="scroll-mt-28">
                <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <div className={`inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.24em] ${style.badge}`}>
                      {group.confederation}
                    </div>
                    <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-100">{group.confederation}</h2>
                    <p className="mt-3 max-w-3xl text-[15px] leading-7 text-slate-300">{group.intro}</p>
                  </div>
                  <div className="rounded-full border border-slate-700 bg-slate-950/80 px-4 py-2 text-sm text-slate-400">
                    {group.teams.length} teams in scope
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  {group.teams.map((team) => {
                    const primary = team.likely_primary?.trim();
                    const secondary = team.likely_secondary?.trim();
                    const confStyle = CONFEDERATION_STYLES[group.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;

                    return (
                      <article
                        key={team.team}
                        className={`overflow-hidden rounded-[28px] border border-slate-700/80 bg-slate-900/75 transition ${style.glow}`}
                      >
                        <div className="grid gap-0 lg:grid-cols-[0.95fr,1.05fr]">
                          <div className={`relative overflow-hidden border-b border-slate-800/80 bg-gradient-to-br p-6 lg:border-b-0 lg:border-r ${confStyle.panel}`}>
                            <div className={`absolute left-0 top-0 h-full w-1 ${style.accent}`} />
                            <div className="relative flex h-full flex-col">
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex items-start gap-4">
                                  <Link
                                    href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                                    className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-950/90"
                                  >
                                    {flagImageUrl(team.team) ? (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img
                                        src={flagImageUrl(team.team)}
                                        alt={`${team.team} flag`}
                                        className="h-8 w-10 rounded-[4px] object-cover shadow-sm"
                                      />
                                    ) : (
                                      <span className="font-mono text-[13px] font-semibold text-slate-200">{initials(team.team)}</span>
                                    )}
                                  </Link>
                                  <div>
                                    <Link
                                      href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                                      className="text-2xl font-semibold tracking-tight text-slate-100 hover:text-emerald-300"
                                    >
                                      {team.team}
                                    </Link>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${style.badge}`}>
                                        {team.confederation}
                                      </span>
                                      <span className="rounded-full border border-slate-700 bg-slate-950/80 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-400">
                                        {team.source_urls?.length ?? 0} sources
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              </div>

                              <div className="mt-8 grid gap-3">
                                <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Current primary</div>
                                  <div className={`mt-2 text-3xl font-semibold tracking-tight ${primary ? confStyle.primary : "text-slate-200"}`}>
                                    {primary || "Board still building"}
                                  </div>
                                </div>

                                <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Closest challenger</div>
                                  <div className={`mt-2 text-xl font-semibold tracking-tight ${secondary ? confStyle.secondary : "text-slate-400"}`}>
                                    {secondary || "Not strong enough to name yet"}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="p-6">
                            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/75 p-4">
                              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Latest key evidence</div>
                              <div className="mt-1.5 text-sm leading-6 text-slate-300">
                                {team.last_evidence || "File still being built from the latest cycle."}
                              </div>
                            </div>

                            <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4">
                              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-emerald-400">Editorial note</div>
                              <p className="mt-3 text-sm leading-7 text-slate-300">{trimEvidence(team.note, 220)}</p>
                            </div>

                            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                              <div className="text-xs text-slate-500">{team.source_urls?.length ?? 0} sources in file</div>
                              <Link
                                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                                className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                              >
                                Open {team.team} page
                              </Link>
                            </div>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </section>

        <section className="mt-14 grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Still Outside The Field</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Play-off watchlist</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
              This block covers the six intercontinental play-off teams fighting for the final two tournament spots.
              The remaining UEFA slots are a separate layer and will sit on their own watchlist once the field is complete.
            </p>
            <div className="mt-5 flex flex-wrap gap-2.5">
              {data.playoff_teams.map((team) => (
                <span key={team.team} className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300">
                  {team.team} <span className="text-slate-500">({team.confederation})</span>
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Editorial Note</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Why this page should rank before the tournament</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>Official senior in-match penalties come first. Federation confirmation comes next. Local-language reporting and event timelines tighten the call when the file is still mixed.</p>
              <p>Shoot-outs can support the order, but they do not automatically overrule a stronger recent in-match trail. When the file is mixed, the page says so plainly in the note instead of hiding behind a vague label.</p>
              <p>The hub is built to scan fast. The country pages exist so every team can stand on its own for searches like <span className="text-slate-100">Germany penalty taker</span>, <span className="text-slate-100">France penalty taker</span> or <span className="text-slate-100">Curacao penalty taker</span>. The page that is live, crawlable and updated fastest once squads are confirmed is the page that has the best shot when tournament demand spikes.</p>
            </div>
          </div>
        </section>

        <section className="mt-6">
          <div className="rounded-3xl border border-emerald-400/18 bg-[linear-gradient(140deg,rgba(6,26,20,0.94),rgba(10,15,24,0.96))] p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Help Tighten The Board</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Closer to one of the squads?</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              If you cover one of the qualified teams locally, work around the squad, or simply have stronger reporting than we do on a live hierarchy shift, send it through. Useful corrections beat stale consensus every time.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <a
                href="mailto:contact@ilmargine.bet"
                className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:border-emerald-300/40 hover:bg-emerald-400/14"
              >
                contact@ilmargine.bet
              </a>
              <span className="text-sm text-slate-400">Spot an error, a new taker, or a better local source? Let us know.</span>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
