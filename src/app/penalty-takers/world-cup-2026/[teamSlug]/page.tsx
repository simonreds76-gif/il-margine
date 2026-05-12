import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
import FlagMark from "@/components/FlagMark";
import PageHomeLink from "@/components/PageHomeLink";
import {
  WORLD_CUP_PENALTIES_URL,
  buildWorldCupTeamDescription,
  buildWorldCupTeamLead,
  buildWorldCupTeamTitle,
  CONFEDERATION_ORDER,
  flagImageUrl,
  getWorldCupTeamBySlug,
  initials,
  readWorldCupData,
  worldCupTeamSlug,
  worldCupTeamUrl,
} from "@/lib/world-cup-penalties";
import { BASE_URL } from "@/lib/config";

type PageProps = {
  params: Promise<{
    teamSlug: string;
  }>;
};

const CONFEDERATION_STYLES: Record<
  string,
  { badge: string; surface: string; band: string; primary: string; secondary: string; accent: string }
> = {
  UEFA: {
    badge: "border-sky-400/30 bg-sky-400/10 text-sky-200",
    surface: "from-sky-500/22 via-sky-400/8 to-slate-950",
    band: "from-sky-400 via-sky-500/70 to-slate-950",
    primary: "text-sky-100",
    secondary: "text-sky-200",
    accent: "bg-sky-300",
  },
  CONMEBOL: {
    badge: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
    surface: "from-emerald-500/22 via-emerald-400/8 to-slate-950",
    band: "from-emerald-400 via-emerald-500/70 to-slate-950",
    primary: "text-emerald-100",
    secondary: "text-emerald-200",
    accent: "bg-emerald-300",
  },
  Concacaf: {
    badge: "border-cyan-400/30 bg-cyan-400/10 text-cyan-200",
    surface: "from-cyan-500/22 via-cyan-400/8 to-slate-950",
    band: "from-cyan-400 via-cyan-500/70 to-slate-950",
    primary: "text-cyan-100",
    secondary: "text-cyan-200",
    accent: "bg-cyan-300",
  },
  AFC: {
    badge: "border-amber-400/30 bg-amber-400/10 text-amber-100",
    surface: "from-amber-500/22 via-amber-400/8 to-slate-950",
    band: "from-amber-300 via-amber-500/70 to-slate-950",
    primary: "text-amber-50",
    secondary: "text-amber-200",
    accent: "bg-amber-300",
  },
  CAF: {
    badge: "border-rose-400/30 bg-rose-400/10 text-rose-200",
    surface: "from-rose-500/22 via-rose-400/8 to-slate-950",
    band: "from-rose-400 via-rose-500/70 to-slate-950",
    primary: "text-rose-100",
    secondary: "text-rose-200",
    accent: "bg-rose-300",
  },
  OFC: {
    badge: "border-violet-400/30 bg-violet-400/10 text-violet-200",
    surface: "from-violet-500/22 via-violet-400/8 to-slate-950",
    band: "from-violet-400 via-violet-500/70 to-slate-950",
    primary: "text-violet-100",
    secondary: "text-violet-200",
    accent: "bg-violet-300",
  },
};

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "source";
  }
}

