"use client";

import { useId, useState } from "react";
import { profitWindow, type ProfitHistory } from "@/lib/model-profit-history";

const signed = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}u`;
const dateLabel = (date: string) => new Date(date).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
export default function ModelProfitChart({ history, name }: { history: ProfitHistory; name: string }) {
  const [windowDays, setWindowDays] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const id = useId().replaceAll(":", "");
  if (history.message || history.omitted) return <p className="mt-5 border-t border-slate-700/60 pt-3 text-xs leading-5 text-slate-400">{history.message || "Chart unavailable: some settled rows lack a date or recorded profit."}</p>;
  if (!history.days.length) return <p className="mt-5 text-xs text-slate-400">Profit history starts when a selection settles.</p>;
  const range = profitWindow(history, windowDays);
  const points = range.days;
  const active = points.find(p => p.date === selected) ?? points[points.length - 1];
  const W = 340, H = 155, left = 7, right = 333, top = 16, bottom = 130;
  const values = [0, range.opening, ...points.map(p => p.cumulative)];
  const low = Math.min(...values), high = Math.max(...values);
  const span = Math.max(high - low, 1);
  const y = (value: number) => bottom - (value - low + span * .08) / (span * 1.16) * (bottom - top);
  const firstTime = Date.parse(range.from!);
  const lastTime = Date.parse(points[points.length - 1].date);
  const x = (date: string) => left + 14 + (Date.parse(date) - firstTime) / Math.max(lastTime - firstTime, 86400000) * (right - left - 14);
  // Straight segments, not a smoothed curve: no invented returns between observations.
  const path = `M ${left} ${y(range.opening)} ` + points.map(p => `L ${x(p.date)} ${y(p.cumulative)}`).join(" ");
  const zero = y(0);
  const activeIndex = points.indexOf(active);
  return <section aria-label={`${name} profit history`} className="mt-5 min-w-0 border-t border-slate-700/60 pt-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-xs font-medium text-slate-300">Cumulative profit / loss</h4><div className="flex gap-1" aria-label={`${name} chart period`}>{[[null, "All"], [30, "30d"]].map(([n, label]) => <button key={String(label)} type="button" aria-pressed={windowDays === n} onClick={() => { setWindowDays(n as number | null); setSelected(null); }} className={`min-h-9 min-w-11 rounded-lg px-2 text-xs focus-visible:outline focus-visible:outline-emerald-300 ${windowDays === n ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800"}`}>{label}</button>)}</div></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 block w-full touch-pan-y" role="img" aria-labelledby={`${id}-title ${id}-description`} onPointerMove={event => {
      if (event.pointerType === "touch" && event.buttons === 0) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const target = (event.clientX - rect.left) / rect.width * W;
      const nearest = points.reduce((best, p) => Math.abs(x(p.date) - target) < Math.abs(x(best.date) - target) ? p : best, points[0]);
      setSelected(nearest.date);
    }} onPointerLeave={() => setSelected(null)}>
      <title id={`${id}-title`}>{`${name}: cumulative profit ${signed(history.profit)}`}</title>
      <desc id={`${id}-description`}>{`${history.settled} settled selections, by match date. ${history.note || "Pending and void bets excluded."} Use the date slider below to inspect daily results.`}</desc>
      <defs><clipPath id={`${id}-positive`}><rect x="0" y="0" width={W} height={Math.max(0, zero)} /></clipPath><clipPath id={`${id}-negative`}><rect x="0" y={zero} width={W} height={H - zero} /></clipPath></defs>
      <line x1={left} x2={right} y1={zero} y2={zero} stroke="#64748b" strokeDasharray="3 4" />
      <text x={right} y={Math.max(10, zero - 5)} textAnchor="end" fill="#94a3b8" fontSize="10">0u</text>
      <path d={`${path} L ${x(points[points.length - 1].date)} ${zero} L ${left} ${zero} Z`} fill="#34d399" fillOpacity=".08" clipPath={`url(#${id}-positive)`} />
      <path d={`${path} L ${x(points[points.length - 1].date)} ${zero} L ${left} ${zero} Z`} fill="#fb7185" fillOpacity=".08" clipPath={`url(#${id}-negative)`} />
      <path d={path} fill="none" stroke="#34d399" strokeWidth="2" clipPath={`url(#${id}-positive)`} />
      <path d={path} fill="none" stroke="#fb7185" strokeWidth="2" clipPath={`url(#${id}-negative)`} />
      <line x1={x(active.date)} x2={x(active.date)} y1={top} y2={bottom} stroke="#94a3b8" strokeOpacity=".25" />
      <circle cx={x(active.date)} cy={y(active.cumulative)} r="3.5" fill={active.cumulative < 0 ? "#fb7185" : "#34d399"} stroke="#0f172a" strokeWidth="2" />
      <text x={left} y={151} fill="#94a3b8" fontSize="10">{dateLabel(range.from!)}</text><text x={right} y={151} textAnchor="end" fill="#94a3b8" fontSize="10">{dateLabel(points[points.length - 1].date)}</text>
    </svg>
    <input type="range" min={0} max={points.length - 1} value={activeIndex} onChange={e => setSelected(points[Number(e.target.value)].date)} aria-label={`Inspect ${name} profit by match date`} aria-valuetext={`${active.date}, cumulative ${signed(active.cumulative)}, day ${signed(active.profit)}`} className="mt-1 h-7 w-full accent-emerald-400" />
    <p className="flex flex-wrap justify-between gap-x-3 gap-y-1 text-xs tabular-nums"><span className="text-slate-400">{dateLabel(active.date)} · {active.settled} settled</span><span className={active.cumulative < 0 ? "text-rose-300" : "text-emerald-300"}>{signed(active.cumulative)} <span className="text-slate-400">total</span></span></p>
    <p className="mt-2 text-xs text-slate-400">Period change <span className={range.change < 0 ? "text-rose-300" : "text-emerald-300"}>{signed(range.change)}</span><span className="mx-2">·</span>Daily drawdown {range.drawdown.toFixed(2)}u</p>
    <p className="mt-2 text-[11px] leading-4 text-slate-500">By match date, through {points[points.length - 1].date}. {windowDays !== null ? `Last ${windowDays} calendar days ending on the latest result; opening balance retained. ` : ""}{history.note || "Same record as the figures above. No pending bets or historical replays added."}</p>
  </section>;
}
