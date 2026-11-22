import Link from "next/link";
import { newsDate, outcomeLabel, type PenaltyArticle } from "@/lib/penalty-news";
import type { ClubPenaltyTeam } from "@/lib/club-penalty-takers";

type Props = { items: PenaltyArticle[]; teams: ClubPenaltyTeam[]; eyebrow?: string };

export default function ClubPenaltyLatestUpdates({ items, teams, eyebrow = "Penalty taker evidence" }: Props) {
  if (!items.length) return null;
  const firstChoices = new Map(teams.filter(team => team.hierarchyDepth > 0).map(team => [team.relativeUrl, team.primary]));

  return (
    <section id="latest-penalty-taker-updates" className="rounded-[30px] border border-emerald-400/18 bg-[linear-gradient(145deg,rgba(6,22,20,0.9),rgba(9,15,26,0.96))] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.24)] sm:p-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400">{eyebrow}</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-100 sm:text-3xl">Latest penalties taken</h2>
          <p className="mt-2 text-sm leading-6 text-slate-400">Reported penalties from completed league matches. Each club’s taker order is reviewed separately.</p>
        </div>
        <Link href="/penalty-news#reports" className="text-sm font-semibold text-emerald-300 hover:underline">All penalty reports →</Link>
      </div>
      <ol className="mt-5 grid items-stretch gap-3 md:grid-cols-2 xl:grid-cols-3">
        {items.map(report => (
          <li key={report.slug} className="flex flex-col rounded-2xl border border-slate-700/70 bg-slate-950/65 p-5">
            <div className="flex items-center gap-3">
              {report.crest && <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={report.crest} alt="" width={32} height={32} className="h-8 w-8 object-contain" />
              </span>}
              <div>
                <p className="text-xs text-slate-400"><time dateTime={report.date}>{newsDate(report.date)}</time> · {report.leagueLabel}</p>
                <p className="mt-1 text-sm font-medium text-slate-300">{report.club}</p>
              </div>
            </div>
            <h3 className="mt-4 text-lg font-semibold leading-6 text-slate-100">
              <Link href={`/penalty-news/${report.slug}`} className="hover:text-emerald-300 hover:underline">{report.title}</Link>
            </h3>
            <p className="mb-4 mt-2 text-sm text-slate-300">{outcomeLabel[report.outcome]}{report.minute && ` · ${report.minute}′`}</p>
            <div className="mt-auto border-t border-slate-800 pt-3">
              {firstChoices.has(report.clubUrl) && <p className="mb-1 text-xs text-slate-300">First choice: <strong>{firstChoices.get(report.clubUrl)}</strong></p>}
              <Link href={report.clubUrl} className="text-xs font-semibold text-emerald-300 hover:underline">{report.club} taker order →</Link>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
