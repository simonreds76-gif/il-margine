import Link from "next/link";
import Image from "next/image";
import Footer from "@/components/Footer";

type TeamEntry = {
  team: string;
  slug: string;
  primary: string;
  secondary: string;
  tertiary: string;
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
  summary: string;
  paragraphs: string[];
  teams: TeamEntry[];
};

type Props = {
  leagues: LeagueEntry[];
  totalTeams: number;
  currentSeason: string;
};

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
  const takers = [
    { label: "First choice", value: team.primary, tier: "1" as const },
    { label: "Second choice", value: team.secondary, tier: "2" as const },
    ...(team.tertiary ? [{ label: "Third choice", value: team.tertiary, tier: "3" as const }] : []),
  ];

  return (
    <article
      id={`${league.key}-${team.slug}`}
      className={`group scroll-mt-28 rounded-xl border border-slate-800/70 bg-slate-900/55 p-5 shadow-[0_10px_30px_rgba(0,0,0,0.18)] transition hover:-translate-y-0.5 hover:border-slate-700 hover:bg-slate-900/80 ${league.cardGlowClasses}`}
    >
      <div className="mb-3.5 flex items-start gap-3 border-b border-slate-800/70 pb-3.5">
        <Crest logoPath={team.logoPath} team={team.team} initials={team.initials} />
        <div className="min-w-0 flex-1 pt-0.5">
          <a
            href={`#${league.key}-${team.slug}`}
            className="truncate text-[15px] font-semibold tracking-[0.01em] text-slate-100 transition hover:text-emerald-400"
          >
            {team.team}
          </a>
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
                    : "flex h-7 w-7 items-center justify-center rounded-lg border border-slate-800 bg-slate-950/60 font-mono text-[11px] font-semibold text-slate-500"
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
                    : "truncate text-[14px] text-slate-400"
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
                    : "rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-slate-600"
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

export default function PenaltyTakersClient({ leagues, totalTeams, currentSeason }: Props) {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="border-b border-slate-800/50 pt-6 pb-12 md:pt-6 md:pb-16">
          <div className="max-w-4xl">
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-300 mb-8">
              <Image src="/favicon.png" alt="" width={40} height={40} className="h-10 w-10 object-contain shrink-0" />
              <span>&larr; Home</span>
            </Link>
            <span className="text-xs font-mono text-emerald-400 mb-3 block tracking-wider">IL MARGINE INTELLIGENCE</span>
            <h1 className="text-3xl sm:text-4xl font-semibold text-slate-100 mb-4">
              Penalty Takers <span className="text-emerald-400">{currentSeason}</span>
            </h1>
            <p className="text-base sm:text-lg text-slate-300 max-w-3xl leading-relaxed">
              First, second and third-choice penalty takers for every club in Europe&apos;s top five leagues.
              Built as a live reference for bettors, fantasy players and anyone who needs the actual hierarchy,
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
          </div>
        </section>

        <section className="grid gap-4 py-10 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-6">
            <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">Why this matters</div>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">One page, full hierarchy</h2>
            <div className="mt-4 space-y-4 text-[15px] leading-7 text-slate-300">
              <p>
                Most penalty-taker pages stop at the headline name. That breaks the moment the first-choice taker
                is benched, suspended or off the pitch. This page is built around the real question: who is next?
              </p>
              <p>
                That is why every team card tracks the first, second and third option. For live goalscorer markets
                and fantasy decisions, the backup order is often the part that matters most.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-400">Editorial standard</div>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-100">How we keep it current</h2>
              </div>
              <span className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-emerald-300">
                evidence first
              </span>
            </div>
            <div className="mt-4 space-y-4 text-[15px] leading-7 text-slate-300">
              <p>
                We only move a hierarchy when there is credible evidence behind it: match evidence, team news,
                injuries, suspensions, transfers, missed penalties or a strong league-specific reference source.
              </p>
              <p>
                Quiet cleanup and old mistakes are not dressed up as breaking changes. The goal is a stable reference
                page you can trust when lineups drop.
              </p>
            </div>
          </div>
        </section>

        <div className="sticky top-0 z-20 -mx-4 mb-10 border-y border-slate-800/70 bg-[#0f1117]/95 px-4 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
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
                <div className="space-y-4 text-[15px] leading-7 text-slate-300">
                  {league.paragraphs.map((paragraph) => (
                    <p key={`${league.key}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
                  ))}
                </div>
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-5">
                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">Quick read</div>
                  <p className="mt-3 text-[15px] leading-7 text-slate-300">{league.summary}</p>
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
          <div className="rounded-xl border border-slate-800/60 bg-slate-900/55 p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10">
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <circle cx="10" cy="10" r="8.5" stroke="currentColor" strokeWidth="1" className="text-emerald-300" />
                  <path d="M10 6v4.5l3 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" className="text-emerald-300" />
                </svg>
              </div>
              <div>
                <h3 className="text-[15px] font-semibold text-slate-100">Updated every matchweek</h3>
                <p className="mt-1 text-[15px] leading-7 text-slate-300">
                  This is a reference page, not a disposable article. When a hierarchy changes because of a missed
                  penalty, a transfer, an injury or a coach decision, this page should move with it.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-5 px-1 text-sm leading-6 text-slate-400">
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
