import Link from "next/link";
import ClubPenaltyLatestUpdates from "@/components/ClubPenaltyLatestUpdates";
import Footer from "@/components/Footer";
import PageHomeLink from "@/components/PageHomeLink";
import type { ClubPenaltyLeague, ClubPenaltyNewsItem, ClubPenaltySeason } from "@/lib/club-penalty-takers";

type Props = { leagues: ClubPenaltyLeague[]; totalTeams: number; season: ClubPenaltySeason; latestNews: ClubPenaltyNewsItem[] };

const FEATURED: Record<string, string[]> = {
  epl: ["Arsenal", "Chelsea", "Liverpool", "Manchester City", "Manchester United"],
  "serie-a": ["AC Milan", "Inter", "Juventus", "Napoli", "Roma"],
  "la-liga": ["Atletico Madrid", "Barcelona", "Real Madrid", "Real Betis", "Villarreal"],
  bundesliga: ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen", "RasenBallsport Leipzig", "Eintracht Frankfurt"],
  "ligue-1": ["Paris Saint Germain", "Marseille", "Monaco", "Lyon", "Lille"],
};

function Crest({ src, label, fallback, large = false }: { src: string; label: string; fallback: string; large?: boolean }) {
  return (
    <div className={`${large ? "h-14 w-14 rounded-2xl" : "h-9 w-9 rounded-xl"} flex shrink-0 items-center justify-center overflow-hidden border border-white/10 bg-white shadow-[0_10px_30px_rgba(0,0,0,0.22)]`}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={`${label} logo`} className={`${large ? "h-10 w-10" : "h-6 w-6"} object-contain`} />
      ) : (
        <span className="font-mono text-[10px] font-bold text-slate-700">{fallback}</span>
      )}
    </div>
  );
}

