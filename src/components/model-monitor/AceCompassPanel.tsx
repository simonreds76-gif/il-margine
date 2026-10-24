import { readTennisEvidence } from "@/lib/tennis-evidence-reader";
import { object } from "@/lib/tennis-monitor-overview";

const number = (v: unknown, digits = 0, suffix = "") => typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(digits)}${suffix}` : "Awaiting results";
const tone = (v: unknown) => typeof v === "number" ? v < 0 ? "text-rose-300" : v > 0 ? "text-emerald-300" : "text-slate-200" : "text-slate-400";
const time = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v)) ? new Date(v).toLocaleString("en-GB", { timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "Unavailable";

export default async function AceCompassPanel() {
  const { snapshot } = await readTennisEvidence();
  const report = object(object(snapshot?.sections).tennis_ace_compass);
  const arms = object(report.arms);
  const capture = object(report.capture);
  const selections = Array.isArray(report.selections) ? report.selections.map(object) : [];
  const bias = Array.isArray(report.bias) ? report.bias.map(object) : [];
  return <section id="ace-compass" className="my-6 scroll-mt-24 rounded-2xl border border-cyan-800 bg-slate-900 p-4 text-slate-100 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Opponent adjusted aces</p><h2 className="mt-2 text-2xl font-semibold">Ace Compass</h2></div><span className="rounded-full border border-amber-700 px-3 py-1 text-xs text-amber-200">Paper only · zero real stake</span></div>
    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">Tests whether accounting for the servers an opponent previously faced improves ace prices. Both versions are frozen before play. ATP and Challenger results remain separate. Live models are unchanged.</p>
    {Object.keys(report).length === 0 ? <p className="mt-4 text-amber-200">Tracker report unavailable. Missing evidence is not a zero result.</p> : <>
      <div className="mt-5 grid gap-4 md:grid-cols-2">{[["candidate", "Ace Compass"], ["control", "Original research reference"]].map(([key, label]) => {
        const arm = object(arms[key]);
        return <article key={key} className="rounded-xl border border-slate-700 bg-slate-950/60 p-4"><h3 className="font-semibold">{label}</h3><dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div><dt className="text-xs text-slate-400">Forward ROI</dt><dd className={`mt-1 text-xl font-semibold ${tone(arm.roi_pct)}`}>{number(arm.roi_pct, 2, "%")}</dd></div>
          <div><dt className="text-xs text-slate-400">Profit / loss</dt><dd className={`mt-1 text-xl font-semibold ${tone(arm.pnl_units)}`}>{number(arm.pnl_units, 2, "u")}</dd></div>
          <div><dt className="text-xs text-slate-400">Wins / losses</dt><dd>{number(arm.wins)} / {number(arm.losses)}</dd></div>
          <div><dt className="text-xs text-slate-400">Settled stake</dt><dd>{number(arm.stake_units, 0, "u")}</dd></div>
          <div><dt className="text-xs text-slate-400">Pending / void</dt><dd>{number(arm.pending)} / {number(arm.void)}</dd></div>
          <div><dt className="text-xs text-slate-400">Overdue by 48 hours</dt><dd>{number(arm.overdue)}</dd></div>
          <div><dt className="text-xs text-slate-400">Probability error · Brier</dt><dd>{number(arm.brier, 4)}</dd></div>
          <div><dt className="text-xs text-slate-400">Log loss · lower is better</dt><dd>{number(arm.log_loss, 4)}</dd></div>
        </dl></article>;
      })}</div>
      <p className="mt-4 break-words text-xs leading-5 text-slate-400">Registered {time(report.registered_at)} UK · Report {time(report.generated_at)} UK · {number(report.registered_quotes)} frozen quotes · {number(report.independent_fixtures)} completed independent fixtures.</p>
      <p className="mt-2 break-words text-sm text-amber-200">Capture: {String(capture.state ?? "unavailable").replaceAll("_", " ").toLowerCase()} · Checked {time(capture.checked_at)} UK{capture.reason ? ` · ${String(capture.reason)}` : ""}.</p>
      {capture.reasons ? <details className="mt-3 text-xs text-slate-400"><summary className="cursor-pointer">Capture coverage</summary><ul className="mt-2 space-y-1">{Object.entries(object(capture.reasons)).map(([key, count]) => <li key={key}>{key.replaceAll("_", " ")}: {String(count)}</li>)}</ul></details> : null}
      <h3 className="mt-6 font-semibold">Are we predicting too few aces?</h3><p className="mt-2 text-sm leading-6 text-slate-400">Negative bias means too few predicted aces; positive means too many. Each player’s match counts once, across all lines and bookmakers. This measures priced-match coverage, not every match on tour.</p>
      {bias.length ? <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><caption className="sr-only">Predicted ace totals compared with actual totals</caption><thead className="text-xs text-slate-400"><tr>{["Group", "Player matches", "Actual aces", "Reference bias", "Compass bias"].map(s => <th scope="col" key={s} className="p-2">{s}</th>)}</tr></thead><tbody>{bias.map(b => <tr key={String(b.group)} className="border-t border-slate-700"><th scope="row" className="p-2 font-medium">{String(b.group)}</th><td className="p-2">{number(b.player_matches)}</td><td className="p-2">{number(b.actual)}</td><td className="p-2">{number(object(b.control).bias_pct, 1, "%")}</td><td className="p-2">{number(object(b.candidate).bias_pct, 1, "%")}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-slate-300">Bias tracking starts when the first player match settles.</p>}
      <details open className="mt-6 border-t border-slate-700 pt-4"><summary className="cursor-pointer font-semibold">Paper selections and results · {number(report.selection_count)}</summary><p className="mt-2 text-xs leading-5 text-slate-400">First recorded prices, 1u per qualifying selection. Latest 200 shown; headline figures use the full record. Several lines from one match are correlated. Retirements and walkovers are void.</p>
        {selections.length === 0 ? <p className="mt-4 text-sm text-slate-300">No qualifying forward selections yet. The historical 19 bets are not added to this record.</p> : <div className="mt-4 grid gap-3 md:grid-cols-2">{selections.map(b => <article key={String(b.id)} className="min-w-0 rounded-xl border border-slate-700 bg-slate-950/60 p-4"><div className="flex flex-wrap justify-between gap-2 text-xs text-slate-400"><span>{time(b.start)} UK</span><span>{String(b.tournament)}</span></div><h4 className="mt-2 break-words font-semibold">{String(b.player)} <span className="font-normal text-slate-400">vs {String(b.opponent)}</span></h4><p className="mt-2 text-sm">Over {number(b.line, 1)} aces · {String(b.bookmaker)} @ {number(b.odds, 2)}</p><div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm"><span>Fair {number(b.fair, 2)}</span><span>EV {typeof b.ev === "number" ? number(b.ev * 100, 1, "%") : "Unavailable"}</span><span className={tone(b.profit)}>{String(b.status)}{b.profit != null ? ` · ${number(b.profit, 2, "u")}` : ""}</span></div>{b.actual != null ? <p className="mt-2 text-xs text-slate-400">Actual aces: {number(b.actual)}</p> : null}</article>)}</div>}
      </details>
    </>}
  </section>;
}
