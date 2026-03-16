import Footer from "@/components/Footer";

type TeamEntry = {
  team: string;
  slug: string;
  primary: string;
  secondary: string;
  tertiary: string;
  lastUpdated: string;
  logoPath: string;
  initials: string;
};

type LeagueEntry = {
  key: string;
  label: string;
  short: string;
  teamCount: number;
  updatedLabel: string;
  logoPath: string;
  tabClasses: string;
  cardGlowClasses: string;
  heading: string;
  summary: string;
  paragraphs: string[];
  teams: TeamEntry[];
};

type ChangeItem = {
  date: string;
  league: string;
  team: string;
  summary: string;
  href: string;
};

type Props = {
  leagues: LeagueEntry[];
  totalTeams: number;
  serifClass: string;
  monoClass: string;
  recentChanges: ChangeItem[];
  currentSeason: string;
};

function Crest({
  logoPath,
  team,
  initials,
  monoClass,
  size = "club",
}: {
  logoPath: string;
  team: string;
  initials: string;
  monoClass: string;
  size?: "club" | "league";
}) {
  const outerClass =
    size === "league"
      ? "flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-stone-200/70 bg-gradient-to-b from-white to-stone-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]"
      : "flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-stone-200/60 bg-gradient-to-b from-white to-stone-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)]";
  const imgClass = size === "league" ? "h-7 w-7 object-contain" : "h-6 w-6 object-contain";

  return (
    <div className={outerClass}>
      {logoPath ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={logoPath} alt={team} className={imgClass} />
      ) : (
        <span className={`${monoClass} text-[11px] font-semibold tracking-tight text-stone-500`}>{initials}</span>
      )}
    </div>
  );
}

