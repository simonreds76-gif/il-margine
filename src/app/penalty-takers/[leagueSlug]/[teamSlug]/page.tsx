import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import {
  CLUB_PENALTY_SEASON,
  CLUB_PENALTY_PREVIOUS_SEASON,
  buildClubPenaltyDescription,
  buildClubPenaltyLead,
  buildClubPenaltyTitle,
  getClubPenaltyTeam,
  readClubPenaltyData,
  readAllClubPenaltyTeams,
  type ClubPenaltyTeam,
} from "@/lib/club-penalty-takers";

export const revalidate = 43200;

type PageProps = {
  params: Promise<{
    leagueSlug: string;
    teamSlug: string;
  }>;
};

const ACCENTS: Record<string, { badge: string; glow: string; text: string; fill: string }> = {
  emerald: {
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    glow: "shadow-[0_24px_80px_rgba(16,185,129,0.10)]",
    text: "text-emerald-300",
    fill: "bg-emerald-300",
  },
  indigo: {
    badge: "border-indigo-400/30 bg-indigo-400/10 text-indigo-200",
    glow: "shadow-[0_24px_80px_rgba(129,140,248,0.10)]",
    text: "text-indigo-200",
    fill: "bg-indigo-300",
  },
  amber: {
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    glow: "shadow-[0_24px_80px_rgba(245,158,11,0.10)]",
    text: "text-amber-200",
    fill: "bg-amber-300",
  },
  rose: {
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    glow: "shadow-[0_24px_80px_rgba(248,113,113,0.10)]",
    text: "text-rose-200",
    fill: "bg-rose-300",
  },
  cyan: {
    badge: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
    glow: "shadow-[0_24px_80px_rgba(34,211,238,0.10)]",
    text: "text-cyan-200",
    fill: "bg-cyan-300",
  },
};

function Crest({ team }: { team: ClubPenaltyTeam }) {
  return (
    <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-[24px] border border-slate-700/80 bg-slate-950/90 shadow-[0_12px_30px_rgba(0,0,0,0.2)] sm:h-24 sm:w-24 sm:rounded-[28px]">
      {team.logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={team.logoPath} alt={`${team.team} crest`} className="h-14 w-14 object-contain sm:h-16 sm:w-16" />
      ) : (
        <span className="font-mono text-lg font-semibold text-slate-300">{team.initials}</span>
      )}
    </div>
  );
}

function LeagueLogo({ team }: { team: ClubPenaltyTeam }) {
  return (
    <span className="inline-flex h-7 w-7 items-center justify-center overflow-hidden rounded-lg border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 align-middle shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={team.leagueLogoPath} alt={team.leagueLabel} className="h-5 w-5 object-contain" />
    </span>
  );
}

function MiniClubLogo({
  team,
  size = "card",
}: {
  team: ClubPenaltyTeam;
  size?: "card" | "nav";
}) {
  const wrapperClass =
    size === "nav"
      ? "inline-flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-700/70 bg-slate-950/80 shadow-[0_8px_18px_rgba(0,0,0,0.18)]"
      : "inline-flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-700/75 bg-slate-950/80 shadow-[0_8px_18px_rgba(0,0,0,0.18)]";
  const imageClass = size === "nav" ? "h-5 w-5 object-contain" : "h-6 w-6 object-contain";

  return (
    <span className={wrapperClass}>
      {team.logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={team.logoPath} alt={`${team.team} crest`} className={imageClass} />
      ) : (
        <span className="font-mono text-[10px] font-semibold text-slate-300">{team.initials}</span>
      )}
    </span>
  );
}

function MiniLeagueLogo({ team }: { team: ClubPenaltyTeam }) {
  return (
    <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/70 bg-gradient-to-b from-white to-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={team.leagueLogoPath} alt={team.leagueLabel} className="h-5 w-5 object-contain" />
    </span>
  );
}

