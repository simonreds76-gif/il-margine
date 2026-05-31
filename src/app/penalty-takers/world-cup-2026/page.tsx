import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import FlagMark from "@/components/FlagMark";
import PageHomeLink from "@/components/PageHomeLink";
import WorldCupTeamIndex from "./WorldCupTeamIndex";
import {
  CONFEDERATION_ORDER,
  WORLD_CUP_PENALTIES_URL,
  WORLD_CUP_GROUP_ORDER,
  WORLD_CUP_GROUPS,
  readWorldCupData,
  teamCrestImageUrl,
  worldCupTeamSlug,
  worldCupTeamUrl,
  formatAuditDate,
  initials,
  publicPenaltyEvidenceText,
} from "@/lib/world-cup-penalties";
import { BASE_URL } from "@/lib/config";

const PAGE_TITLE = "World Cup 2026 Penalty Takers by Nation";
const PAGE_DESCRIPTION =
  "Who takes penalties for every qualified nation at the 2026 FIFA World Cup? First-choice and backup penalty takers from the Il Margine World Cup intelligence file.";

const FEATURED_TEAMS = ["Germany", "France", "Brazil", "Argentina", "England", "Spain", "Japan", "Netherlands", "USA", "Mexico"];

const LATEST_HIERARCHY_UPDATES = [
  {
    team: "Brazil",
    label: "Neymar conditional No. 1",
    summary: "Neymar owns the penalty if fit and on the pitch; Raphinha is the practical taker only when Neymar is absent or not starting.",
  },
  {
    team: "Korea Republic",
    label: "Son then Hwang confirmed",
    summary: "Son scored the first penalty against Trinidad and Tobago; Hwang converted another after Son had been substituted.",
  },
  {
    team: "Curacao",
    label: "Backup caveat tightened",
    summary: "Leandro Bacuna has the direct qualifier evidence. Juninho Bacuna is an inferred fallback after Jordi Paulina missed the final squad.",
  },
  {
    team: "IR Iran",
    label: "Azmoun removed from backup line",
    summary: "Azmoun is outside the squad path, so Jahanbakhsh moves into the in-squad fallback slot behind Taremi.",
  },
  {
    team: "Cabo Verde",
    label: "Bebe out, Cabral in",
    summary: "Ryan Mendes remains the lead. Jovane Cabral replaces Bebe as the best in-squad backup after the final-squad audit.",
  },
  {
    team: "Jordan",
    label: "Olwan trail stays stronger",
    summary: "Ali Olwan has the late-cycle penalty trail; Musa Al-Taamari remains the closest challenger from the current squad list.",
  },
];