function TeamCard({
  team,
  league,
  monoClass,
}: {
  team: TeamEntry;
  league: LeagueEntry;
  monoClass: string;
}) {
  const takers = [
    { label: "Primary", value: team.primary, tier: "1" as const },
    { label: "Secondary", value: team.secondary, tier: "2" as const },
    ...(team.tertiary ? [{ label: "Tertiary", value: team.tertiary, tier: "3" as const }] : []),
  ];

  return (
    <article
      id={`${league.key}-${team.slug}`}
      className={`group scroll-mt-28 relative overflow-hidden rounded-2xl border border-white/7 bg-[#0b0b0b] p-5 transition duration-300 hover:-translate-y-0.5 hover:border-white/12 hover:bg-[#101010] ${league.cardGlowClasses}`}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-white/35 via-white/10 to-transparent opacity-0 transition duration-300 group-hover:opacity-100" />

      <div className="mb-4 flex items-start gap-3 border-b border-white/6 pb-4">
        <Crest logoPath={team.logoPath} team={team.team} initials={team.initials} monoClass={monoClass} />
        <div className="min-w-0 flex-1 pt-1">
          <a href={`#${league.key}-${team.slug}`} className="truncate text-[15px] font-semibold tracking-[0.02em] text-stone-100 hover:text-emerald-300">
            {team.team}
          </a>
        </div>
        <div className={`shrink-0 rounded-md border border-white/6 bg-white/[0.03] px-2 py-1 ${monoClass} text-[9px] uppercase tracking-[0.16em] text-stone-500`}>
          {team.lastUpdated}
        </div>
      </div>

      <div className="space-y-1.5">
        {takers.map((taker) => (
          <div
            key={`${team.team}-${taker.label}`}
            className="grid grid-cols-[30px_minmax(0,1fr)_auto] items-center gap-3 py-2.5"
          >
            <div
              className={
                taker.tier === "1"
                  ? `flex h-7 w-7 items-center justify-center rounded-[10px] border border-[#d4a853]/25 bg-gradient-to-br from-[#2b2009] to-[#181208] ${monoClass} text-[11px] font-medium text-[#d4a853] shadow-[0_0_14px_rgba(212,168,83,0.08)]`
                  : taker.tier === "2"
                    ? `flex h-7 w-7 items-center justify-center rounded-[10px] border border-white/8 bg-white/[0.04] ${monoClass} text-[11px] font-medium text-stone-300`
                    : `flex h-7 w-7 items-center justify-center rounded-[10px] border border-white/5 bg-white/[0.02] ${monoClass} text-[11px] font-medium text-stone-500`
              }
            >
              {taker.tier}
            </div>
            <span
              className={
                taker.tier === "1"
                  ? "truncate text-[14px] font-medium text-stone-100"
                  : taker.tier === "2"
                    ? "truncate text-[14px] font-normal text-stone-300"
                    : "truncate text-[14px] font-normal text-stone-500"
              }
            >
              {taker.value}
            </span>
            <span
              className={
                taker.tier === "1"
                  ? `rounded-md bg-emerald-500/10 px-2 py-1 ${monoClass} text-[9px] uppercase tracking-[0.18em] text-emerald-300`
                  : taker.tier === "2"
                    ? `rounded-md bg-white/[0.03] px-2 py-1 ${monoClass} text-[9px] uppercase tracking-[0.18em] text-stone-500`
                    : `rounded-md px-2 py-1 ${monoClass} text-[9px] uppercase tracking-[0.18em] text-stone-700`
              }
            >
              {taker.label}
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}

export default function PenaltyTakersClient({
  leagues,
  totalTeams,
  serifClass,
  monoClass,
  recentChanges,
  currentSeason,
}: Props) {
  return (
    <div className="min-h-screen bg-[#060606] text-stone-100">
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />

      <main className="relative mx-auto max-w-[1080px] px-5 pb-16 sm:px-8">
        <section className="relative overflow-hidden py-14 sm:py-20">
          <div className="pointer-events-none absolute left-1/2 top-[-8rem] h-[34rem] w-[34rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,_rgba(16,185,129,0.08)_0%,_transparent_72%)]" />

          <div className="relative">
            <div className={`mb-6 flex items-center gap-3 ${monoClass} text-[11px] uppercase tracking-[0.28em] text-emerald-400 sm:text-[12px]`}>
              <span className="block h-px w-8 bg-emerald-400" />
              Il Margine Intelligence
            </div>

            <h1 className={`max-w-4xl ${serifClass} text-[2.5rem] font-normal leading-[1.02] tracking-[-0.03em] text-stone-100 sm:text-[4rem]`}>
              Penalty takers <em className={`${serifClass} italic text-emerald-300`}>{currentSeason}</em>
            </h1>

            <p className="mt-5 max-w-3xl text-[15px] leading-7 text-stone-400 sm:text-[17px]">
              First, second and third-choice penalty takers for every club in Europe&apos;s top five leagues.
              This is a living reference page built for bettors, fantasy players and football obsessives who need
              the current hierarchy, not stale season-open guesses.
            </p>

            <div className="mt-10 flex flex-wrap gap-x-10 gap-y-5 border-t border-white/7 pt-8">
              <div>
                <div className={`${monoClass} text-[28px] font-medium leading-none text-stone-100`}>{totalTeams}</div>
                <div className="mt-1.5 text-[11px] tracking-[0.04em] text-stone-600">Teams tracked</div>
              </div>
              <div>
                <div className={`${monoClass} text-[28px] font-medium leading-none text-stone-100`}>{leagues.length}</div>
                <div className="mt-1.5 text-[11px] tracking-[0.04em] text-stone-600">Leagues</div>
              </div>
              <div>
                <div className={`${monoClass} text-[28px] font-medium leading-none text-stone-100`}>{currentSeason}</div>
                <div className="mt-1.5 text-[11px] tracking-[0.04em] text-stone-600">Season</div>
              </div>
            </div>
          </div>
        </section>

        <section className="mb-12 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-white/7 bg-[#0b0b0b] p-6">
            <h2 className={`${serifClass} text-[28px] font-normal text-stone-100`}>Why this page exists</h2>
            <div className="mt-4 space-y-4 text-[14px] leading-7 text-stone-400">
              <p>
                Most penalty-taker pages are just lists. They rarely tell you who is second in line, they often
                lag behind transfers and manager decisions, and they almost never help when the first-choice taker
                is benched an hour before kickoff.
              </p>
              <p>
                We track the first, second and third-choice hierarchy because that is what actually matters in live
                goalscorer markets. When a primary taker drops out, the backup becomes immediately relevant, and the
                market does not always catch up fast enough.
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-white/7 bg-[#0b0b0b] p-6">
            {recentChanges.length > 0 ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <h2 className={`${serifClass} text-[28px] font-normal text-stone-100`}>Recent changes</h2>
                  <span className={`${monoClass} rounded-md border border-white/8 bg-white/[0.03] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-stone-500`}>
                    latest {recentChanges.length}
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  {recentChanges.map((change) => (
                    <a
                      key={`${change.date}-${change.team}`}
                      href={change.href}
                      className="block rounded-xl border border-white/6 bg-white/[0.02] px-4 py-3 transition hover:border-white/12 hover:bg-white/[0.04]"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <span className={`${monoClass} text-[10px] uppercase tracking-[0.18em] text-stone-500`}>{change.date}</span>
                        <span className="text-[11px] text-stone-600">{change.league}</span>
                      </div>
                      <div className="mt-1 text-[14px] font-medium text-stone-100">{change.team}</div>
                      <div className="mt-1 text-[13px] leading-6 text-stone-400">{change.summary}</div>
                    </a>
                  ))}
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between gap-3">
                  <h2 className={`${serifClass} text-[28px] font-normal text-stone-100`}>How we keep it current</h2>
                  <span className={`${monoClass} rounded-md border border-white/8 bg-white/[0.03] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-stone-500`}>
                    evidence first
                  </span>
                </div>
                <div className="mt-4 space-y-4 text-[14px] leading-7 text-stone-400">
                  <p>
                    This page only moves when a hierarchy change is backed by a credible source, clear match evidence,
                    or a squad change that materially affects who is first, second or third in line.
                  </p>
                  <p>
                    That means injuries, suspensions, transfers, missed penalties, manager comments and official league
                    fantasy references matter. Quiet cleanup and old mistakes do not get dressed up as breaking news.
                  </p>
                </div>
              </>
            )}
          </div>
        </section>

        <div className="sticky top-0 z-20 -mx-5 mb-12 border-y border-white/7 bg-black/80 px-5 backdrop-blur-xl sm:-mx-8 sm:px-8">
          <nav aria-label="League jump links" className="flex overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
            {leagues.map((league) => (
              <a
                key={league.key}
                href={`#${league.key}`}
                className={`relative whitespace-nowrap border-b-2 px-5 py-4 text-[13px] font-medium tracking-[0.02em] transition ${league.tabClasses} hover:text-white`}
              >
                <span className="mr-2 inline-flex h-5 w-5 items-center justify-center overflow-hidden rounded-md border border-stone-200/70 bg-gradient-to-b from-white to-stone-100 align-middle">
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
              <div className="mb-8 flex items-center gap-4">
                <Crest
                  logoPath={league.logoPath}
                  team={league.label}
                  initials={league.short}
                  monoClass={monoClass}
                  size="league"
                />
                <div>
                  <h2 className={`${serifClass} text-[30px] font-normal text-stone-100`}>{league.heading}</h2>
                  <p className="text-[12px] text-stone-500">
                    {league.teamCount} teams - {league.updatedLabel}
                  </p>
                </div>
              </div>

              <div className="mb-8 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-4 text-[14px] leading-7 text-stone-400">
                  {league.paragraphs.map((paragraph) => (
                    <p key={`${league.key}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
                  ))}
                </div>
                <div className="rounded-2xl border border-white/7 bg-[#0b0b0b] p-5">
                  <div className={`${monoClass} text-[10px] uppercase tracking-[0.2em] text-stone-500`}>
                    Quick read
                  </div>
                  <p className="mt-3 text-[14px] leading-7 text-stone-300">{league.summary}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {league.teams.map((team) => (
                  <TeamCard key={`${league.key}-${team.slug}`} team={team} league={league} monoClass={monoClass} />
                ))}
              </div>
            </section>
          ))}
        </section>

        <section className="mt-14 space-y-5 border-t border-white/7 py-10">
          <div className="rounded-2xl border border-white/7 bg-[#0b0b0b] p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <circle cx="10" cy="10" r="8.5" stroke="currentColor" strokeWidth="1" className="text-emerald-300" />
                  <path d="M10 6v4.5l3 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" className="text-emerald-300" />
                </svg>
              </div>
              <div>
                <h3 className="text-[15px] font-semibold text-stone-100">Updated every matchweek</h3>
                <p className="mt-1 text-[14px] leading-6 text-stone-400">
                  This page is designed as a reference hub, not a one-off article. When penalty hierarchies change
                  because of missed kicks, transfers, coaching calls or injuries, this page should move with them.
                </p>
              </div>
            </div>
          </div>

          <div className="px-1 text-[13px] leading-6 text-stone-500">
            Spot an error or a hierarchy change?{" "}
            <a href="mailto:contact@ilmargine.bet" className="border-b border-emerald-500/30 text-emerald-300 hover:text-emerald-200">
              Let us know
            </a>{" "}
            and we&apos;ll update the reference quickly.
          </div>

          <div className={`px-1 ${monoClass} text-[11px] uppercase tracking-[0.16em] text-stone-700`}>
            Il Margine - Penalty takers reference - Season {currentSeason}
          </div>
        </section>
      </main>

      <Footer className="border-slate-900 bg-[#060606]" />
    </div>
  );
}