function LeagueCard({ league, season }: { league: ClubPenaltyLeague; season: ClubPenaltySeason }) {
  const featured = (FEATURED[league.key] ?? [])
    .map((name) => league.teams.find((team) => team.team === name))
    .filter((team): team is ClubPenaltyLeague["teams"][number] => Boolean(team));
  const unverified = league.teams.filter((team) => team.hierarchyStatus === "unknown").length;
  const isLive = league.phase === "live";

  return (
    <article className="group relative overflow-hidden rounded-[28px] border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_18px_55px_rgba(0,0,0,0.2)] transition hover:-translate-y-0.5 hover:border-slate-700 sm:p-6">
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-r ${league.surface} opacity-70`} />
      <div className="relative">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <Crest src={league.logoPath} label={league.label} fallback={league.short} large />
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-slate-400">{season.label} board</div>
              <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-100">{league.label}</h2>
            </div>
          </div>
          <span className={`rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.16em] ${isLive ? "border-emerald-300/25 bg-emerald-400/10 text-emerald-100" : "border-amber-300/20 bg-amber-400/10 text-amber-100"}`}>
            {isLive ? "Live season" : "Preseason"}
          </span>
        </div>

        <p className="mt-4 text-sm leading-6 text-slate-400">{league.copy}</p>
        <p className="mt-3 text-xs text-slate-300">
          <span className="text-slate-500">Board checked</span>{" "}
          <span className="font-medium text-emerald-200">{league.boardCheckedLabel || "pending"}</span>
        </p>

        <div className="mt-5 grid grid-cols-3 gap-2">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.17em] text-slate-500">Clubs</div>
            <div className="mt-1 text-lg font-semibold text-slate-100">{league.teams.length}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.17em] text-slate-500">New</div>
            <div className="mt-1 text-lg font-semibold text-amber-200">{unverified}</div>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/65 p-3">
            <div className="font-mono text-[9px] uppercase tracking-[0.17em] text-slate-500">Archived</div>
            <div className="mt-1 text-lg font-semibold text-slate-300">{league.archivedTeams.length}</div>
          </div>
        </div>

        <div className="mt-5 space-y-2">
          {featured.slice(0, 4).map((team) => (
            <Link key={team.relativeUrl} href={team.relativeUrl} className="flex items-center gap-3 rounded-xl border border-slate-800/80 bg-slate-950/45 px-3 py-2 transition hover:border-slate-700 hover:bg-slate-950/80">
              <Crest src={team.logoPath} label={team.team} fallback={team.initials} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-100">{team.team}</span>
                <span className="block truncate text-xs text-slate-500">{team.primary}</span>
              </span>
              <span className="text-slate-600" aria-hidden="true">-&gt;</span>
            </Link>
          ))}
        </div>

        <Link href={`/penalty-takers/${league.key}`} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-400/25 bg-emerald-400/10 px-4 py-3 text-sm font-semibold text-emerald-100 transition hover:border-emerald-300/40 hover:bg-emerald-400/15">
          View every {league.label} club <span aria-hidden="true">-&gt;</span>
        </Link>
      </div>
    </article>
  );
}

export default function PenaltyTakersClient({ leagues, totalTeams, season, latestNews }: Props) {
  const archivedCount = leagues.reduce((sum, league) => sum + league.archivedTeams.length, 0);

  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <main className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <section className="pt-8 pb-12 md:pb-16">
          <PageHomeLink className="mb-8" />
          <div className="relative overflow-hidden rounded-[34px] border border-slate-800/80 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.15),transparent_38%),linear-gradient(150deg,#07100f,#0f1722_58%,#11131b)] p-6 sm:p-9 lg:p-11">
            <div className="max-w-4xl">
              <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Il Margine intelligence</div>
              <h1 className="mt-4 text-4xl font-semibold tracking-[-0.035em] text-slate-100 sm:text-6xl">
                Club penalty takers <span className="text-emerald-400">{season.label}</span>
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
                Five dedicated league boards, {totalTeams} current clubs and transparent evidence status. Final {season.previous_label} orders were only a starting point; live-season penalties and lineup context now drive every update.
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-200">{totalTeams} current clubs</span>
                <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-emerald-100">Live evidence monitoring</span>
                <span className="rounded-full border border-slate-700 bg-slate-950/60 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-300">{archivedCount} relegated records retained</span>
              </div>
            </div>
          </div>
        </section>

        <ClubPenaltyLatestUpdates items={latestNews} />

        <section className="mt-10">
          <div className="mb-6 max-w-3xl">
            <div className="font-mono text-xs uppercase tracking-[0.25em] text-emerald-400">Choose a league</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-100">Every league now has its own indexable board</h2>
            <p className="mt-3 text-sm leading-7 text-slate-400">The main page is an overview. Full club tables live on dedicated league pages so users and search engines do not have to navigate five duplicate sections.</p>
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            {leagues.map((league) => <LeagueCard key={league.key} league={league} season={season} />)}
          </div>
        </section>

        <section className="mt-10 grid gap-4 md:grid-cols-3">
          {[
            ["Carryover is labelled", `A ${season.previous_label} order is not presented as fresh ${season.label} evidence.`],
            ["Real events move the order", "Penalties, misses, who was on the pitch and explicit hierarchy comments matter more than reputation."],
            ["No automatic claims", "Promoted clubs remain unverified until the evidence supports a public hierarchy."],
          ].map(([title, body]) => (
            <div key={title} className="rounded-2xl border border-slate-800 bg-slate-900/55 p-5">
              <h2 className="font-semibold text-slate-100">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">{body}</p>
            </div>
          ))}
        </section>
        <section className="mt-8 rounded-3xl border border-emerald-400/18 bg-emerald-400/6 p-5 sm:p-6">
          <h2 className="text-xl font-semibold text-slate-100">How these orders are verified</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Read the rules for in-match penalties, absences, shootouts, misses, corrections and human approval.</p>
          <Link href="/penalty-takers/methodology" className="mt-4 inline-flex text-sm font-semibold text-emerald-300 hover:text-emerald-200">Read the methodology -&gt;</Link>
        </section>

        <section className="mt-8">
          <Link href="/penalty-takers/world-cup-2026" className="group block overflow-hidden rounded-[26px] border border-amber-400/15 bg-[linear-gradient(135deg,rgba(20,18,12,0.82),rgba(16,18,24,0.92))] p-5 transition hover:border-amber-300/30">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-amber-400/15 bg-amber-500/8">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src="/world-cup-2026-logo.png" alt="FIFA World Cup 2026 logo" className="h-10 w-10 object-contain" />
                </div>
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-300/80">Tournament archive</div>
                  <div className="mt-1 text-sm font-semibold text-slate-100">World Cup 2026 penalty takers</div>
                  <p className="mt-1 text-sm text-slate-400">The final 48-nation hierarchy and dated evidence pages remain available as a permanent archive.</p>
                </div>
              </div>
              <span className="text-sm font-medium text-amber-200">Open archive -&gt;</span>
            </div>
          </Link>
        </section>
      </main>
      <Footer />
    </div>
  );
}
