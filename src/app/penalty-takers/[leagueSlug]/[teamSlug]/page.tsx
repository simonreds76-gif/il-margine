import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import { BASE_URL } from "@/lib/config";
import {
  CLUB_PENALTY_SEASON,
  CLUB_PENALTY_PREVIOUS_SEASON,
  buildClubPenaltyConditionSummary,
  buildClubPenaltyDescription,
  buildClubPenaltyFaq,
  buildClubPenaltyHierarchyNote,
  buildClubPenaltyLead,
  buildClubPenaltyTitle,
  buildClubPenaltyWatchNote,
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
  const conditionSummary = buildClubPenaltyConditionSummary(team);
  const watchNote = buildClubPenaltyWatchNote(team);
  const latestEvidenceUpdate = team.evidenceUpdates[0];
  const hierarchyLabels = ["Current primary", "Second choice", "Third choice"];
  const hierarchyNote = buildClubPenaltyHierarchyNote(team);
  const faqItems = buildClubPenaltyFaq(team);
  const isUnderReview = ["unknown", "disputed", "conditional"].includes(team.hierarchyStatus);
  const hierarchyPositions = ["primary", "secondary", "tertiary"] as const;
  const checkedLabel = team.checkedLabel || team.leagueCheckedLabel || "review pending";
  const evidenceFreshness = team.lastUpdatedLabel && team.lastUpdated !== team.checkedAt
    ? `Order unchanged since ${team.lastUpdatedLabel}`
    : team.lastUpdatedLabel
      ? `Hierarchy updated ${team.lastUpdatedLabel}`
      : "Awaiting hierarchy-changing evidence";

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

  const faqData = team.isArchived ? null : {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqItems.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(pageData) }} />
      {faqData ? <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqData) }} /> : null}

      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pb-9 pt-6 sm:pb-12">
          <PageHomeLink className="mb-8" />

          <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-slate-400">
            <Link href="/penalty-takers" className="hover:text-slate-100">Penalty Takers</Link>
            <span>/</span>
            <Link href={`/penalty-takers/${team.leagueKey}`} className="hover:text-slate-100">{team.leagueLabel}</Link>
            <span>/</span>
            <span className="text-slate-200">{team.team}</span>
          </div>

          <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
            <article className={`overflow-hidden rounded-2xl border border-slate-800 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.08),transparent_36%),#10151f] p-5 sm:p-7 lg:p-8 ${accent.glow}`}>
              <div className="flex items-start justify-between gap-4">
                <Crest team={team} />
                <div className="flex flex-wrap justify-end gap-2">
                  <span className={`inline-flex items-center rounded-full border px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] ${accent.badge}`}>
                    <LeagueLogo team={team} /> <span className="ml-2">{team.leagueLabel}</span>
                  </span>
                  <span className="rounded-full border border-slate-700 bg-slate-950/80 px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                    {team.seasonLabel}
                  </span>
                </div>
              </div>

              <h1 className="mt-6 text-[2.15rem] font-semibold leading-[1.02] tracking-tight text-white sm:text-5xl">
                {team.team} <span className={accent.text}>penalty taker</span>
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-200 sm:text-lg sm:leading-8">{lead}</p>

              {team.isArchived ? (
                <p className="mt-5 rounded-2xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm leading-6 text-slate-300">
                  Archived record: {team.team} are not on the current {team.leagueLabel} board. This page preserves the final {team.seasonLabel} hierarchy and URL.
                </p>
              ) : conditionSummary ? (
                <div className={`mt-6 border-l-2 pl-4 ${isUnderReview ? "border-amber-300" : "border-emerald-300"}`}>
                  <div className={`font-mono text-[10px] font-semibold uppercase tracking-[0.2em] ${isUnderReview ? "text-amber-200" : "text-emerald-300"}`}>
                    {isUnderReview ? "Order under review" : "Why this order stands"}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-200">{conditionSummary}</p>
                  {team.conditionNote !== conditionSummary ? (
                    <details className="mt-3 text-xs text-slate-400">
                      <summary className="cursor-pointer font-semibold text-slate-300 hover:text-white">Full evidence note</summary>
                      <p className="mt-2 leading-6 text-slate-300">{team.conditionNote}</p>
                    </details>
                  ) : null}
                </div>
              ) : team.isCarryover ? (
                <p className="mt-5 border-l-2 border-cyan-300 pl-4 text-sm leading-6 text-cyan-100">
                  Provisional carryover from the final {CLUB_PENALTY_PREVIOUS_SEASON} order. It is being re-verified through the opening weeks.
                </p>
              ) : null}

              {!team.isArchived ? (
                <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-800 pt-4 text-xs text-slate-400">
                  <span className="font-semibold text-emerald-300">Checked {checkedLabel}</span>
                  <span className="hidden text-slate-600 sm:inline">/</span>
                  <span>{evidenceFreshness}</span>
                </div>
              ) : null}
            </article>

            <aside className={`rounded-2xl border border-slate-700/80 bg-slate-900 p-4 shadow-[0_18px_50px_rgba(0,0,0,0.24)] sm:p-5 lg:sticky lg:top-5`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-slate-400">Filed order</div>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight text-white">Penalty hierarchy</h2>
                </div>
                <span className={`rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] ${isUnderReview ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"}`}>
                  {isUnderReview ? "Reviewing" : "Current"}
                </span>
              </div>

              <ol className="mt-4 space-y-2.5">
                {team.verifiedNames.map((value, index) => {
                  const rank = index + 1;
                  const confidence = team.confidence[hierarchyPositions[index]];
                  const confidenceLabel = confidence === "high" ? "Confirmed" : confidence === "medium" ? "Probable" : confidence === "low" ? "Projected" : "";
                  return (
                    <li key={`${rank}-${value}`} className={`rounded-xl border p-3.5 ${rank === 1 ? "border-emerald-300/30 bg-emerald-300/[0.07]" : "border-slate-800 bg-slate-950/55"}`}>
                      <div className="flex items-center gap-3">
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-mono text-sm font-bold ${rank === 1 ? `${accent.fill} text-slate-950` : "border border-slate-700 bg-slate-900 text-slate-300"}`}>
                          {rank}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[9px] uppercase tracking-[0.16em] text-slate-400">{hierarchyLabels[index]}</span>
                          <strong className={`mt-1 block truncate text-base font-semibold ${rank === 1 ? accent.text : "text-slate-100"}`}>{value}</strong>
                        </span>
                        {confidenceLabel ? (
                          <span className="shrink-0 rounded-full border border-slate-700 px-2 py-1 text-[9px] font-medium text-slate-300">{confidenceLabel}</span>
                        ) : null}
                      </div>
                    </li>
                  );
                })}
                {!team.isArchived && team.hierarchyDepth < 3 ? (
                  <li className="rounded-xl border border-dashed border-slate-700 bg-slate-950/30 p-3.5 text-sm text-slate-400">
                    Position {team.hierarchyDepth + 1} remains open; no unsupported name is inserted.
                  </li>
                ) : null}
              </ol>
              <p className="mt-4 border-t border-slate-800 pt-4 text-xs leading-5 text-slate-400">{hierarchyNote}</p>
              {watchNote ? (
                <div className={`mt-4 rounded-xl border px-3.5 py-3 text-xs leading-5 ${isUnderReview ? "border-amber-300/25 bg-amber-300/[0.07] text-amber-50" : "border-slate-700 bg-slate-950/60 text-slate-300"}`}>
                  <strong className={isUnderReview ? "text-amber-200" : "text-slate-100"}>Watch next:</strong> {watchNote}
                </div>
              ) : null}
            </aside>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/65 p-5 sm:p-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400">Evidence file</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">How we verified {team.team}&apos;s penalty order</h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Checked <strong className="font-semibold text-emerald-300">{checkedLabel}</strong>. {evidenceFreshness}.
            </p>
            <div className="mt-5 space-y-4 text-sm leading-7 text-slate-300">
              {latestEvidenceUpdate ? (
                <div className="rounded-xl border border-slate-700 bg-slate-950/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-emerald-300">Latest hierarchy evidence</span>
                    <span className="text-xs text-slate-400">{latestEvidenceUpdate.dateLabel}</span>
                  </div>
                  <h3 className="mt-2 font-semibold text-slate-100">{latestEvidenceUpdate.headline}</h3>
                  {latestEvidenceUpdate.match ? <p className="mt-1 text-xs font-medium text-slate-300">{latestEvidenceUpdate.match}</p> : null}
                  <p className="mt-2 text-sm leading-6 text-slate-300">{latestEvidenceUpdate.summary}</p>
                  {latestEvidenceUpdate.fullSummary !== latestEvidenceUpdate.summary ? (
                    <details className="mt-3 text-xs text-slate-400">
                      <summary className="cursor-pointer font-semibold text-emerald-300 hover:text-emerald-200">Full evidence context</summary>
                      <p className="mt-2 leading-6 text-slate-300">{latestEvidenceUpdate.fullSummary}</p>
                    </details>
                  ) : null}
                </div>
              ) : null}
              {team.evidenceSources.length ? (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium text-slate-100">Sources checked</p>
                    <span className="rounded-full border border-slate-700 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.14em] text-slate-300">
                      {Math.min(team.evidenceSources.length, 4)} sources shown
                    </span>
                  </div>
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                    {team.evidenceSources.slice(0, 4).map((source) => (
                      <li key={source.url} className="rounded-xl border border-slate-800 bg-slate-950/55 px-3 py-3">
                        <span className="font-medium text-slate-100">{source.label}</span>
                        {source.note ? <span className="mt-1 block text-xs leading-5 text-slate-400">{source.note}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p className="border-t border-slate-800 pt-4 text-xs leading-5 text-slate-400">{team.leagueCopy} Source URLs remain in the internal audit file so this page keeps readers focused on the current decision.</p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/65 p-5 sm:p-6">
            <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400">Quick reference</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">{team.team} penalty taker FAQ</h2>
            <div className="mt-5 divide-y divide-slate-800">
              {faqItems.map((item) => (
                <div key={item.question} className="py-4 first:pt-0 last:pb-0">
                  <h3 className="font-semibold text-slate-100">{item.question}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{item.answer}</p>
                </div>
              ))}
            </div>
            <p className="mt-5 border-t border-slate-800 pt-4 text-sm leading-6 text-slate-300">
              For live goalscorer pricing, compare the filed order with the{" "}
              <Link href="/fair-odds-lab" className="font-semibold text-emerald-300 hover:text-emerald-200">Goalscorer Fair Odds Lab</Link>.
            </p>
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/65 p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <MiniLeagueLogo team={team} />
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400">More {team.leagueLabel}</div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Related club penalty takers</h2>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-4">
              {related.map((relatedTeam) => (
                <Link
                  key={relatedTeam.relativeUrl}
                  href={relatedTeam.relativeUrl}
                  className="group flex min-w-0 items-center gap-2.5 rounded-xl border border-slate-800 bg-slate-950/70 px-2.5 py-2.5 text-sm text-slate-300 transition hover:border-slate-600 hover:bg-slate-950 hover:text-slate-100 sm:px-3"
                >
                  <MiniClubLogo team={relatedTeam} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-100 transition group-hover:text-emerald-300">
                      {relatedTeam.team}
                    </span>
                    <span className="mt-0.5 block truncate text-xs text-slate-400">{relatedTeam.primary}</span>
                  </span>
                </Link>
              ))}
            </div>
        </section>

        <section className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/65 p-4 sm:p-5">
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