const CONFEDERATION_INTROS: Record<string, string> = {
  UEFA:
    "UEFA gives us the deepest evidence pool: qualifiers, Nations League minutes and repeated senior penalty events usually make the first-choice order easier to verify.",
  CONMEBOL:
    "CONMEBOL often looks obvious on the headline sides, but the right answer still comes from actual in-match penalties, not reputation alone.",
  Concacaf:
    "Concacaf is the section where squad context matters most. Some countries are stable, others switch takers depending on availability and tournament squad strength.",
  AFC:
    "AFC needs a multilingual lens more than any other section here. The hierarchy often needs a deeper event audit before the backup line becomes trustworthy.",
  CAF:
    "CAF is exactly where this kind of page can be useful. Tournament and qualifier evidence exists, but few places keep the hierarchy cleanly updated.",
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
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(56,189,248,0.08)]",
    primary: "text-sky-100",
    secondary: "text-sky-200",
    accent: "bg-sky-300",
  },
  CONMEBOL: {
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    panel: "from-emerald-500/20 via-emerald-400/8 to-slate-950",
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(16,185,129,0.08)]",
    primary: "text-emerald-100",
    secondary: "text-emerald-200",
    accent: "bg-emerald-300",
  },
  Concacaf: {
    badge: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
    panel: "from-cyan-500/20 via-cyan-400/8 to-slate-950",
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(34,211,238,0.08)]",
    primary: "text-cyan-100",
    secondary: "text-cyan-200",
    accent: "bg-cyan-300",
  },
  AFC: {
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    panel: "from-amber-500/20 via-amber-400/8 to-slate-950",
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(251,191,36,0.08)]",
    primary: "text-amber-50",
    secondary: "text-amber-200",
    accent: "bg-amber-300",
  },
  CAF: {
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    panel: "from-rose-500/20 via-rose-400/8 to-slate-950",
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(251,113,133,0.08)]",
    primary: "text-rose-100",
    secondary: "text-rose-200",
    accent: "bg-rose-300",
  },
  OFC: {
    badge: "border-violet-400/30 bg-violet-400/10 text-violet-200",
    panel: "from-violet-500/20 via-violet-400/8 to-slate-950",
    glow: "shadow-none sm:hover:shadow-[0_26px_70px_rgba(167,139,250,0.08)]",
    primary: "text-violet-100",
    secondary: "text-violet-200",
    accent: "bg-violet-300",
  },
};

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: {
    canonical: WORLD_CUP_PENALTIES_URL,
  },
  keywords: [
    "world cup 2026 penalty takers",
    "fifa world cup 2026 penalty takers",
    "who takes penalties in the world cup",
    "national team penalty takers",
    "germany penalty taker",
    "france penalty taker",
    "brazil penalty taker",
    "australia penalty taker",
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

  const featuredTeams = FEATURED_TEAMS.flatMap((name) => {
    const match = data.teams.find((team) => team.team === name);
    return match ? [match] : [];
  });
  const latestHierarchyUpdates = LATEST_HIERARCHY_UPDATES.flatMap((update) => {
    const team = data.teams.find((candidate) => candidate.team === update.team);
    return team ? [{ ...update, team }] : [];
  });
  const finalSquadsAudited = data.teams.filter((team) => team.squad_status === "final_announced").length;
  const lastVerifiedLabel = formatAuditDate(data.last_verified);
  const alphabeticalTeams = [...data.teams].sort((left, right) => left.team.localeCompare(right.team, "en"));
  const alphabeticalIndexTeams = alphabeticalTeams.map((team) => ({
    team: team.team,
    confederation: team.confederation,
    group: team.group,
    likely_primary: team.likely_primary,
    slug: worldCupTeamSlug(team.team),
    crestUrl: teamCrestImageUrl(team.team),
    initials: initials(team.team),
  }));
  const indexFilters = grouped.map((group) => ({
    key: group.confederation,
    count: group.teams.length,
    badgeClassName: CONFEDERATION_STYLES[group.confederation]?.badge ?? CONFEDERATION_STYLES.CONMEBOL.badge,
  }));
  const indexGroups = WORLD_CUP_GROUP_ORDER.map((group) => ({
    key: group,
    count: WORLD_CUP_GROUPS[group]?.length ?? 0,
    entries: (WORLD_CUP_GROUPS[group] ?? []).map((entry) => {
      const team = data.teams.find((candidate) => candidate.team === entry);
      if (team) {
        return {
          kind: "team" as const,
          team: team.team,
          confederation: team.confederation,
          group,
          likely_primary: team.likely_primary,
          slug: worldCupTeamSlug(team.team),
          crestUrl: teamCrestImageUrl(team.team),
          initials: initials(team.team),
        };
      }

      return {
        kind: "placeholder" as const,
        team: entry,
        group,
        initials: initials(entry),
        note: entry.startsWith("UEFA Path") ? "Winner slots in after 31 March" : "Winner slots in after the play-off tournament",
      };
    }),
  }));
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
    dateModified: data.last_verified,
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

          <div className="relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-[linear-gradient(160deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] p-5 shadow-[0_18px_48px_rgba(0,0,0,0.24)] sm:p-8 sm:shadow-[0_28px_80px_rgba(0,0,0,0.28)] lg:p-10">
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -left-10 top-0 hidden h-44 w-44 rounded-full bg-emerald-400/10 blur-3xl sm:block" />
              <div className="absolute right-0 top-10 hidden h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl sm:block" />
              <div className="absolute bottom-0 left-1/3 hidden h-36 w-36 rounded-full bg-amber-400/10 blur-3xl sm:block" />
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/world-cup-trophy.svg"
                alt=""
                aria-hidden="true"
                className="absolute -bottom-10 right-4 hidden h-[18rem] w-auto rotate-[-8deg] opacity-[0.16] saturate-125 xl:block"
              />
            </div>

            <div className="relative max-w-4xl">
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
                First-choice and backup penalty takers for every qualified nation at the 2026 FIFA World Cup.
                If you are searching for France penalty taker, Germany penalty taker or Australia penalty taker, each
                nation page gives the current World Cup call, backup order and evidence trail.
              </p>

              <div className="mt-6 flex flex-wrap gap-2">
                <span className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                  Hosts: Canada, Mexico, USA
                </span>
                <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-100">
                  Field complete: 48/48
                </span>
              </div>

              <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 sm:p-5">
                  <div className="font-mono text-3xl font-semibold text-emerald-400">
                    {data.qualified_count}
                    <span className="text-lg text-emerald-200/70">/48</span>
                  </div>
                  <div className="mt-1 text-sm text-slate-400">Qualified nations covered</div>
                </div>
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 sm:p-5">
                  <div className="font-mono text-3xl font-semibold text-emerald-400">{finalSquadsAudited}</div>
                  <div className="mt-1 text-sm text-slate-400">Final squads audited</div>
                </div>
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 sm:p-5">
                  <div className="font-mono text-3xl font-semibold text-emerald-400">{latestHierarchyUpdates.length}</div>
                  <div className="mt-1 text-sm text-slate-400">Evidence notes refreshed</div>
                </div>
                <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 sm:p-5">
                  <div className="font-mono text-xl font-semibold text-emerald-400">{lastVerifiedLabel}</div>
                  <div className="mt-1 text-sm text-slate-400">Latest audit</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-2 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
          <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Most searched team pages</div>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-100">Fastest route to the likely answer</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
                The highest-volume country queries first. Open the nation page and the penalty-taker answer is at the
                top, with the supporting trail straight underneath it.
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
            {featuredTeams.map((team) => (
              <Link
                key={team.team}
                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                className="rounded-2xl border border-slate-800 bg-slate-900/80 px-3 py-3 transition hover:border-slate-600 hover:bg-slate-900 sm:px-4"
              >
                <div className="truncate text-sm font-semibold text-slate-100">{team.team} penalty taker</div>
                <div className="mt-1 truncate text-xs text-slate-400">{team.likely_primary || "Board still building"}</div>
              </Link>
            ))}
          </div>
        </section>

        <section
          id="group-browser"
          className="mt-6 scroll-mt-28 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]"
        >
          <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Group browser</div>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-100">Browse by World Cup 2026 group</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
                Group A through Group L of the 2026 FIFA World Cup, with each team&apos;s current first-choice penalty taker.
              </p>
            </div>
            <div className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-400">
              Updated {lastVerifiedLabel}
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {indexGroups.map((group) => (
              <article key={`group-browser-${group.key}`} className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-4">
                <h3 className="text-lg font-semibold tracking-tight text-slate-100">Group {group.key}</h3>
                <ul className="mt-3 space-y-2">
                  {group.entries.map((entry) => (
                    <li key={`group-browser-${group.key}-${entry.team}`}>
                      {entry.kind === "team" ? (
                        <Link
                          href={`/penalty-takers/world-cup-2026/${entry.slug}`}
                          className="flex items-center gap-3 rounded-xl border border-slate-800/80 bg-slate-900/70 px-3 py-2 transition hover:border-slate-600 hover:bg-slate-900"
                        >
                          <FlagMark
                            src={entry.crestUrl}
                            alt={`${entry.team} crest`}
                            fallbackText={entry.initials}
                            wrapperClassName="flex h-9 w-9 shrink-0 items-center justify-center"
                            imageClassName="h-8 w-8 object-contain drop-shadow-[0_4px_10px_rgba(0,0,0,0.45)]"
                            fallbackClassName="font-mono text-[10px] text-slate-200"
                            width={32}
                            height={32}
                            sizes="32px"
                          />
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-semibold text-slate-100">{entry.team}</span>
                            <span className="mt-0.5 block truncate text-xs text-slate-400">
                              {entry.likely_primary || "Penalty file still building"}
                            </span>
                          </span>
                        </Link>
                      ) : (
                        <div className="rounded-xl border border-dashed border-slate-700/80 bg-slate-900/40 px-3 py-2">
                          <span className="block truncate text-sm font-semibold text-slate-300">{entry.team}</span>
                          <span className="mt-0.5 block text-xs text-slate-500">{entry.note}</span>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <WorldCupTeamIndex teams={alphabeticalIndexTeams} confederations={indexFilters} groups={indexGroups} />

        <section className="mt-10 space-y-10 sm:mt-12 sm:space-y-14">
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
                                    className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl"
                                  >
                                    <FlagMark
                                      src={teamCrestImageUrl(team.team)}
                                      alt={`${team.team} crest`}
                                      fallbackText={initials(team.team)}
                                      wrapperClassName="flex h-14 w-14 shrink-0 items-center justify-center"
                                      imageClassName="h-12 w-12 object-contain drop-shadow-[0_8px_18px_rgba(0,0,0,0.45)]"
                                      fallbackClassName="font-mono text-[13px] font-semibold text-slate-200"
                                      width={48}
                                      height={48}
                                      sizes="48px"
                                    />
                                  </Link>
                                  <div>
                                    <Link
                                      href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                                      className="text-2xl font-semibold tracking-tight text-slate-100 hover:text-emerald-300"
                                    >
                                      {team.team} penalty taker
                                    </Link>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${style.badge}`}>
                                        {team.confederation}
                                      </span>
                                      <span className="rounded-full border border-slate-700 bg-slate-950/80 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-400">
                                        Il Margine file
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
                                {publicPenaltyEvidenceText(team.last_evidence, "File still being built from the latest cycle.")}
                              </div>
                            </div>

                            <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4">
                              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-emerald-400">Editorial note</div>
                              <p className="mt-3 text-sm leading-7 text-slate-300">{trimEvidence(publicPenaltyEvidenceText(team.note), 220)}</p>
                            </div>

                            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                              <div className="text-xs text-slate-500">Il Margine confidence: {team.confidence}</div>
                              <Link
                                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(team.team)}`}
                                className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                              >
                                Open {team.team} penalty taker
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

        <section className="mt-14 grid gap-4 sm:gap-6 xl:grid-cols-[1.05fr,0.95fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Latest Evidence Notes</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">What changed in the latest audit</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
              The page is now less about qualification slots and more about the penalty hierarchy itself. These are the
              latest notes that moved the board or tightened the public wording after the final-squad check.
            </p>
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {latestHierarchyUpdates.map((update) => (
                <Link
                  key={update.team.team}
                  href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(update.team.team)}`}
                  className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4 transition hover:border-slate-600 hover:bg-slate-900/90"
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center">
                      <FlagMark
                        src={teamCrestImageUrl(update.team.team)}
                        alt={`${update.team.team} crest`}
                        fallbackText={initials(update.team.team)}
                        wrapperClassName="flex h-12 w-12 shrink-0 items-center justify-center"
                        imageClassName="h-10 w-10 object-contain drop-shadow-[0_8px_18px_rgba(0,0,0,0.45)]"
                        fallbackClassName="font-mono text-[12px] font-semibold text-slate-200"
                        width={40}
                        height={40}
                        sizes="40px"
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-base font-semibold tracking-tight text-slate-100">{update.team.team}</span>
                        <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                          Group {update.team.group}
                        </span>
                        <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-200">
                          {update.team.confidence}
                        </span>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-slate-200">{update.label}</div>
                      <div className="mt-2 text-xs leading-6 text-slate-400">{update.summary}</div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">How The Board Moves</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">How the finished board gets tightened</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>Senior in-match penalties come first. Squad confirmation, event timelines and repeat pressure evidence tighten the call when the file is still mixed.</p>
              <p>Shoot-outs can support the order, but they do not automatically overrule a stronger recent in-match trail. When the file is mixed, the page says so plainly in the note instead of hiding behind a vague label.</p>
              <p>Now that the field is complete, the live work is less about qualification slots and more about hierarchy drift. The goal is simple: give the country-level answer quickly, then show the evidence that justifies it.</p>
            </div>
          </div>
        </section>

        <section className="mt-6">
          <div className="rounded-3xl border border-emerald-400/18 bg-[linear-gradient(140deg,rgba(6,26,20,0.94),rgba(10,15,24,0.96))] p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Help Tighten The Board</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Closer to one of the squads?</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              If you cover one of the qualified teams locally, work around the squad, or simply have stronger information on a live hierarchy shift, send it through. Useful corrections beat stale consensus every time.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <a
                href="mailto:contact@ilmargine.bet"
                className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:border-emerald-300/40 hover:bg-emerald-400/14"
              >
                contact@ilmargine.bet
              </a>
              <span className="text-sm text-slate-400">Spot an error, a new taker, or a stronger hierarchy signal? Let us know.</span>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
