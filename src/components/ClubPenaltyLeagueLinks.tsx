import Link from "next/link";
import { CLUB_LEAGUES, CLUB_PENALTY_SEASON } from "@/lib/club-penalty-takers";

export default function ClubPenaltyLeagueLinks({ compact = false }: { compact?: boolean }) {
  return (
    <section className={compact ? "mt-8" : "mt-10"}>
      <div className="rounded-3xl border border-emerald-400/18 bg-[linear-gradient(140deg,rgba(6,25,20,0.94),rgba(10,15,24,0.96))] p-5 sm:p-6">
        <div className="font-mono text-xs uppercase tracking-[0.25em] text-emerald-400">Club penalty intelligence</div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-100 sm:text-2xl">Follow the {CLUB_PENALTY_SEASON} club hierarchies</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
          The same evidence-first format now covers every current club in Europe&apos;s top five leagues, with provisional carryovers clearly labelled during preseason.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {CLUB_LEAGUES.map((league) => (
            <Link key={league.key} href={`/penalty-takers/${league.key}`} className="rounded-full border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-emerald-400/35 hover:text-emerald-200">
              {league.label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
