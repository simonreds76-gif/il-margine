import ModelProfitChart from "./ModelProfitChart";
import { reportSelectionHistory } from "@/lib/model-profit-history";
import { obj } from "@/lib/admin-model-summary";

const num = (v: unknown): number | null => typeof v === "number" && Number.isFinite(v) ? v : null;
const txt = (v: unknown) => typeof v === "string" ? v : "";
const fmt = (v: unknown, digits = 2) => num(v)?.toLocaleString("en-GB", { maximumFractionDigits: digits }) ?? "—";
const tone = (v: unknown) => (num(v) ?? 0) > 0 ? "text-emerald-300" : (num(v) ?? 0) < 0 ? "text-rose-300" : "text-slate-200";
const date = (v: unknown) => txt(v).replace("T", " ").slice(0, 16);

export default function FrozenPaperComparison({ report, id }: { report: unknown; id: string }) {
  const r = obj(report);
  if (!r.registered_at) return null;
  const protocol = obj(r.protocol), labels = obj(protocol.labels), arms = obj(r.arms), health = obj(r.capture);
  const records = Array.isArray(r.records) ? r.records.map(obj) : [];
  const atp = "MJ1_S" in labels;
  const markets = atp ? [["total_games", "Total games"], ["game_handicap", "Handicaps"]] : [["all", "Team shots"]];
  return <section id={id} aria-labelledby={`${id}-title`} className="mt-6 min-w-0 rounded-xl border border-cyan-800/70 bg-slate-950/40 p-4 sm:p-5">
    <p className="text-xs font-semibold uppercase tracking-wider text-cyan-300">New frozen comparison · Paper only</p>
    <h3 id={`${id}-title`} className="mt-2 text-xl font-semibold text-white">{txt(r.name)}</h3>
    <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-300">{atp
      ? "J1 serve/return rates and the matching bookmaker winner price produce two game-score distributions. The frozen correction is compared with its uncorrected reference and current pricing on the same new matches. Indoor and qualifying are included."
      : "The correction adds strength from a verified match-winner quote to Opponent Shots. Both versions use the same new contracts and first observation. The four-model comparison above remains separate."}</p>
    <p className="mt-3 text-xs leading-6 text-slate-400">Started {date(r.registered_at)} UTC · {fmt(r.fixtures, 0)} fixtures · {fmt(r.contracts, 0)} contracts · {fmt(r.settled_fixtures, 0)} settled fixtures. Historical test profits are excluded.</p>
    <p className="mt-2 text-xs leading-6 text-amber-200">{txt(protocol.historical_status)} Primary measure: paired log loss against the same bookmaker’s margin-adjusted price; ROI is secondary.</p>
    <p className="mt-2 break-words text-xs text-amber-200">Capture: {txt(health.state).replaceAll("_", " ").toLowerCase()}. {txt(health.reason)} {date(health.checked_at)} UTC</p>
    {(num(r.conflicts) ?? 0) > 0 && <p className="mt-2 text-sm text-amber-200">{fmt(r.conflicts, 0)} result conflicts need review. Recorded grades are retained.</p>}
    {markets.map(([market, title]) => <div key={market} className="mt-5">
      <h4 className="text-sm font-semibold text-white">{title}</h4>
      <div className={`mt-3 grid gap-4 ${atp ? "lg:grid-cols-3" : "sm:grid-cols-2"}`}>{Object.entries(labels).map(([arm, label]) => {
        const s = obj(obj(arms[arm])[market]), cal = obj(s.calibration);
        const selected = records.filter(row => (market === "all" || row.market === market) && obj(obj(row.arms)[arm]).selected === true);
        return <article key={arm} className="min-w-0 rounded-xl border border-slate-700 p-4">
          <h5 className="text-sm font-semibold text-cyan-200">{txt(label)}</h5>
          <p className={`mt-3 text-2xl font-semibold tabular-nums ${tone(s.roi_pct)}`}>{num(s.roi_pct) === null ? "—" : `${fmt(s.roi_pct)}%`}</p>
          <p className="text-xs text-slate-400">{num(s.roi_pct) === null ? "ROI awaits settled selections" : "Forward paper ROI"}</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs leading-5">
            <div><dt className="text-slate-400">Profit / stake</dt><dd><span className={tone(s.profit)}>{fmt(s.profit)}u</span> / {fmt(s.stake)}u</dd></div>
            <div><dt className="text-slate-400">W / L / pushes</dt><dd>{fmt(s.wins, 0)} / {fmt(s.losses, 0)} / {fmt(s.pushes, 0)}</dd></div>
            <div><dt className="text-slate-400">Pending / overdue</dt><dd>{fmt(s.pending, 0)} / {fmt(s.overdue, 0)}</dd></div>
            <div><dt className="text-slate-400">Excluded / quarantined</dt><dd>{fmt(s.excluded, 0)} / {fmt(s.quarantined, 0)}</dd></div>
          </dl>
          <ModelProfitChart name={`${txt(label)} · ${title}`} history={reportSelectionHistory(selected.map(row => ({ ...row, profit: obj(obj(row.arms)[arm]).profit })), { settled: num(s.settled), profit: num(s.profit) })} />
          <p className="mt-3 border-t border-slate-700 pt-3 text-xs leading-6 text-slate-300">Brier {fmt(cal.brier, 4)} · log loss {fmt(cal.log_loss, 4)}<br/>Market: {fmt(cal.market_brier, 4)} / {fmt(cal.market_log_loss, 4)}<br/>{fmt(cal.n, 0)} settled fixtures, including no-bet observations.</p>
        </article>;
      })}</div>
    </div>)}
    <details className="mt-5 border-t border-slate-700 pt-4"><summary className="min-h-11 cursor-pointer text-sm text-cyan-200">Prices, selections and results ({records.length})</summary>
      {!records.length ? <p className="mt-3 text-sm leading-6 text-slate-400">Waiting for eligible fresh inputs and prices after registration. Selections and results will appear automatically.</p> : <div className="mt-3 grid gap-3 md:grid-cols-2">{records.slice(0, 40).map(row => {
        const players = Array.isArray(row.players) ? row.players.map(txt) : [], prices = Array.isArray(row.odds) ? row.odds : [];
        return <article key={txt(row.id)} className="min-w-0 rounded-lg border border-slate-700 p-3">
          <h4 className="break-words text-sm font-semibold">{players.join(" vs ")}</h4>
          <p className="mt-1 text-xs leading-5 text-slate-400">{txt(row.tournament)} · {date(row.start)} UTC</p>
          <p className="mt-2 text-xs leading-5">{txt(row.team)} {txt(row.market).replaceAll("_", " ")} {fmt(row.line, 1)} · {txt(row.bookmaker)} · {fmt(prices[0])} / {fmt(prices[1])}</p>
          {Object.entries(labels).map(([arm, label]) => { const s = obj(obj(row.arms)[arm]); const side = num(s.side) === 1 ? 0 : 1;
            return <p key={arm} className="mt-2 break-words text-xs leading-5"><span className="text-cyan-200">{txt(label)}</span>: {row.market === "game_handicap" ? players[side] : side === 0 ? "Over" : "Under"} · fair {fmt(s.fair_odds)} · {s.selected ? "1u paper" : "No bet"}{num(s.profit) !== null ? ` · ${fmt(s.profit)}u` : ""}</p>;
          })}
          <p className="mt-2 text-xs text-slate-400">{txt(row.status)} {txt(row.score)} · Price observed {date(row.price_observed_at)} UTC</p>
        </article>;
      })}</div>}
      {records.length > 40 && <p className="mt-2 text-xs text-slate-400">Latest 40 contracts shown. Charts and totals include the entire cohort.</p>}
    </details>
    <p className="mt-4 text-xs leading-6 text-slate-400">Lower Brier and log loss are better. Each fixture has equal weight. 1u is hypothetical; real stake is zero. Descriptive review at 100 fixtures, decision reviews at 400 / 800 or 12 months. Small samples are inconclusive. No new alerts or automatic promotion.</p>
  </section>;
}
