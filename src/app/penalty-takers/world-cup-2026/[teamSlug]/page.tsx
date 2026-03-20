import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
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
      title: "World Cup penalty taker | Il Margine",
    };
  }

  const title = buildWorldCupTeamTitle(team);
  const description = buildWorldCupTeamDescription(team);
  const url = worldCupTeamUrl(team.team);

  return {
    title: `${title} | Il Margine`,
    description,
    alternates: {
      canonical: url,
    },
    keywords: [
      `${team.team} penalty taker`,
      `${team.team} world cup penalty taker`,
      `${team.team} world cup 2026 penalties`,
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
          alt: `${team.team} World Cup 2026 penalty takers`,
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
  const style = CONFEDERATION_STYLES[team.confederation] ?? CONFEDERATION_STYLES.CONMEBOL;
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

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(pageData) }} />

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

          <div className="relative overflow-hidden rounded-[32px] border border-slate-800/80 bg-[linear-gradient(160deg,rgba(4,10,18,0.98),rgba(6,22,20,0.96))] shadow-[0_28px_80px_rgba(0,0,0,0.28)]">
            <div className={`pointer-events-none absolute inset-x-0 top-0 h-24 sm:h-28 bg-gradient-to-r ${style.band}`} />
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute -left-6 top-0 h-44 w-44 rounded-full bg-emerald-400/10 blur-3xl" />
              <div className="absolute right-0 top-8 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
              <div className="absolute right-8 top-4 hidden text-[120px] font-semibold tracking-[-0.08em] text-white/5 xl:block">
                {initials(team.team)}
              </div>
            </div>

            <div className="relative p-6 pt-24 sm:p-8 sm:pt-28 lg:p-10 lg:pt-32">
              <div className="grid gap-8 xl:grid-cols-[1.08fr,0.92fr] xl:items-start">
                <div className="max-w-4xl">
                  <div className="flex items-start gap-4">
                    <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[24px] border border-slate-700/80 bg-slate-950/90 shadow-[0_12px_30px_rgba(0,0,0,0.18)]">
                      {flagImageUrl(team.team) ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={flagImageUrl(team.team)}
                          alt={`${team.team} flag`}
                          className="h-11 w-14 rounded-[6px] object-cover shadow-sm"
                        />
                      ) : (
                        <span className="font-mono text-base font-semibold text-slate-200">{initials(team.team)}</span>
                      )}
                    </div>
                    <div>
                      <h1 className="text-3xl font-semibold tracking-tight text-slate-100 sm:text-5xl sm:leading-[1.02]">
                        {team.team} <span className="text-emerald-400">penalty taker</span>
                      </h1>
                      <p className="mt-4 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
                        {buildWorldCupTeamLead(team)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex flex-wrap gap-2">
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                      World Cup 2026 team page
                    </span>
                    <span className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] ${style.badge}`}>
                      {team.confederation}
                    </span>
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
                      Current file: {data.last_verified}
                    </span>
                    <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-400">
                      {team.source_urls?.length ?? 0} sources reviewed
                    </span>
                  </div>
                </div>

                <aside className={`overflow-hidden rounded-3xl border border-slate-800/80 bg-gradient-to-br p-5 shadow-[0_22px_60px_rgba(0,0,0,0.22)] ${style.surface}`}>
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

        <section className="mt-2 grid gap-6 xl:grid-cols-[1.08fr,0.92fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Evidence And Context</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">{team.team} at a glance</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>{team.note}</p>
              <p>
                This page is built for the specific country query. If someone is searching for{" "}
                <span className="text-slate-100">{team.team} penalty taker</span>, this is the cleanest World Cup
                read we are willing to publish right now.
              </p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
            <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">What Moves It</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">What would move the order?</h2>
            <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
              <p>A fresh in-match penalty can change this page quickly, especially if it contradicts the current lead or happens with the full-strength tournament pool on the pitch.</p>
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

        <section className="mt-8 grid gap-6 xl:grid-cols-[1.02fr,0.98fr]">
          <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
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
            <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
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

            <div className="rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
              <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Related Pages</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">More from the same confederation</h2>
              <div className="mt-5 flex flex-wrap gap-2.5">
                {peers.map((peer) => (
                  <Link
                    key={peer.team}
                    href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(peer.team)}`}
                    className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
                  >
                    {peer.team}
                  </Link>
                ))}
              </div>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  href="/penalty-takers/world-cup-2026"
                  className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-100 hover:border-emerald-300/40 hover:bg-emerald-400/14"
                >
                  Back to full World Cup board
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

        <section className="mt-10 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
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
                Prev: {previousAndNext.previous.team}
              </Link>
            ) : null}
            {previousAndNext.next ? (
              <Link
                href={`/penalty-takers/world-cup-2026/${worldCupTeamSlug(previousAndNext.next.team)}`}
                className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-slate-100"
              >
                Next: {previousAndNext.next.team}
              </Link>
            ) : null}
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