export async function generateStaticParams() {
  const teams = await readAllClubPenaltyTeams();
  return teams.map((team) => ({
    leagueSlug: team.leagueKey,
    teamSlug: team.slug,
  }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { leagueSlug, teamSlug } = await params;
  const team = await getClubPenaltyTeam(leagueSlug, teamSlug);

  if (!team) {
    return { title: "Club penalty taker" };
  }

  const title = buildClubPenaltyTitle(team);
  const description = buildClubPenaltyDescription(team);

  return {
    title,
    description,
    alternates: { canonical: team.absoluteUrl },
    keywords: [
      `${team.team} penalty taker`,
      `who is ${team.team} penalty taker`,
      `who takes penalties for ${team.team}`,
      `${team.team} first choice penalty taker`,
      `${team.team} penalty takers`,
      `${team.team} penalty order`,
      `${team.leagueLabel} penalty takers`,
    ],
    openGraph: {
      type: "article",
      title: `${title} | Il Margine`,
      description,
      url: team.absoluteUrl,
      siteName: "Il Margine",
      images: [{ url: `${team.absoluteUrl}/opengraph-image`, width: 1200, height: 630, alt: `${team.team} penalty taker` }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} | Il Margine`,
      description,
      images: [`${team.absoluteUrl}/opengraph-image`],
    },
    robots: { index: true, follow: true },
  };
}

export default async function ClubPenaltyTakerPage({ params }: PageProps) {
  const { leagueSlug, teamSlug } = await params;
  const [team, leagues] = await Promise.all([getClubPenaltyTeam(leagueSlug, teamSlug), readClubPenaltyData()]);

  if (!team) notFound();

  const league = leagues.find((entry) => entry.key === team.leagueKey);
  const leagueTeams = league?.teams ?? [];
  const teamIndex = leagueTeams.findIndex((entry) => entry.slug === team.slug);
  const previous = teamIndex > 0 ? leagueTeams[teamIndex - 1] : undefined;
  const next = teamIndex >= 0 && teamIndex < leagueTeams.length - 1 ? leagueTeams[teamIndex + 1] : undefined;
  const related = leagueTeams.filter((entry) => entry.slug !== team.slug).slice(0, 8);
  const accent = ACCENTS[team.leagueAccent] ?? ACCENTS.emerald;
  const title = buildClubPenaltyTitle(team);
  const description = buildClubPenaltyDescription(team);
  const lead = buildClubPenaltyLead(team);

  const quickAnswer = lead;
  const secondAnswer = team.hierarchyStatus === "unknown"
    ? `The ${team.team} backup penalty taker is not yet verified for ${CLUB_PENALTY_SEASON}.`
    : team.secondary && team.secondary !== "TBC" && team.secondary !== "Not yet verified"
    ? `${team.secondary} is listed as the next ${team.team} penalty taker behind ${team.primary}. ${team.tertiary ? `${team.tertiary} is the current third-choice name.` : "The third-choice line is thinner."}`
    : `We do not have a strong second-choice ${team.team} penalty taker call yet.`;

  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Penalty Takers", item: `${BASE_URL}/penalty-takers` },
      { "@type": "ListItem", position: 3, name: team.leagueLabel, item: `${BASE_URL}/penalty-takers/${team.leagueKey}` },
      { "@type": "ListItem", position: 4, name: team.team, item: team.absoluteUrl },
    ],
  };

  const pageData = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: title,
    description,
    url: team.absoluteUrl,
    dateModified: team.publicUpdatedAt || undefined,
    about: {
      "@type": "SportsTeam",
      name: team.team,
      sport: "Association football",
      memberOf: team.leagueLabel,
    },
    isPartOf: {
      "@type": "CollectionPage",
      name: `Penalty Takers ${CLUB_PENALTY_SEASON}`,
      url: `${BASE_URL}/penalty-takers`,
    },
  };

  const faqData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: `Who is ${team.team}'s penalty taker?`,
        acceptedAnswer: { "@type": "Answer", text: quickAnswer },
      },
      {
        "@type": "Question",
        name: `Who is ${team.team}'s second-choice penalty taker?`,
        acceptedAnswer: { "@type": "Answer", text: secondAnswer },
      },
    ],
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(pageData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqData) }} />

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6 pb-12 md:pb-16">
          <PageHomeLink className="mb-8" />

          <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-400">
            <Link href="/penalty-takers" className="hover:text-slate-100">Penalty Takers</Link>
            <span>/</span>
            <Link href={`/penalty-takers/${team.leagueKey}`} className="hover:text-slate-100">{team.leagueLabel}</Link>
            <span>/</span>
            <span className="text-slate-200">{team.team}</span>
          </div>

          <div className={`relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-[linear-gradient(160deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] ${accent.glow}`}>
            <div className={`pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-r ${team.leagueSurface}`} />
            <div className="pointer-events-none absolute right-8 top-4 hidden text-[130px] font-semibold tracking-[-0.08em] text-white/5 xl:block">
              {team.initials}
            </div>

            <div className="relative p-5 pt-20 sm:p-8 sm:pt-28 lg:p-10">
              <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr] xl:items-start">
                <div className="max-w-4xl">
                  <div className="flex flex-col items-start gap-4 sm:flex-row">
                    <Crest team={team} />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${accent.badge}`}>
                          <LeagueLogo team={team} /> <span className="ml-2 align-middle">{team.leagueLabel}</span>
                        </span>
                        <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                          {team.seasonLabel}
                        </span>
                      </div>
                      <h1 className="mt-4 text-[2.2rem] font-semibold leading-[0.98] tracking-tight text-slate-100 sm:text-5xl sm:leading-[1.02]">
                        {team.team} <span className={accent.text}>penalty taker</span>
                      </h1>
                      <p className="mt-4 max-w-3xl text-[15px] leading-7 text-slate-300 sm:text-lg sm:leading-8">
                        {lead}
                      </p>
                      {team.isArchived ? (
                        <p className="mt-4 max-w-3xl rounded-2xl border border-slate-600/60 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-300">
                          Archived record: {team.team} are not on the current {team.leagueLabel} board. This page preserves the final {team.seasonLabel} hierarchy and URL.
                        </p>
                      ) : team.hierarchyStatus === "unknown" || team.hierarchyStatus === "disputed" ? (
                        <p className="mt-4 max-w-3xl rounded-2xl border border-amber-300/25 bg-amber-400/10 px-4 py-3 text-sm leading-6 text-amber-100">
                          {team.conditionNote || `No public hierarchy is claimed until direct preseason or competitive evidence supports it for ${CLUB_PENALTY_SEASON}.`}
                        </p>
                      ) : team.isCarryover ? (
                        <p className="mt-4 max-w-3xl rounded-2xl border border-cyan-300/20 bg-cyan-400/8 px-4 py-3 text-sm leading-6 text-cyan-100">
                          Provisional carryover from the final {CLUB_PENALTY_PREVIOUS_SEASON} order. It is being re-verified through preseason and the opening weeks.
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>

                <aside className={`overflow-hidden rounded-3xl border border-slate-800/80 bg-gradient-to-br ${team.leagueSurface} p-4 shadow-[0_18px_50px_rgba(0,0,0,0.24)] sm:p-5`}>
                  <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-slate-300">Penalty hierarchy</div>
                  <div className="mt-4 space-y-3">
                    {[
                      ["1", "Current primary", team.primary],
                      ["2", "Second choice", team.secondary],
                      ["3", "Third choice", team.tertiary || "Watchlist"],
                    ].map(([rank, label, value]) => (
                      <div key={label} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                        <div className="flex items-start gap-3">
                          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 font-mono text-base font-semibold ${rank === "1" ? `${accent.fill} text-slate-950` : "bg-slate-950/60 text-slate-300"}`}>
                            {rank}
                          </div>
                          <div>
                            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">{label}</div>
                            <div className={`mt-1.5 text-xl font-semibold tracking-tight ${rank === "1" ? accent.text : "text-slate-200"}`}>{value}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </aside>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 sm:gap-6 xl:grid-cols-[1.08fr,0.92fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_14px_40px_rgba(0,0,0,0.18)] sm:p-6">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Quick answer</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Who takes penalties for {team.team}?</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>{quickAnswer}</p>
              <p>
                This page is built as a live Il Margine club file, not a one-name list. If the first-choice taker is injured, suspended, substituted or not starting, the second and third names become the useful part of the hierarchy.
              </p>
              <p>
                Penalty order is one input in goalscorer pricing. When {team.leagueLabel} fixtures are live, compare the hierarchy with the{" "}
                <Link href="/fair-odds-lab" className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300">
                  Goalscorer Fair Odds Lab
                </Link>
                .
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_14px_40px_rgba(0,0,0,0.18)] sm:p-6">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Il Margine file</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Evidence verified: {team.lastUpdatedLabel || "awaiting direct evidence"}</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p className="rounded-xl border border-emerald-400/20 bg-emerald-400/8 px-3 py-2 text-emerald-100">
                {team.leagueLabel} board review run: {team.leagueCheckedLabel || "pending"}. An unchanged evidence date means the order was checked but no stronger event justified rewriting it.
              </p>
              <p>Public file updated: {team.publicUpdatedLabel || "not available"}.</p>
              {team.evidenceSources.length ? (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-slate-100">Evidence checked</p>
                    <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.15em] text-emerald-200">
                      {team.evidenceSources.length} sources reviewed
                    </span>
                  </div>
                  <ul className="mt-2 space-y-2">
                    {team.evidenceSources.slice(0, 4).map((source) => (
                      <li key={source.url} className="rounded-xl border border-slate-800 bg-slate-950/55 px-3 py-2.5">
                        <span className="font-medium text-emerald-300">{source.label}</span>
                        {source.note ? <span className="mt-1 block text-xs leading-5 text-slate-400">{source.note}</span> : null}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    Source URLs are retained in the internal review file so the public page stays focused on the hierarchy.
                  </p>
                </div>
              ) : null}
              <p>
                We update the order only when the evidence changes: penalties taken or missed, lineup context, injuries, suspensions, transfers, coaching comments, or strong league-specific signals.
              </p>
              <p>
                Spot a hierarchy shift? <a href="mailto:contact@ilmargine.bet" className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300">Send it to us</a> and we will tighten the file.
              </p>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 sm:gap-6 xl:grid-cols-[0.95fr,1.05fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_14px_40px_rgba(0,0,0,0.18)] sm:p-6">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">FAQ</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">{team.team} penalty taker FAQ</h2>
            <div className="mt-5 space-y-4">
              <div>
                <h3 className="font-semibold text-slate-100">Who is {team.team}&apos;s penalty taker?</h3>
                <p className="mt-2 text-sm leading-7 text-slate-300">{quickAnswer}</p>
              </div>
              <div>
                <h3 className="font-semibold text-slate-100">Who is {team.team}&apos;s second-choice penalty taker?</h3>
                <p className="mt-2 text-sm leading-7 text-slate-300">{secondAnswer}</p>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_14px_40px_rgba(0,0,0,0.18)] sm:p-6">
            <div className="flex items-start gap-3">
              <MiniLeagueLogo team={team} />
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">More {team.leagueLabel}</div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Related club penalty takers</h2>
              </div>
            </div>
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              {related.map((relatedTeam) => (
                <Link
                  key={relatedTeam.relativeUrl}
                  href={relatedTeam.relativeUrl}
                  className="group flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-950 hover:text-slate-100"
                >
                  <MiniClubLogo team={relatedTeam} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-100 transition group-hover:text-emerald-300">
                      {relatedTeam.team}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-slate-500">{relatedTeam.primary}</span>
                  </span>
                  <span className="text-slate-600 transition group-hover:text-emerald-300" aria-hidden="true">-&gt;</span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-10 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_14px_40px_rgba(0,0,0,0.18)]">
          <div className="text-sm text-slate-300">
            <span className="text-slate-100">Keep moving through {team.leagueLabel}:</span> use the previous and next links or return to the full table.
          </div>
          <div className="flex flex-wrap gap-2">
            {previous ? (
              <Link
                href={previous.relativeUrl}
                className="group inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-950 py-1.5 pr-3 pl-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              >
                <MiniClubLogo team={previous} size="nav" />
                <span>Prev: <span className="font-medium text-slate-100 transition group-hover:text-emerald-300">{previous.team}</span></span>
              </Link>
            ) : null}
            {next ? (
              <Link
                href={next.relativeUrl}
                className="group inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-950 py-1.5 pr-3 pl-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              >
                <MiniClubLogo team={next} size="nav" />
                <span>Next: <span className="font-medium text-slate-100 transition group-hover:text-emerald-300">{next.team}</span></span>
              </Link>
            ) : null}
            <Link
              href={`/penalty-takers/${team.leagueKey}`}
              className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 py-1.5 pr-3 pl-1.5 text-xs text-emerald-100 transition hover:border-emerald-300/40 hover:bg-emerald-400/14"
            >
              <MiniLeagueLogo team={team} />
              <span>All {team.leagueLabel}</span>
            </Link>
            <Link
              href="/penalty-takers/methodology"
              className="inline-flex items-center rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
            >
              How we verify takers
            </Link>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
