import Link from "next/link";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";

type TeamEntry = {
  team: string;
  slug: string;
  primary: string;
  secondary: string;
  tertiary: string;
  lastUpdated: string;
  lastUpdatedLabel: string;
  logoPath: string;
  initials: string;
};

type LeagueEntry = {
  key: string;
  label: string;
  short: string;
  teamCount: number;
  subtitle: string;
  logoPath: string;
  tabClasses: string;
  cardGlowClasses: string;
  heading: string;
  intro: string;
  teams: TeamEntry[];
};

type Props = {
  leagues: LeagueEntry[];
  totalTeams: number;
  currentSeason: string;
  lastUpdatedLabel: string;
  lastUpdatedIso: string;
  recentChanges: {
    team: string;
    slug: string;
    leagueKey: string;
    leagueLabel: string;
    primary: string;
    secondary: string;
    lastUpdated: string;
    lastUpdatedLabel: string;
  }[];
};

function getLeagueDotClass(leagueKey: string): string {
  switch (leagueKey) {
    case "serie-a":
      return "bg-emerald-400";
    case "epl":
      return "bg-indigo-400";
    case "la-liga":
      return "bg-amber-400";
    case "bundesliga":
      return "bg-rose-400";
    case "ligue-1":
      return "bg-cyan-400";
    default:
      return "bg-slate-500";
  }
}

function Crest({
  logoPath,
  team,
  initials,
  size = "club",
}: {
  logoPath: string;
  team: string;
  initials: string;
  size?: "club" | "league";
}) {
  const wrapperClass =
    size === "league"
      ? "flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]"
      : "flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-700/80 bg-slate-900/85";
  const imageClass = size === "league" ? "h-7 w-7 object-contain" : "h-6 w-6 object-contain";

  return (
    <div className={wrapperClass}>
      {logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logoPath} alt={team} className={imageClass} />
      ) : (
        <span className="font-mono text-[11px] font-semibold tracking-tight text-slate-400">{initials}</span>
      )}
    </div>
  );
}