export async function generateStaticParams() {
  const data = await readWorldCupData();
  return data.teams.map((team) => ({
    teamSlug: worldCupTeamSlug(team.team),
  }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { teamSlug } = await params;
  const data = await readWorldCupData();
  const team = getWorldCupTeamBySlug(data, teamSlug);

  if (!team) {
    return {
      title: "World Cup penalty taker",
    };
  }

  const title = buildWorldCupTeamTitle(team);
  const description = buildWorldCupTeamDescription(team);
  const url = worldCupTeamUrl(team.team);

  return {
    title,
    description,
    alternates: {
      canonical: url,
    },
    keywords: [
      `${team.team} penalty taker`,
      `who is ${team.team} penalty taker`,
      `${team.team} world cup penalty taker`,
      `${team.team} penalty taker world cup 2026`,
      `${team.team} world cup 2026 penalties`,
      `${team.team} first choice penalty taker`,
      `who takes penalties for ${team.team}`,
      `${team.team} likely penalty taker`,
      `${team.team} penalty takers`,
    ],
    openGraph: {
      type: "article",
      title: `${title} | Il Margine`,
      description,
      url,
      siteName: "Il Margine",
      images: [
        {
          url: `${BASE_URL}/banner.png`,
          width: 1200,
          height: 400,
          alt: `${team.team} penalty taker for World Cup 2026`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} | Il Margine`,
      description,
      images: [`${BASE_URL}/banner.png`],
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default async function WorldCupTeamPenaltyPage({ params }: PageProps) {
  const { teamSlug } = await params;
  const data = await readWorldCupData();
  const team = getWorldCupTeamBySlug(data, teamSlug);

  if (!team) {
    notFound();
  }

  const title = buildWorldCupTeamTitle(team);
  const description = buildWorldCupTeamDescription(team);
  const pageUrl = worldCupTeamUrl(team.team);
  const heroFlagUrl = flagImageUrl(team.team);
  const style = CONFEDERATION_STYLES[team.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
  const primary = team.likely_primary?.trim();
  const secondary = team.likely_secondary?.trim();
  const groupMates = team.group
    ? data.teams
        .filter((candidate) => candidate.group === team.group && candidate.team !== team.team)
        .sort((left, right) => left.team.localeCompare(right.team, "en"))
    : [];
  const peers = data.teams
    .filter((candidate) => candidate.confederation === team.confederation && candidate.team !== team.team)
    .sort((left, right) => left.team.localeCompare(right.team, "en"))
    .slice(0, 8);

  const previousAndNext = (() => {
    const ordered = CONFEDERATION_ORDER.flatMap((confed) =>
      data.teams
        .filter((candidate) => candidate.confederation === confed)
        .sort((left, right) => left.team.localeCompare(right.team, "en")),
    );
    const index = ordered.findIndex((candidate) => candidate.team === team.team);
    return {
      previous: index > 0 ? ordered[index - 1] : undefined,
      next: index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : undefined,
    };
  })();

  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: BASE_URL },
      { "@type": "ListItem", position: 2, name: "Penalty Takers", item: `${BASE_URL}/penalty-takers` },
      { "@type": "ListItem", position: 3, name: "FIFA World Cup 2026 Penalty Takers", item: WORLD_CUP_PENALTIES_URL },
      { "@type": "ListItem", position: 4, name: team.team, item: pageUrl },
    ],
  };

  const pageData = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: title,
    description,
    url: pageUrl,
    about: {
      "@type": "SportsTeam",
      name: team.team,
      sport: "Association football",
    },
    isPartOf: {
      "@type": "CollectionPage",
      name: "FIFA World Cup 2026 Penalty Takers",
      url: WORLD_CUP_PENALTIES_URL,
    },
  };

  const quickAnswer = !primary
    ? `We are still researching ${team.team}'s penalty order for World Cup 2026 and need another clean senior signal before naming a first-choice taker.`
    : secondary
      ? `${primary} is our current ${team.team} penalty taker call, with ${secondary} next in line if the order changes.`
      : `${primary} is our current ${team.team} penalty taker call. We do not name a firm backup yet because the secondary order is still too thin or too mixed.`;

  const worldCupAnswer = !primary
    ? `Right now we are not willing to publish a firmer World Cup 2026 penalty order for ${team.team} until the evidence file tightens.`
    : secondary
      ? `For World Cup 2026, ${primary} is the current first-choice call for ${team.team}, with ${secondary} the closest backup if the tournament order shifts.`
      : `For World Cup 2026, ${primary} is the current first-choice call for ${team.team}. The backup line stays open because the next layer of evidence is still mixed.`;

  const faqData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: `Who is ${team.team}'s penalty taker?`,
        acceptedAnswer: {
          "@type": "Answer",
          text: quickAnswer,
        },
      },
      {
        "@type": "Question",
        name: `Who takes penalties for ${team.team} at World Cup 2026?`,
        acceptedAnswer: {
          "@type": "Answer",
          text: worldCupAnswer,
        },
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
            <Link href="/penalty-takers" className="hover:text-slate-100">
              Penalty Takers
            </Link>
            <span>/</span>
            <Link href="/penalty-takers/world-cup-2026" className="hover:text-slate-100">
              World Cup 2026
            </Link>
            <span>/</span>
            <span className="text-slate-200">{team.team}</span>
          </div>

          <div className="relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-[linear-gradient(160deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] shadow-[0_18px_48px_rgba(0,0,0,0.24)] sm:shadow-[0_28px_80px_rgba(0,0,0,0.28)]">
            <div className={`pointer-events-none absolute inset-x-0 top-0 h-16 sm:h-28 bg-gradient-to-r ${style.band}`} />
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -left-6 top-0 hidden h-44 w-44 rounded-full bg-emerald-400/10 blur-3xl sm:block" />
              <div className="absolute right-0 top-8 hidden h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl sm:block" />
              <div className="absolute right-8 top-4 hidden text-[120px] font-semibold tracking-[-0.08em] text-white/5 xl:block">
                {initials(team.team)}
              </div>
            </div>

            <div className="relative p-4 pt-16 sm:p-8 sm:pt-28 lg:p-10 lg:pt-32">
              <div className="grid gap-8 xl:grid-cols-[1.08fr,0.92fr] xl:items-start">
                <div className="max-w-4xl">
                  <div className="flex flex-col items-start gap-4 sm:flex-row">
                    <FlagMark
                      src={heroFlagUrl}
                      alt={`${team.team} flag`}
                      fallbackText={initials(team.team)}
                      wrapperClassName="flex h-16 w-16 shrink-0 items-center justify-center rounded-[20px] border border-slate-700/80 bg-slate-950/90 shadow-[0_12px_30px_rgba(0,0,0,0.18)] sm:h-20 sm:w-20 sm:rounded-[24px]"
                      imageClassName="h-9 w-11 rounded-[6px] object-cover shadow-sm sm:h-11 sm:w-14"
                      fallbackClassName="font-mono text-base font-semibold text-slate-200"
                      width={56}
                      height={44}
                      sizes="(min-width: 640px) 56px, 44px"
                      priority
                    />
                    <div className="min-w-0">
                      <h1 className="text-[2.1rem] font-semibold leading-[0.98] tracking-tight text-slate-100 sm:text-5xl sm:leading-[1.02]">
                        {team.team} <span className="text-emerald-400">penalty taker</span>
                      </h1>
                      <p className="mt-4 max-w-3xl text-[15px] leading-7 text-slate-300 sm:text-lg sm:leading-8">
                        {buildWorldCupTeamLead(team)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-2">
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-300 sm:text-[10px] sm:tracking-[0.18em]">
                      World Cup penalty board
                    </span>
                    <span className={`rounded-full border px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] sm:text-[10px] sm:tracking-[0.18em] ${style.badge}`}>
                      {team.confederation}
                    </span>
                    {team.group ? (
                      <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300 sm:text-xs sm:tracking-[0.18em]">
                        Group {team.group}
                      </span>
                    ) : null}
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300 sm:text-xs sm:tracking-[0.18em]">
                      Current file: {data.last_verified}
                    </span>
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[10px] text-slate-400 sm:text-xs">
                      {team.source_urls?.length ?? 0} sources reviewed
                    </span>
                  </div>
                </div>

                <aside className={`overflow-hidden rounded-3xl border border-slate-800/80 bg-gradient-to-br p-4 shadow-[0_14px_36px_rgba(0,0,0,0.18)] sm:p-5 sm:shadow-[0_22px_60px_rgba(0,0,0,0.22)] ${style.surface}`}>
                  <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-slate-300">Penalty hierarchy</div>

                  <div className="mt-4 space-y-3">
                    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-slate-950/45 font-mono text-base font-semibold text-slate-100">
                          1
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Current primary</div>
                          <div className={`mt-1.5 text-2xl font-semibold tracking-tight ${team.likely_primary ? style.primary : "text-slate-200"}`}>
                            {team.likely_primary || "Board still building"}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                      <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-slate-950/45 font-mono text-base font-semibold text-slate-300">
                          2
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Closest challenger</div>
                          <div className={`mt-1.5 text-xl font-semibold tracking-tight ${team.likely_secondary ? style.secondary : "text-slate-400"}`}>
                            {team.likely_secondary || "Not strong enough to name yet"}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-950/35 p-4">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Latest key evidence</div>
                      <div className="mt-1.5 text-sm leading-6 text-slate-200">
                        {team.last_evidence || "Evidence file still being built from the current cycle."}
                      </div>
                    </div>
                  </div>
                </aside>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-2 grid gap-4 sm:gap-6 xl:grid-cols-[1.08fr,0.92fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Quick Answer</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Who is {team.team}&apos;s penalty taker?</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>{quickAnswer}</p>
              <p>{team.note}</p>
              <p>
                If you searched for <span className="text-slate-100">{team.team} penalty taker</span>, the hierarchy
                at the top is the quickest answer we are willing to publish right now. The evidence trail underneath
                shows why that order makes the cut.
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Tournament Context</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Who takes penalties for {team.team} at World Cup 2026?</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>{worldCupAnswer}</p>
              <p>A fresh in-match penalty can move this page quickly, especially if it contradicts the current lead or happens with the full-strength tournament pool on the pitch.</p>
              <p>For the more conditional boards, one more clean senior penalty is often enough to sharpen the backup line or flip the order outright.</p>
              <p>
                Spot a hierarchy shift, a squad-specific wrinkle or a better local source?{" "}
                <a href="mailto:contact@ilmargine.bet" className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300">
                  Contact us here
                </a>
                . If you are close to the {team.team} setup and have stronger information, that is exactly the kind of update we want.
              </p>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 sm:gap-6 xl:grid-cols-[1.02fr,0.98fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Evidence Trail</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Why the board looks like this</h2>
            <div className="mt-5 space-y-4">
              {(team.evidence_log?.length ? team.evidence_log : ["Evidence trail still being built."]).map((entry, index) => (
                <div key={`${team.team}-${entry}`} className="flex gap-3">
                  <div
                    className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold ${
                      index === 0
                        ? "border-emerald-300 bg-emerald-300 text-[#04110d] shadow-[0_0_0_1px_rgba(16,185,129,0.18)]"
                        : "border-slate-700 bg-slate-900 text-slate-300"
                    }`}
                  >
                    {index + 1}
                  </div>
                  <div className="text-sm leading-7 text-slate-300">{entry}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
              <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Sources Reviewed</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Primary trail and supporting checks</h2>
              <div className="mt-5 flex flex-wrap gap-2.5">
                {(team.source_urls?.length ? team.source_urls : []).map((url) => (
                  <a
                    key={url}
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
                  >
                    {hostname(url)}
                  </a>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
              <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Related Pages</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">More routes through the field</h2>
              {groupMates.length > 0 ? (
                <div className="mt-5">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    Group {team.group}
                  </div>
                  <div className="mt-3 grid gap-2">
                    {groupMates.map((mate) => (
                      <Link
                        key={`group-${mate.team}`}
                        href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(mate.team)}`}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
                      >
                        <span className="font-medium text-slate-100">{mate.team} penalty taker</span>
                        <span className="truncate text-xs text-slate-400">{mate.likely_primary || "Building"}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className={groupMates.length > 0 ? "mt-6" : "mt-5"}>
                <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                  More from {team.confederation}
                </div>
                <div className="mt-3 flex flex-wrap gap-2.5">
                  {peers.map((peer) => (
                    <Link
                      key={peer.team}
                      href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(peer.team)}`}
                      className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
                    >
                      {peer.team} penalty taker
                    </Link>
                  ))}
                </div>
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  href="/penalty-takers/world-cup-2026"
                  className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:border-emerald-300/40 hover:bg-emerald-400/14"
                >
                  Back to World Cup penalty takers
                </Link>
                <Link
                  href="/penalty-takers"
                  className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
                >
                  Club penalty takers
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-10 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
          <div className="text-sm text-slate-300">
            <span className="text-slate-100">Keep moving through the board:</span> the team pages are ordered so the whole
            World Cup field is easy to review country by country.
          </div>
          <div className="flex flex-wrap gap-2">
            {previousAndNext.previous ? (
              <Link
                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(previousAndNext.previous.team)}`}
                className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
              >
                Prev: {previousAndNext.previous.team} penalty taker
              </Link>
            ) : null}
            {previousAndNext.next ? (
              <Link
                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(previousAndNext.next.team)}`}
                className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
              >
                Next: {previousAndNext.next.team} penalty taker
              </Link>
            ) : null}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
