import {breakPointHistory, type BreakPointRound} from '@/lib/tournament-break-points';
import {text, type SignalRow} from '@/lib/admin-monitor-display';

const value = (n: number | null) => n === null ? '—' : String(n);
const converted = (r: BreakPointRound) => r.converted === null || r.created === null ? '—' : `${r.converted} / ${r.created}`;

export default function TournamentBreakPoints({row}: {row: SignalRow}) {
  const h = breakPointHistory(row), complete = h.covered === h.completed;
  return <div className="mt-3 min-w-0" aria-label={`${text(row.player)} break point history`}>
    <p className="text-xs leading-relaxed text-slate-400">Chances created on return, breaks converted, and chances faced on serve. Converted 1 / 6 means one break from six chances.</p>
    {!h.available ? <p className="mt-3 rounded-lg border border-amber-300/20 p-3 text-xs text-amber-200">Break-point history is unavailable in this saved snapshot. Missing statistics are not zero.</p>
      : !h.logs.length ? <p className="mt-3 text-xs text-slate-400">No earlier played matches recorded in this tournament before {h.cutoff}. Qualifying is included when recorded.</p>
      : <>
        <div className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-300/5 p-3">
          <p className="text-[11px] font-medium text-slate-300">Tournament {complete ? 'totals' : 'subtotals'} · {h.covered}/{h.completed} completed matches with stats</p>
          <dl className="mt-3 grid grid-cols-3 gap-2">
            {([['Created',h.created],['Converted',h.converted],['Faced',h.faced]] as const).map(([label,n]) => <div key={label} className="min-w-0"><dt className="text-[11px] text-slate-400">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums text-slate-100">{value(n)}</dd></div>)}
          </dl>
          {!complete && <p className="mt-2 text-xs text-amber-200">Incomplete coverage: totals include only matches with verified counts.</p>}
          {h.partial > 0 && <p className="mt-2 text-xs text-amber-200">{h.partial} interrupted {h.partial === 1 ? 'match shown' : 'matches shown'} separately below; excluded from completed-match totals.</p>}
        </div>
        <div className="mt-3 space-y-3 sm:hidden">
          {h.logs.map(r => <article key={r.key} className="rounded-lg border border-slate-700/70 p-3">
            <p className="text-[11px] text-slate-400">{r.round} · {r.date}</p>
            <p className="mt-1 break-words text-sm font-medium text-slate-100">vs {r.opponent}</p>
            <p className="mt-1 text-xs text-slate-400">{r.result}{r.partial ? ' · Partial match' : ''}</p>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
              {([['Created',value(r.created)],['Converted',converted(r)],['Faced',value(r.faced)]] as const).map(([label,n]) => <div key={label}><dt className="text-[11px] text-slate-400">{label}</dt><dd className="mt-1 font-semibold tabular-nums text-slate-100">{n}</dd></div>)}
            </dl>
            <p className="mt-3 border-t border-slate-700/60 pt-2 text-[11px] text-slate-400">{r.valid ? <>Total match chances <strong className="text-slate-200">{r.matchChances}</strong> · both players</> : 'Break-point statistics unavailable'}</p>
          </article>)}
        </div>
        <div className="mt-3 hidden sm:block">
          <table className="w-full table-fixed text-xs">
            <caption className="sr-only">{text(row.player)} break-point chances by round</caption>
            <thead className="text-slate-400"><tr><th scope="col" className="pb-2 text-left font-normal">Round / opponent</th><th scope="col" className="w-12 pb-2 text-right font-normal">Created</th><th scope="col" className="w-16 pb-2 text-right font-normal">Converted</th><th scope="col" className="w-11 pb-2 text-right font-normal">Faced</th></tr></thead>
            <tbody>{h.logs.map(r => <tr key={r.key} className="border-t border-slate-700/60"><th scope="row" className="py-3 pr-2 text-left font-normal"><span className="block break-words text-slate-100">{r.round} · {r.opponent}</span><span className="mt-1 block text-[11px] text-slate-400">{r.date} · {r.result}{r.partial ? ' · Partial match' : ''}</span><span className="mt-1 block text-[11px] text-slate-400">{r.valid ? `Total match chances: ${r.matchChances} · both players` : 'Break-point statistics unavailable'}</span></th><td className="py-3 text-right align-top font-semibold tabular-nums">{value(r.created)}</td><td className="py-3 text-right align-top font-semibold tabular-nums">{converted(r)}</td><td className="py-3 text-right align-top font-semibold tabular-nums">{value(r.faced)}</td></tr>)}</tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-slate-400">History before {h.cutoff}, including recorded qualifying. Match chances = created + faced, counted once. These are previous results, not a forecast for the next match.</p>
      </>}
  </div>;
}