function TeamCard({ team, league }: { team: TeamEntry; league: LeagueEntry }) {
  const anchorId = `${league.key}-${team.slug}`;
  const teamPath = `/penalty-takers/${league.key}/${team.slug}`;
  const takers = [
    { label: "First choice", value: team.primary, tier: "1" as const },
    { label: "Second choice", value: team.secondary, tier: "2" as const },
    { label: "Third choice", value: team.tertiary, tier: "3" as const },
  ].filter((taker) => taker.value);

  return (
    <article
      className={`group scroll-mt-28 rounded-xl border border-slate-800/70 bg-slate-900/55 p-5 shadow-[0_10px_30px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:border-slate-700 hover:bg-slate-900/80 ${league.cardGlowClasses}`}
    >
      <div className="mb-3.5 flex items-start gap-3 border-b border-slate-800/70 pb-3.5">
        <Crest logoPath={team.logoPath} team={team.team} initials={team.initials} />
        <div className="min-w-0 flex-1 pt-0.5">
          <h3 id={anchorId} className="scroll-mt-28 truncate text-[15px] font-semibold tracking-[0.01em] text-slate-100">
            <Link href={teamPath} className="transition hover:text-emerald-400">
              {team.team}
            </Link>
          </h3>
          {team.lastUpdated ? (
            <p className="mt-1 text-[11px] font-mono uppercase tracking-[0.14em] text-slate-500">
              Updated {team.lastUpdatedLabel || team.lastUpdated}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-1">
        {takers.map((taker) => (
          <div key={`${team.team}-${taker.label}`} className="grid grid-cols-[30px_minmax(0,1fr)_auto] items-center gap-3 py-2">
            <div
              className={
                taker.tier === "1"
                  ? "flex h-7 w-7 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 font-mono text-[11px] font-semibold text-emerald-300"
                  : taker.tier === "2"
                    ? "flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700/80 bg-slate-950/80 font-mono text-[11px] font-semibold text-slate-300"
                    : "flex h-7 w-7 items-center justify-center rounded-lg border border-slate-700/80 bg-slate-950/70 font-mono text-[11px] font-semibold text-slate-300"
              }
            >
              {taker.tier}
            </div>
            <span
              className={
                taker.tier === "1"
                  ? "truncate text-[14px] font-medium text-slate-100"
                  : taker.tier === "2"
                    ? "truncate text-[14px] text-slate-300"
                    : "truncate text-[14px] text-slate-300"
              }
            >
              {taker.value}
            </span>
            <span
              className={
                taker.tier === "1"
                  ? "rounded-md bg-emerald-500/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-emerald-300"
                  : taker.tier === "2"
                    ? "rounded-md bg-slate-950/80 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-400"
                    : "rounded-md bg-slate-950/70 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-400"
              }
            >
              {taker.label}
            </span>
          </div>
        ))}
      </div>

      <Link
        href={teamPath}
        className="mt-4 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition hover:border-emerald-300/35 hover:bg-emerald-400/15"
      >
        Open {team.team} page <span aria-hidden="true">-&gt;</span>
      </Link>
    </article>
  );
}

export default function PenaltyTakersClient({
  leagues,
  totalTeams,
  currentSeason,
  lastUpdatedLabel,
  lastUpdatedIso,
  recentChanges,
}: Props) {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-6">
          <Link
            href="/penalty-takers/world-cup-2026"
            className="group block overflow-hidden rounded-[26px] border border-amber-400/20 bg-[linear-gradient(135deg,rgba(20,18,12,0.98),rgba(16,18,24,0.98))] p-5 shadow-[0_18px_50px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:border-amber-300/35"
          >
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-amber-400/20 bg-amber-500/10 text-amber-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src="/world-cup-2026-logo.png"
                    alt="FIFA World Cup 2026 logo"
                    className="h-10 w-10 object-contain"
                  />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-100">World Cup 2026 Penalty Takers</span>
                    <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-300">
                      New
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-400">
                    All qualified nations, full hierarchy, country pages built for tournament search.
                  </p>
                  <div className="mt-2 inline-flex items-center rounded-full border border-amber-300/20 bg-amber-400/8 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-amber-100">
                    11 Jun to 19 Jul 2026
                  </div>
                </div>
              </div>
              <div className="inline-flex items-center gap-2 text-sm font-medium text-amber-200 transition group-hover:translate-x-0.5 group-hover:text-amber-100">
                <span>Open World Cup board</span>
                <span aria-hidden="true">→</span>
              </div>
            </div>
          </Link>
        </section>

        <section className="border-b border-slate-800/50 pt-6 pb-12 md:pt-6 md:pb-16">
          <div className="max-w-4xl">
            <PageHomeLink className="mb-8" />
            <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">IL MARGINE INTELLIGENCE</span>
            <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
              Penalty Takers <span className="text-emerald-400">{currentSeason}</span>
            </h1>
            <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
              First, second and third-choice penalty takers for every club in Europe&apos;s top five leagues.
              Built as a live reference for bettors, fantasy players and anyone who needs the full hierarchy,
              not a stale one-name list from August.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-800/60 bg-slate-900/60 p-5">
                <div className="font-mono text-3xl font-semibold text-emerald-400">{totalTeams}</div>
                <div className="mt-1 text-sm text-slate-400">Teams tracked</div>
              </div>
              <div className="rounded-xl border border-slate-800/60 bg-slate-900/60 p-5">
                <div className="font-mono text-3xl font-semibold text-emerald-400">{leagues.length}</div>
                <div className="mt-1 text-sm text-slate-400">Leagues covered</div>
              </div>
              <div className="rounded-xl border border-slate-800/60 bg-slate-900/60 p-5">
                <div className="font-mono text-3xl font-semibold text-emerald-400">{currentSeason}</div>
                <div className="mt-1 text-sm text-slate-400">Current season</div>
              </div>
            </div>

            <div className="mt-5 inline-flex flex-wrap items-center gap-2 rounded-2xl border border-slate-800/70 bg-slate-900/65 px-4 py-3 text-xs text-slate-300">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </span>
              <span className="font-mono uppercase tracking-[0.18em] text-emerald-300">Latest file edit</span>
              <time dateTime={lastUpdatedIso || undefined}>{lastUpdatedLabel || "Live"}</time>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-[28px] border border-slate-800/70 bg-slate-900/55 p-6 shadow-[0_12px_40px_rgba(0,0,0,0.16)]">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-400">Recent changes</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100">Latest hierarchy updates</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
                The newest team-level edits and re-checks across the five leagues, pulled from the latest club files rather than a full-page reset.
              </p>
            </div>
            <div className="text-right">
              <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">Freshest edit</div>
              <div className="mt-1 text-sm text-slate-300">{lastUpdatedLabel || "Live"}</div>
            </div>
          </div>

          <div className="mt-6 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/70">
            {recentChanges.map((change, index) => (
              <Link
                key={`${change.leagueKey}-${change.slug}-${change.lastUpdated}`}
                href={`/penalty-takers/${change.leagueKey}/${change.slug}`}
                className={`grid grid-cols-[84px_20px_minmax(0,1fr)] items-center gap-3 px-4 py-3 transition hover:bg-slate-900/80 sm:grid-cols-[108px_20px_minmax(0,1fr)] ${index > 0 ? "border-t border-slate-800/80" : ""}`}
              >
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
                  {change.lastUpdatedLabel}
                </span>
                <span className={`h-2.5 w-2.5 rounded-full ${getLeagueDotClass(change.leagueKey)}`} />
                <span className="min-w-0 text-sm leading-6 text-slate-300">
                  <strong className="font-semibold text-slate-100">{change.team}</strong>
                  <span className="text-slate-500"> — </span>
                  <span>{change.primary}</span>
                  {change.secondary && change.secondary !== "TBC" ? (
                    <span className="text-slate-500"> next: {change.secondary}</span>
                  ) : null}
                </span>
              </Link>
            ))}
          </div>
        </section>

        <div className="sticky top-0 z-20 -mx-4 my-10 border-y border-slate-800/70 bg-[#0f1117]/95 px-4 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <nav aria-label="League jump links" className="flex overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
            {leagues.map((league) => (
              <a
                key={league.key}
                href={`#${league.key}`}
                className={`relative whitespace-nowrap border-b-2 px-5 py-4 text-sm font-medium transition ${league.tabClasses} hover:bg-slate-900/40 hover:text-slate-100`}
              >
                <span className="mr-2 inline-flex h-5 w-5 items-center justify-center overflow-hidden rounded-md border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 align-middle shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={league.logoPath} alt={league.label} className="h-3.5 w-3.5 object-contain" />
                </span>
                {league.label}
              </a>
            ))}
          </nav>
        </div>

        <section className="space-y-16">
          {leagues.map((league) => (
            <section key={league.key} id={league.key} className="scroll-mt-28">
              <div className="mb-7 flex items-center gap-4">
                <Crest logoPath={league.logoPath} team={league.label} initials={league.short} size="league" />
                <div>
                  <h2 className="text-3xl font-semibold tracking-tight text-slate-100">{league.heading}</h2>
                  <p className="text-sm text-slate-500">{league.subtitle}</p>
                </div>
              </div>

              <div className="mb-8 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="lg:max-w-4xl">
                  <p className="text-[15px] leading-7 text-slate-300">{league.intro}</p>
                </div>
                <div className="rounded-2xl border border-slate-800/70 bg-slate-900/50 p-4">
                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-400">Jump to team</div>
                  <div className="mt-3 flex flex-wrap items-center text-sm leading-6 text-slate-400">
                    {league.teams.map((team, index) => (
                      <div key={`jump-${league.key}-${team.slug}`} className="contents">
                        <a
                          href={`#${league.key}-${team.slug}`}
                          className="py-0.5 transition hover:text-emerald-300"
                        >
                          {team.team}
                        </a>
                        {index < league.teams.length - 1 ? (
                          <span className="px-2 text-slate-600">·</span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {league.teams.map((team) => (
                  <TeamCard key={`${league.key}-${team.slug}`} team={team} league={league} />
                ))}
              </div>
            </section>
          ))}
        </section>

        <section className="mt-14 border-t border-slate-800/50 py-10">
          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-6">
              <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">Using the hierarchy</div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">Why the full order matters</h2>
              <p className="mt-4 text-[15px] leading-7 text-slate-300">
                The first name is the current likeliest taker. The second and third names matter when the regular
                taker is benched, suspended, injured or substituted. That is usually where a quick one-name list
                stops being useful.
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-6">
              <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">When it changes</div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">Only on real evidence</h2>
              <p className="mt-4 text-[15px] leading-7 text-slate-300">
                We only move a team when the hierarchy actually changes on the pitch or in the squad context:
                penalties taken, penalties missed, injuries, suspensions, transfers, coach decisions or strong
                league-specific reporting.
              </p>
            </div>
          </div>

          <div className="mt-5 px-1 text-sm leading-6 text-slate-400">
            Need the international board too?{" "}
            <Link
              href="/penalty-takers/world-cup-2026"
              className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300"
            >
              World Cup 2026 penalty takers
            </Link>
            .{" "}
          </div>

          <div className="mt-2 px-1 text-sm leading-6 text-slate-400">
            Spot an error or a hierarchy shift?{" "}
            <a href="mailto:contact@ilmargine.bet" className="border-b border-emerald-500/30 text-emerald-400 hover:text-emerald-300">
              Let us know
            </a>{" "}
            and we&apos;ll tighten the reference.
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}

