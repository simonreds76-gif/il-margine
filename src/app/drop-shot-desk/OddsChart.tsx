"use client";

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode, Ref } from "react";
import styles from "./board.module.css";
import { DeskIcon, marketIcon } from "./DeskIcon";
import { marketName } from "./DeskParts";
import { amountText, displayedLimit, delta, outcomeLabel, outcomeOf, paper, price, slug, units, utcClock, utcDate, utcStamp } from "./desk";
import type { DeskMove } from "./desk";
import type { LimitRun } from "./types";

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

// Literal colours: the same drawing is serialised for the PNG, where CSS variables do not exist.
// They are Tennis Matchday's panel, line, ink and mint, so the chart sits straight on the stage
// with no frame of its own. C.bg must stay equal to --ds-surface in board.module.css.
const C = {
  bg: "#111a22", grid: "#22313b", hatch: "#33454f",
  ink: "#eef3f6", text: "#b7c6d0", mute: "#8497a4",
  mint: "#8ce5bd", amber: "#e0bb78", loss: "#ff9e8d",
} as const;
const FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
const SHARE_MARGIN = 56;
const SHARE_ICON_SIZE = 32;
const MIN = 60000;
const HOUR = 60 * MIN;
const X_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 180, 360, 720, 1440, 2880, 10080].map(v => v * MIN);
// The one place the limit series is named; the strip, the readout, the table and the PNG all use it.
const LIMIT_NAME = "Stake limit";
// Height the limit strip adds under the plot in the live chart: a caption row and the band itself.
const STRIP_H = 66;

type Pt = { i: number; t: number; time: string; price: number; other?: number; gap: boolean };
/**
 * One stretch of the limit strip in time order: a recorded run, or a stretch with no recorded limit.
 * A run is only ever as long as its evidence (first to last scan that saw the amount).
 */
type Span = {
  k: number; kind: "run" | "gap"; t0: number; t1: number; start: string; end: string;
  amount: number; currency: string; assumed: boolean; plot: boolean; joined: boolean; latest: boolean;
  change: "first" | "rise" | "fall" | "same" | "resumed" | "unjoined" | "gap"; was: number | null;
  why: "before" | "between" | "after" | "";
};
type Limits = { spans: Span[]; runs: Span[]; currency: string; assumed: boolean; mixed: boolean; first: number; last: number; latest: Span };
type Model = {
  pts: Pt[]; first: number; last: number; full: [number, number];
  tB: number; tA: number; tS: number; toStart: boolean; iB: number; iA: number; iL: number; multiDay: boolean;
  lim: Limits | null;
};
/** G is the left edge the gutter labels may reach; strip, when present, is the limit band under the plot. */
type Geo = { L: number; R: number; T: number; B: number; s: number; G?: number; strip?: { cap: number; T: number; B: number } };
type MarkRole = "earlier" | "detected" | "latest";
type KeyKind = MarkRole | "sample" | "break" | "limit" | "rise" | "fall";

const r2 = (n: number) => Math.round(n * 100) / 100;
const pct = (n: number) => r2(n * 100) + "%";
const clipText = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

/** Elapsed time in plain words; seconds only under two minutes. */
export function spanText(ms: number) {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms < 2 * MIN) return Math.round(ms / 1000) + " s";
  const m = Math.round(ms / MIN);
  if (m < 60) return m + " min";
  const h = Math.floor(m / 60), r = m % 60;
  return h < 48 ? h + " h" + (r ? " " + r + " min" : "") : Math.round(h / 24) + " d";
}

/** Gutter form of the same figure: abbreviated only where that loses nothing. */
function amountShort(n: number) {
  const full = amountText(n);
  if (full.length <= 6) return full;
  if (n >= 1e6 && n % 1e5 === 0) return n / 1e6 + "M";
  if (n >= 1e4 && n % 100 === 0) return n / 1e3 + "k";
  return full;
}

/**
 * Limit runs as their own series, never merged into the odds captures. Gaps are derived from the record only:
 * the time before the first recorded limit, any stretch between two runs that were not seen back to back, and
 * the time after the last recorded limit while odds were still being captured.
 */
function buildLimits(m: DeskMove, oddsFirst: number, oddsLast: number): Limits | null {
  const raw = (m as DeskMove & { limitRuns?: LimitRun[] }).limitRuns;
  if (!Array.isArray(raw) || !raw.length) return null;
  const iso = (t: number) => new Date(t).toISOString();
  const runs: Span[] = [];
  for (const r of raw) {
    const t0 = Date.parse(r.start), end = Date.parse(r.end);
    if (!Number.isFinite(t0) || typeof r.amount !== "number" || !Number.isFinite(r.amount)) continue;
    const t1 = Number.isFinite(end) && end > t0 ? end : t0;
    const code = typeof r.currency === "string" ? r.currency.trim().toUpperCase() : "";
    // Where the source names no currency, USD is assumed (and said so under the chart).
    runs.push({ k: 0, kind: "run", t0, t1, start: iso(t0), end: iso(t1), amount: r.amount, currency: code || "USD", assumed: !code,
      plot: true, joined: r.joined === true, latest: false, change: "first", was: null, why: "" });
  }
  if (!runs.length) return null;
  runs.sort((a, b) => a.t0 - b.t0 || a.t1 - b.t1);
  const latest = runs[runs.length - 1];
  latest.latest = true;
  let last = -Infinity;
  for (const r of runs) if (r.t1 > last) last = r.t1;

  const spans: Span[] = [];
  const gap = (t0: number, t1: number, why: Span["why"]) => spans.push({ k: 0, kind: "gap", t0, t1, start: iso(t0), end: iso(t1),
    amount: NaN, currency: "", assumed: false, plot: false, joined: false, latest: false, change: "gap", was: null, why });
  if (Number.isFinite(oddsFirst) && oddsFirst < runs[0].t0 - MIN) gap(oddsFirst, runs[0].t0, "before");
  runs.forEach((r, i) => {
    // The strip has one scale, so it plots the currency of the latest limit; any other is listed, not drawn.
    r.plot = r.currency === latest.currency;
    const prev = i ? runs[i - 1] : null;
    if (prev) {
      const same = prev.currency === r.currency;
      const apart = r.t0 > prev.t1 + 1000;
      r.joined = r.joined && same;
      r.was = same ? prev.amount : null;
      r.change = !r.joined ? (apart ? "resumed" : "unjoined") : r.amount > prev.amount ? "rise" : r.amount < prev.amount ? "fall" : "same";
      if (!r.joined && apart) gap(prev.t1, r.t0, "between");
    }
    spans.push(r);
  });
  if (Number.isFinite(oddsLast) && oddsLast > last + MIN) gap(last, oddsLast, "after");
  spans.forEach((sp, k) => { sp.k = k; });
  return { spans, runs, currency: latest.currency, assumed: runs.some(r => r.assumed), mixed: runs.some(r => !r.plot), first: runs[0].t0, last, latest };
}

/** What a stretch of the strip is, in words: used by the readout and by the table. */
function spanNote(sp: Span) {
  if (sp.kind === "gap") {
    return sp.why === "before" ? "Before limit tracking began" : sp.why === "after" ? "No limit recorded after the last one" : "No limit recorded";
  }
  const was = sp.was !== null ? displayedLimit(sp.was, sp.currency) : "";
  const before = was && sp.was !== sp.amount ? ", " + was + " before it" : "";
  const head = sp.change === "first" ? "First recorded limit"
    : sp.change === "rise" ? "Raised from " + was
    : sp.change === "fall" ? "Lowered from " + was
    : sp.change === "same" ? "Continues unchanged"
    : sp.change === "resumed" ? "Recorded again after a gap" + before
    : "Not joined to the previous limit" + before;
  return head + (sp.latest ? " · latest" : "") + (sp.plot ? "" : " · other currency, not on the strip");
}

function buildModel(m: DeskMove): Model {
  const pts: Pt[] = [];
  for (const q of m.quotes ?? []) {
    const t = Date.parse(q.time);
    if (Number.isFinite(t) && Number.isFinite(q.price)) pts.push({ i: pts.length, t, time: q.time, price: q.price, other: q.other, gap: q.gap === true });
  }
  const tB = Date.parse(m.before), tA = Date.parse(m.after), tS = Date.parse(m.start);
  const find = (t: number) => {
    if (!Number.isFinite(t)) return -1;
    const exact = pts.findIndex(p => p.t === t);
    return exact >= 0 ? exact : pts.findIndex(p => Math.abs(p.t - t) < 1000);
  };
  let first = Infinity, last = -Infinity;
  for (const p of pts) { if (p.t < first) first = p.t; if (p.t > last) last = p.t; }
  const lim = buildLimits(m, pts.length ? first : NaN, pts.length ? last : NaN);
  if (!pts.length) { first = Number.isFinite(tB) ? tB : 0; last = Number.isFinite(tA) ? tA : first; }
  // The time axis covers both series: the odds captures and the limit runs.
  const lo = lim ? Math.min(first, lim.first) : first, hi = lim ? Math.max(last, lim.last) : last;
  // As in the original templates the axis ends on the scheduled start, but only when the
  // empty tail that adds is at most half the recorded span, so the move is never squeezed.
  const toStart = hi > lo && Number.isFinite(tS) && tS > hi && tS - hi <= 0.5 * (hi - lo);
  const full: [number, number] = toStart ? [lo, tS] : hi > lo ? [lo, hi] : [lo - 30 * MIN, lo + 30 * MIN];
  return { pts, first, last, full, tB, tA, tS, toStart, iB: find(tB), iA: find(tA), iL: pts.length - 1, multiDay: utcDate(full[0]) !== utcDate(full[1]), lim };
}

function niceStep(raw: number) {
  const safe = Math.max(raw, 1e-6);
  const pow = Math.pow(10, Math.floor(Math.log10(safe)));
  const n = safe / pow;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return Math.max(0.01, Number((m * pow).toFixed(6)));
}

/** Linear time on x, linear decimal odds on y with the higher price drawn higher. */
function layout(model: Model, view: [number, number], g: Geo) {
  const { pts } = model;
  const t0 = view[0], t1 = view[1];
  const span = Math.max(1, t1 - t0);
  const inset = 12 * g.s;
  const inner = Math.max(1, g.R - g.L - 2 * inset);
  const x = (t: number) => g.L + inset + ((t - t0) / span) * inner;
  const tAt = (px: number) => t0 + ((px - g.L - inset) / inner) * span;
  const inView = (t: number) => t >= t0 && t <= t1;

  let basis = pts.filter(p => inView(p.t));
  const visible = basis.length;
  if (!basis.length) {
    basis = [...pts.filter(p => p.t < t0).slice(-1), ...pts.filter(p => p.t > t1).slice(0, 1)];
    if (!basis.length) basis = pts;
  }
  let lo = Infinity, hi = -Infinity;
  for (const p of basis) { if (p.price < lo) lo = p.price; if (p.price > hi) hi = p.price; }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) { lo = 1; hi = 2; }
  const least = Math.max(0.04, hi * 0.02);
  if (hi - lo < least) { const mid = (hi + lo) / 2; lo = mid - least / 2; hi = mid + least / 2; }
  // A little air above and below the extremes, so no mark ever sits on the frame.
  const padY = 18 * g.s;
  const k = Math.max(1, g.B - g.T - 2 * padY) / (hi - lo);
  const y = (p: number) => g.T + padY + (hi - p) * k;
  const pTop = hi + padY / k, pBot = lo - padY / k;

  const wantY = Math.max(2, Math.min(6, Math.floor((g.B - g.T) / (46 * g.s))));
  const stepY = niceStep((pTop - pBot) / wantY);
  const yTicks: number[] = [];
  for (let v = Math.ceil(pBot / stepY) * stepY, n = 0; v <= pTop + 1e-9 && n < 60; v += stepY, n += 1) {
    const tick = Number(v.toFixed(4));
    const py = y(tick);
    if (tick >= 1 && py > g.T + 8 * g.s && py < g.B - 4 * g.s) yTicks.push(tick);
  }

  const maxX = Math.max(2, Math.floor((g.R - g.L) / (84 * g.s)));
  const stepX = X_STEPS.find(step => span / step <= maxX) ?? X_STEPS[X_STEPS.length - 1];
  const xTicks: number[] = [];
  for (let t = Math.ceil(t0 / stepX) * stepX; t <= t1 && xTicks.length < 40; t += stepX) xTicks.push(t);

  return { t0, t1, x, y, tAt, inView, visible, yTicks, xTicks, stepX };
}
type Lay = ReturnType<typeof layout>;

/**
 * The only marks on the line. The pair that makes the move: a hollow ring in the line's
 * own colour for the earlier odds, a solid mint dot where the move was observed. The
 * latest observation, when it is a third point, is a small plain dot at the line's end.
 */
function mark(role: MarkRole, cx: number, cy: number, s: number): ReactNode {
  if (role === "earlier") return <circle cx={cx} cy={cy} r={4.6 * s} fill={C.bg} stroke={C.text} strokeWidth={2 * s} />;
  if (role === "detected") return <circle cx={cx} cy={cy} r={5.4 * s} fill={C.mint} stroke={C.bg} strokeWidth={2 * s} />;
  return <circle cx={cx} cy={cy} r={3 * s} fill={C.ink} stroke={C.bg} strokeWidth={1.5 * s} />;
}

/** The arrowhead seated on a limit change: up where the limit was raised, down where it was lowered. */
function tri(up: boolean, cx: number, cy: number, s: number): ReactNode {
  const w = 3.8 * s, h = 3.3 * s, d = up ? -1 : 1;
  return <path d={`M${r2(cx)} ${r2(cy + d * h)}L${r2(cx + w)} ${r2(cy - d * h)}H${r2(cx - w)}Z`}
    fill={C.ink} stroke={C.bg} strokeWidth={1.2 * s} strokeLinejoin="round" />;
}

function keyMark(kind: KeyKind, cx: number, cy: number, s: number): ReactNode {
  if (kind === "sample") return <circle cx={cx} cy={cy} r={2.6 * s} fill={C.text} />;
  if (kind === "break") return <>
    <rect x={cx - 9 * s} y={cy - 7 * s} width={18 * s} height={14 * s} fill="none" stroke={C.hatch} strokeWidth={s} />
    <path d={`M${cx - 8 * s} ${cy + 2 * s}l${8 * s} ${-8 * s}M${cx - 4 * s} ${cy + 6 * s}l${12 * s} ${-12 * s}M${cx + 2 * s} ${cy + 6 * s}l${6 * s} ${-6 * s}`}
      fill="none" stroke={C.mute} strokeWidth={1.4 * s} />
  </>;
  if (kind === "limit") return <>
    <path d={`M${cx - 1 * s} ${cy + 4 * s}V${cy - 4 * s}`} fill="none" stroke={C.mute} strokeWidth={1.2 * s} />
    <path d={`M${cx - 8 * s} ${cy + 4 * s}H${cx - 1 * s}M${cx - 1 * s} ${cy - 4 * s}H${cx + 8 * s}`} fill="none" stroke={C.text} strokeWidth={2 * s} />
  </>;
  if (kind === "rise" || kind === "fall") return tri(kind === "rise", cx, cy, 1.5 * s);
  return mark(kind, cx, cy, s);
}

/** Legend swatch that reuses the exact marks drawn on the chart. */
export function KeyGlyph({ kind }: { kind: KeyKind }) {
  return <svg className={styles.glyph} width="18" height="18" viewBox="-10 -10 20 20" aria-hidden="true" focusable="false">
    {keyMark(kind, 0, 0, 1)}
  </svg>;
}

function PlotLayer({ model, move, lay, g, uid, annotate, active = null, brush = null }: {
  model: Model; move: DeskMove; lay: Lay; g: Geo; uid: string; annotate: boolean;
  active?: number | null; brush?: { a: number; b: number } | null;
}) {
  const { pts, tA, tB, iA, iB, iL } = model;
  const { x, y, inView } = lay;
  const { L, R, T, B, s } = g;
  // One time axis for everything drawn: with a limit strip the clock is written under the strip, not under the plot.
  const AX = g.strip ? g.strip.B : B;
  const fs = 12 * s;
  const small = R - L < 470 * s;
  const clipId = uid + "-clip", hatchId = uid + "-hatch";
  const clampX = (v: number) => Math.max(L, Math.min(R, v));

  const seg = (from: number, to: number) => {
    let d = "";
    for (let i = from; i <= to; i += 1) d += (i === from || pts[i].gap ? "M" : "L") + r2(x(pts[i].t)) + " " + r2(y(pts[i].price)) + " ";
    return d.trim();
  };
  const key = (i: number, t: number, p: number) =>
    i >= 0 ? { t: pts[i].t, x: x(pts[i].t), y: y(pts[i].price) }
      : Number.isFinite(t) && Number.isFinite(p) ? { t, x: x(t), y: y(p) } : null;
  const kB = key(iB, tB, move.old);
  const kA = key(iA, tA, move.new);
  const kL = iL >= 0 && iL !== iA && iL !== iB ? key(iL, NaN, NaN) : null;
  // The line tells the story. A dot is drawn only where the line cannot: a capture that no
  // segment joins, or a series so short that every observation is a landmark of its own.
  const lone = (i: number) => (i === 0 || pts[i].gap) && (i === pts.length - 1 || pts[i + 1].gap);
  const sparse = !!move.chartSummary || pts.length <= 6;
  const segments = 1 + pts.filter((p, i) => i > 0 && p.gap).length;

  // The move itself: a faint band between its two captures, closed by a hairline at the later one.
  // Nothing is written on the plot; times, odds and roles are read under the chart.
  const hasA = Number.isFinite(tA), hasB = Number.isFinite(tB);
  const pair = hasA && hasB && tA > tB;
  const xA = hasA ? x(tA) : NaN, xB = hasB ? x(tB) : NaN;
  const bandOn = pair && tA >= lay.t0 && tB <= lay.t1;

  const edgeOnly = lay.xTicks.length < 2;
  const dayStep = lay.stepX >= 1440 * MIN;
  const hover = active !== null && pts[active] && inView(pts[active].t) ? pts[active] : null;

  // Scheduled start: the solid axis-coloured line the original charts end on. Clock ticks that would run into its label give way.
  const tS = model.tS;
  const startOn = Number.isFinite(tS) && inView(tS);
  const xS = startOn ? x(tS) : NaN;
  const nearStart = (px: number) => startOn && Math.abs(px - xS) < (small ? 62 : 100) * s;
  const startAnchor = !startOn ? "middle" : xS > R - 60 * s ? "end" : xS < L + 60 * s ? "start" : "middle";
  const startAt = startAnchor === "end" ? R : startAnchor === "start" ? L : xS;

  return <g>
    <defs>
      <clipPath id={clipId}><rect x={L} y={T} width={R - L} height={B - T} /></clipPath>
      <pattern id={hatchId} width={7 * s} height={7 * s} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2={7 * s} stroke={C.hatch} strokeWidth={2 * s} />
      </pattern>
    </defs>

    <g fontSize={fs} fill={C.text}>
      {lay.yTicks.map(v => <g key={v}>
        <path d={`M${L} ${r2(y(v))}H${R}`} stroke={C.grid} strokeWidth={s} />
        <text x={L - 8 * s} y={r2(y(v) + 4 * s)} textAnchor="end">{v.toFixed(2)}</text>
      </g>)}
      <path d={`M${L} ${B}H${R}`} stroke={C.grid} strokeWidth={s} />
      {!edgeOnly && lay.xTicks.map((t, i) => {
        const px = r2(x(t));
        const withDate = !dayStep && (i === 0 || utcDate(t) !== utcDate(lay.xTicks[i - 1]));
        return <g key={t}>
          <path d={`M${px} ${T}V${AX + 5 * s}`} stroke={C.grid} strokeWidth={s} strokeDasharray={`${s} ${4 * s}`} />
          {!nearStart(px) && <text x={px} y={AX + 19 * s} textAnchor="middle" fill={C.ink}>{dayStep ? utcDate(t) : utcClock(t)}</text>}
          {withDate && !nearStart(px) && <text x={px} y={AX + 33 * s} textAnchor="middle" fill={C.mute} fontSize={fs * 0.92}>{utcDate(t)}</text>}
        </g>;
      })}
      {edgeOnly && <>
        <text x={L + 12 * s} y={AX + 19 * s} fill={C.ink}>{utcClock(lay.t0, true)}</text>
        <text x={L + 12 * s} y={AX + 33 * s} fill={C.mute} fontSize={fs * 0.92}>{utcDate(lay.t0)}</text>
        {!nearStart(R - 12 * s) && <text x={R - 12 * s} y={AX + 19 * s} textAnchor="end" fill={C.ink}>{utcClock(lay.t1, true)}</text>}
      </>}
      <text x={L - 8 * s} y={AX + 19 * s} textAnchor="end" fill={C.mute} fontSize={fs * 0.92}>UTC</text>
    </g>

    {startOn && <g {...(annotate ? { "data-role": "scheduled-start", "data-time": move.start } : {})}>
      <path d={`M${r2(xS)} ${T}V${AX + 5 * s}`} stroke={C.mute} strokeWidth={s} />
      <text x={r2(startAt)} y={AX + 19 * s} textAnchor={startAnchor} fontSize={fs} fill={C.ink}>{small ? "Start" : "Scheduled start"}</text>
      <text x={r2(startAt)} y={AX + 33 * s} textAnchor={startAnchor} fontSize={fs * 0.92} fill={C.mute}>{utcClock(tS) + " UTC"}</text>
    </g>}

    <g clipPath={`url(#${clipId})`}>
      {pts.map((p, i) => i > 0 && p.gap
        ? <rect key={"gap" + p.i} x={r2(x(pts[i - 1].t))} y={T} width={r2(Math.max(0, x(p.t) - x(pts[i - 1].t)))} height={B - T} fill={`url(#${hatchId})`}
          {...(annotate ? { "data-role": "capture-break", "data-from": pts[i - 1].time, "data-to": p.time } : {})} />
        : null)}
      {bandOn && <rect x={r2(clampX(xB))} y={T} width={r2(Math.max(0, clampX(xA) - clampX(xB)))} height={B - T} fill={C.mint} fillOpacity={0.09}
        {...(annotate ? { "data-role": "move-interval", "data-from": move.before, "data-to": move.after } : {})} />}
      {hasA && <path d={`M${r2(xA)} ${T}V${B}`} stroke={C.mint} strokeOpacity={0.4} strokeWidth={s}
        {...(annotate ? { "data-role": "detection-line", "data-time": move.after } : {})} />}
      <path d={seg(0, pts.length - 1)} fill="none" stroke={C.text} strokeWidth={1.8 * s} strokeLinejoin="round" strokeLinecap="round"
        {...(annotate ? { "data-role": "series", "data-segments": segments, "data-interpolation": move.chartSummary ? "selected-observations" : "straight-between-consecutive-captures" } : {})} />
      {iB >= 0 && iA > iB && <path d={seg(iB, iA)} fill="none" stroke={C.mint} strokeWidth={2.6 * s} strokeLinejoin="round" strokeLinecap="round"
        {...(annotate ? { "data-role": "move" } : {})} />}
      {pts.map(p => {
        const roles = [p.i === iB && "earlier", p.i === iA && "detected", p.i === iL && "latest"].filter(Boolean).join(" ") || "sample";
        const after = hasA && p.t > tA;
        const data = annotate ? {
          "data-index": p.i, "data-time": p.time, "data-price": p.price, "data-other": p.other, "data-role": roles,
          "data-phase": after ? "after-detection" : "to-detection", "data-gap": p.gap ? "true" : undefined, "data-in-view": String(inView(p.t)),
        } : {};
        // Every observation stays in the live drawing with its data; only the ones the line cannot show are painted.
        const shown = sparse || lone(p.i);
        if (!shown && !annotate) return null;
        return <circle key={p.i} cx={r2(x(p.t))} cy={r2(y(p.price))} r={2.6 * s} fill={C.text} stroke={C.bg} strokeWidth={1.2 * s} opacity={shown ? 1 : 0} {...data}>
          {annotate && <title>{`${utcStamp(p.t, true)} · ${price(p.price)}`}</title>}
        </circle>;
      })}
      {kB && mark("earlier", r2(kB.x), r2(kB.y), s)}
      {kL && mark("latest", r2(kL.x), r2(kL.y), s)}
      {kA && mark("detected", r2(kA.x), r2(kA.y), s)}
    </g>

    {pts.map((p, i) => {
      if (i === 0 || !p.gap) return null;
      const a = Math.max(L, x(pts[i - 1].t)), b = Math.min(R, x(p.t));
      return b - a > 64 * s
        ? <text key={"gapLabel" + p.i} x={r2((a + b) / 2)} y={r2(T + 16 * s)} textAnchor="middle" fontSize={11 * s} fill={C.mute}
          stroke={C.bg} strokeWidth={4 * s} strokeLinejoin="round" paintOrder="stroke">break in capture</text>
        : null;
    })}

    {/* The observation in hand: a hairline to the axis and a ring; a plain capture also gets its dot, a marked one keeps its mark. */}
    {hover && <g pointerEvents="none">
      <path d={`M${r2(x(hover.t))} ${T}V${B}`} stroke={C.ink} strokeOpacity={0.3} strokeWidth={s} />
      {hover.i !== iA && hover.i !== iB && <circle cx={r2(x(hover.t))} cy={r2(y(hover.price))} r={3.4 * s} fill={C.ink} stroke={C.bg} strokeWidth={1.5 * s} />}
      <circle cx={r2(x(hover.t))} cy={r2(y(hover.price))} r={9 * s} fill="none" stroke={C.ink} strokeOpacity={0.85} strokeWidth={1.4 * s} />
    </g>}
    {brush && <rect x={r2(Math.min(brush.a, brush.b))} y={T} width={r2(Math.abs(brush.b - brush.a))} height={B - T} fill={C.ink} fillOpacity={0.1} stroke={C.text} strokeWidth={s} pointerEvents="none" />}
  </g>;
}

/** Rough advance width of UI-sans text; used only to seat a mark beside a right-aligned caption. */
function textW(text: string, size: number, tracking = 0) {
  let em = 0;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    em += ch >= "0" && ch <= "9" ? 0.56 : ch >= "A" && ch <= "Z" ? 0.66 : ch >= "a" && ch <= "z" ? 0.52 : 0.27;
  }
  return em * size + tracking * text.length;
}

/**
 * The limit strip: its own band under the odds, on the plot's time scale, drawn into the same SVG so the
 * live chart and the PNG carry the identical strip. It shows the record and nothing else:
 * a level only between the first and last scan that saw that amount, a thin join only where a change was
 * seen with no gap (an arrowhead says raised or lowered), hatching wherever no limit was recorded.
 * The band runs from the lowest to the highest recorded limit in view, both labelled; there is no zero
 * line, no fill down to a floor and no run carried on to the scheduled start.
 * Must be rendered after PlotLayer with the same uid: it reuses that layer's hatch pattern.
 */
function LimitLayer({ model, lay, g, uid, annotate, activeSpan = null, hoverT = null }: {
  model: Model; lay: Lay; g: Geo; uid: string; annotate: boolean; activeSpan?: number | null; hoverT?: number | null;
}) {
  const lim = model.lim, st = g.strip;
  if (!lim || !st) return null;
  const { L, R, s } = g;
  const { x } = lay;
  const clipId = uid + "-limit-clip", hatchId = uid + "-hatch";
  const seen = (sp: Span) => sp.t1 >= lay.t0 && sp.t0 <= lay.t1;
  const plotted = lim.runs.filter(r => r.plot);
  let basis = plotted.filter(seen);
  if (!basis.length) basis = plotted;
  let lo = Infinity, hi = -Infinity;
  for (const r of basis) { if (r.amount < lo) lo = r.amount; if (r.amount > hi) hi = r.amount; }
  const pad = 8 * s, mid = (st.T + st.B) / 2;
  const y = (a: number) => (hi > lo ? st.T + pad + ((hi - a) / (hi - lo)) * (st.B - st.T - 2 * pad) : mid);

  // Gutter labels are the recorded extremes themselves, shrunk rather than rounded when they are long.
  const cap = 11 * s, room = Math.max(8 * s, L - 8 * s - (g.G ?? 0));
  const edge = (a: number) => {
    const text = amountShort(a), size = Math.min(cap, (cap * room) / Math.max(1, textW(text, cap)));
    return <text key={a} x={L - 8 * s} y={r2(y(a) + size * 0.36)} textAnchor="end" fontSize={r2(size)} fill={C.text}>{text}</text>;
  };
  const tight = R - L < 250 * s;
  const halo = { stroke: C.bg, strokeWidth: 4 * s, strokeLinejoin: "round" as const, paintOrder: "stroke" };
  const tA = model.tA, detOn = Number.isFinite(tA) && tA >= lay.t0 && tA <= lay.t1;
  const held = hoverT === null ? undefined : plotted.find(r => hoverT >= r.t0 && hoverT <= r.t1);
  const act = activeSpan !== null ? lim.spans[activeSpan] : undefined;
  let lastArrow = -Infinity;

  return <g {...(annotate ? { "data-role": "limit-strip", "data-currency": lim.currency, "data-runs": lim.runs.length } : {})}>
    <defs><clipPath id={clipId}><rect x={L} y={st.T} width={R - L} height={st.B - st.T} /></clipPath></defs>
    <path d={`M${L} ${st.B}H${R}`} stroke={C.grid} strokeWidth={s} />
    {Number.isFinite(lo) && (hi > lo ? [hi, lo].map(edge) : edge(lo))}

    <g clipPath={`url(#${clipId})`}>
      {lim.spans.map(sp => {
        if ((sp.kind === "run" && sp.plot) || !seen(sp)) return null;
        const a = Math.max(L, x(sp.t0)), b = Math.min(R, x(sp.t1));
        if (b <= a) return null;
        const words = sp.kind === "run" ? "quoted in " + sp.currency : sp.why === "before" ? "before limit tracking" : "no limit recorded";
        return <g key={"g" + sp.k}>
          <rect x={r2(a)} y={st.T} width={r2(b - a)} height={st.B - st.T} fill={`url(#${hatchId})`}
            {...(annotate ? { "data-role": sp.kind === "run" ? "limit-other-currency" : "limit-gap", "data-why": sp.why || undefined, "data-from": sp.start, "data-to": sp.end } : {})} />
          {b - a > textW(words, 11 * s) + 18 * s && <text x={r2((a + b) / 2)} y={r2(mid + 4 * s)} textAnchor="middle" fontSize={11 * s} fill={C.mute} {...halo}>{words}</text>}
        </g>;
      })}
      {detOn && <path d={`M${r2(x(tA))} ${st.T}V${st.B}`} stroke={C.mint} strokeOpacity={0.4} strokeWidth={s} />}
      {/* Joins first, so the recorded levels sit on top of them. A join spans only the two scans either side of the change. */}
      {lim.runs.map((r, i) => {
        const p = i ? lim.runs[i - 1] : null;
        if (!p || !r.joined || !r.plot || !p.plot) return null;
        return <path key={"j" + r.k} d={`M${r2(x(p.t1))} ${r2(y(p.amount))}L${r2(x(r.t0))} ${r2(y(r.amount))}`} fill="none" stroke={C.mute} strokeWidth={1.2 * s} />;
      })}
      {plotted.map(r => {
        const a = x(r.t0), b = x(r.t1), py = r2(y(r.amount));
        const data = annotate ? { "data-role": "limit-run", "data-from": r.start, "data-to": r.end, "data-amount": r.amount, "data-currency": r.currency,
          "data-change": r.change, "data-joined": String(r.joined), "data-latest": r.latest ? "true" : undefined } : {};
        // A limit seen at a single scan has no length to draw: it is a dot, like a lone odds capture.
        return b - a < 3 * s
          ? <circle key={"r" + r.k} cx={r2((a + b) / 2)} cy={py} r={2.6 * s} fill={C.text} stroke={C.bg} strokeWidth={1.2 * s} {...data} />
          : <path key={"r" + r.k} d={`M${r2(a)} ${py}H${r2(b)}`} fill="none" stroke={C.text} strokeWidth={2 * s} {...data} />;
      })}
      {lim.runs.map((r, i) => {
        if (!i || !r.plot || (r.change !== "rise" && r.change !== "fall")) return null;
        const p = lim.runs[i - 1], cx = (x(p.t1) + x(r.t0)) / 2;
        // Where changes crowd, the steps themselves still show the direction; arrowheads thin out instead of piling up.
        if (cx < L || cx > R || cx - lastArrow < 10 * s) return null;
        lastArrow = cx;
        return <g key={"a" + r.k}>{tri(r.change === "rise", cx, (y(p.amount) + y(r.amount)) / 2, s)}</g>;
      })}
      {lim.latest.plot && mark("latest", r2(x(lim.latest.t1)), r2(y(lim.latest.amount)), s)}

      {/* The stretch in hand: its level redrawn in ink between two end ticks, or the gap outlined. */}
      {act && seen(act) && (act.kind === "run" && act.plot
        ? <g pointerEvents="none">
          <path d={`M${r2(x(act.t0))} ${r2(y(act.amount))}H${r2(x(act.t1))}`} fill="none" stroke={C.ink} strokeWidth={3 * s} strokeLinecap="round" />
          <path d={`M${r2(x(act.t0))} ${r2(y(act.amount) - 6 * s)}v${12 * s}M${r2(x(act.t1))} ${r2(y(act.amount) - 6 * s)}v${12 * s}`} fill="none" stroke={C.ink} strokeWidth={1.4 * s} />
        </g>
        : <rect x={r2(Math.max(L, x(act.t0)))} y={st.T + s} width={r2(Math.max(0, Math.min(R, x(act.t1)) - Math.max(L, x(act.t0))))} height={st.B - st.T - 2 * s}
          fill="none" stroke={C.text} strokeWidth={1.4 * s} pointerEvents="none" />)}
      {/* The odds observation in hand, carried down: the same hairline, and a ring on the limit recorded at that moment. */}
      {hoverT !== null && hoverT >= lay.t0 && hoverT <= lay.t1 && <g pointerEvents="none">
        <path d={`M${r2(x(hoverT))} ${st.T}V${st.B}`} stroke={C.ink} strokeOpacity={0.3} strokeWidth={s} />
        {held && <circle cx={r2(x(hoverT))} cy={r2(y(held.amount))} r={5 * s} fill="none" stroke={C.ink} strokeOpacity={0.85} strokeWidth={1.4 * s} />}
      </g>}
    </g>

    <text x={L} y={st.cap} fontSize={10.5 * s} fontWeight="600" letterSpacing={0.9 * s} fill={C.mute} {...halo}>
      {(tight ? "LIMIT" : LIMIT_NAME.toUpperCase()) + " · " + lim.currency}
    </text>
    <text x={R} y={st.cap} textAnchor="end" fontSize={11 * s} fill={C.mute} {...halo}>
      {"Latest "}<tspan fill={C.ink} fontWeight="600">{displayedLimit(lim.latest.amount, lim.latest.currency)}</tspan>
    </text>
  </g>;
}

/**
 * The fixed 1200 × 675 share card, rendered only while a download is in progress.
 * It stands alone on one grid: a three-row head (caption, figure, detail) with the
 * selection on the left and one pair of odds, each over its own capture time, on the
 * right; the plotted line across the full measure; one footer line. The pair carries
 * the same two marks as the line, so the card needs no key and repeats no figure.
 * With recorded limits the plot gives up its lower third to the limit strip, captioned
 * with its currency; the clock stays where it was, now under both.
 */
function ExportCard({ svgRef, model, move, view, archive, uid }: {
  svgRef: Ref<SVGSVGElement>; model: Model; move: DeskMove; view: [number, number]; archive: boolean; uid: string;
}) {
  const W = 1200, H = 675, M = SHARE_MARGIN;
  const lim = model.lim;
  const g: Geo = lim
    ? { L: 112, R: W - M, T: 240, B: 446, s: 1.4, G: M, strip: { cap: 467, T: 474, B: 528 } }
    : { L: 112, R: W - M, T: 240, B: 528, s: 1.4, G: M };
  const lay = layout(model, view, g);
  const outcome = outcomeOf(move.result), pl = paper(move);
  const tone = outcome === "won" ? C.mint : outcome === "lost" ? C.loss : C.text;
  const label = archive && !move.market ? "" : marketName(move);
  const icon = label ? marketIcon(move.market) : null;
  const competition = move.league.toLowerCase().startsWith(move.tour.toLowerCase() + " ")
    ? move.league : move.tour + " · " + move.league;
  const nameSize = move.player.length > 30 ? 30 : move.player.length > 24 ? 36 : move.player.length > 18 ? 42 : 46;

  // The pair: two right-aligned columns of equal width, sized so the longest price still clears the name.
  const was = price(move.old), now = price(move.new);
  const chars = Math.max(was.length, now.length);
  const big = chars <= 5 ? 64 : chars === 6 ? 56 : 48;
  const colW = Math.max(150, Math.max(textW(was, big), textW(now, big)) * 1.1);
  const xNow = W - M, xWas = xNow - colW - big * 1.2, xArrow = xNow - colW - big * 0.6;
  const yCap = 98, yBig = 158, yDetail = 190;
  const yArrow = yBig - big * 0.33, arrow = big * 0.26;
  const capSize = 12.5, capTrack = 1.6;
  const leg = (role: "earlier" | "detected", cap: string, val: string, when: string, xr: number) => {
    const strong = role === "detected";
    return <g>
      {mark(role, r2(xr - textW(cap, capSize, capTrack) - 13), yCap - 4.5, 1.15)}
      <text x={xr} y={yCap} textAnchor="end" fontSize={capSize} fontWeight="600" letterSpacing={capTrack} fill={strong ? C.mint : C.mute}>{cap}</text>
      <text x={xr} y={yBig} textAnchor="end" fontSize={big} fontWeight={strong ? 700 : 400} letterSpacing={r2(-big * 0.03)} fill={strong ? C.mint : C.text}>{val}</text>
      <text x={xr} y={yDetail} textAnchor="end" fontSize="18" fill={strong ? C.ink : C.text}>{when}</text>
    </g>;
  };

  // The footer says only what the drawing cannot: the scheduled start when it falls outside the plot,
  // a recorded score, the replay stake, and how the line was drawn.
  const startShown = Number.isFinite(model.tS) && lay.inView(model.tS);
  const context = [
    !startShown && Number.isFinite(model.tS) ? "Scheduled start " + utcStamp(move.start) : "",
    move.score ? clipText(move.score, 40) : "",
    archive && pl !== null ? "Historical replay: 1u at the odds of the observed move" : "",
  ].filter(Boolean).join(" · ");
  // With a limit strip the same line also names its currency and says that a limit is a quote, not a stake.
  const method = lim
    ? (move.chartSummary
      ? "Decimal odds, UTC. Selected odds observations only; gaps stay open."
      : "Decimal odds, UTC. Lines join consecutive captures; breaks stay open.")
      + ` ${LIMIT_NAME}s show the reported maximum in ${lim.currency}. Actual turnover is unknown.`
    : move.chartSummary
      ? "Decimal odds, times in UTC. Selected observations only: earlier, observed move, later low, high and latest. Known gaps are left open."
      : "Decimal odds, times in UTC. The line joins consecutive recorded captures only; breaks in capture are left open.";

  return <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" width={W} height={H} viewBox={`0 0 ${W} ${H}`} fontFamily={FONT}>
    <rect width={W} height={H} fill={C.bg} />
    <rect width={W} height="6" fill={archive ? C.amber : C.mint} />
    <text x={M + SHARE_ICON_SIZE + 10} y="52" fontSize="14" fontWeight="700" letterSpacing="2.2" fill={C.mint}>
      IL MARGINE<tspan fill={C.mute} fontWeight="500">{" · DROP SHOT DESK" + (archive ? " · HISTORICAL REPLAY" : "")}</tspan>
    </text>
    <text x={W - M} y="52" textAnchor="end" fontSize="14" letterSpacing="1.2" fill={C.mute}>{clipText(competition, 46).toUpperCase()}</text>

    {label && <>
      {icon && <DeskIcon name={icon} size={18} x={M} y={yCap - 14} color={C.text} />}
      <text x={icon ? M + 26 : M} y={yCap} fontSize={capSize} fontWeight="600" letterSpacing={capTrack} fill={C.text}>{label.toUpperCase()}</text>
    </>}
    <text x={M} y={yBig} fontSize={nameSize} fontWeight="700" letterSpacing={r2(-nameSize * 0.03)} fill={C.ink}>{clipText(move.player, 34)}</text>
    <text x={M} y={yDetail} fontSize="18" fill={C.text}>{clipText(move.fixtureLabel ?? ("vs " + move.opponent), 40)}</text>

    {leg("earlier", "EARLIER", was, utcStamp(move.before), xWas)}
    <path d={`M${r2(xArrow - arrow)} ${r2(yArrow)}H${r2(xArrow + arrow)}M${r2(xArrow + arrow - 7)} ${r2(yArrow - 7)}L${r2(xArrow + arrow)} ${r2(yArrow)}L${r2(xArrow + arrow - 7)} ${r2(yArrow + 7)}`}
      fill="none" stroke={C.mute} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    {leg("detected", "MOVE OBSERVED", now, utcStamp(move.after), xNow)}

    <rect x={M} y="214" width={W - 2 * M} height="1" fill={C.grid} />
    <PlotLayer model={model} move={move} lay={lay} g={g} uid={uid} annotate={false} />
    <LimitLayer model={model} lay={lay} g={g} uid={uid} annotate={false} />
    <rect x={M} y="596" width={W - 2 * M} height="1" fill={C.grid} />

    {context && <text x={M} y="613" fontSize="15" fill={C.text}>{context}</text>}
    <text x={M} y={context ? 633 : 617} fontSize="13.5" fill={C.mute}>{method}</text>
    <text x={M} y="657" fontSize="24" fontWeight="600" fill="#a7d6c3">ilmargine.bet</text>
    {outcome !== "pending" && <text x={W - M} y="634" textAnchor="end" fontSize="24" fontWeight="700" letterSpacing="1" fill={tone}>
      {clipText(outcomeLabel(move), 12).toUpperCase() + (archive && pl !== null ? " " + units(pl) : "")}
    </text>}
  </svg>;
}

async function savePng(svg: SVGSVGElement, w: number, h: number, name: string) {
  const xml = new XMLSerializer().serializeToString(svg);
  const url = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.src = url;
    const brandIcon = new Image();
    brandIcon.src = "/brand/20260913/icon-128.png";
    await Promise.all([image.decode(), brandIcon.decode()]);
    const canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas");
    ctx.scale(canvas.width / w, canvas.height / h);
    ctx.drawImage(image, 0, 0, w, h);
    // Draw the same-origin mark separately: an SVG rendered as an image cannot load external assets.
    ctx.drawImage(brandIcon, SHARE_MARGIN, 29, SHARE_ICON_SIZE, SHARE_ICON_SIZE);
    const blob = await new Promise<Blob | null>(done => canvas.toBlob(done, "image/png"));
    if (!blob) throw new Error("blob");
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 1500);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function OddsChart({ move, archive }: { move: DeskMove; archive: boolean }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const model = useMemo(() => buildModel(move), [move]);
  const { pts, full, lim } = model;
  const boxRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const exportRef = useRef<SVGSVGElement>(null);
  const drag = useRef<number | null>(null);
  const [W, setW] = useState(720);
  const [win, setWin] = useState<{ from: number; to: number; name: string } | null>(null);
  const [active, setActive] = useState<number | null>(null);
  // The stretch of the limit strip in hand. An odds observation and a limit stretch are never in hand together.
  const [activeSpan, setActiveSpan] = useState<number | null>(null);
  const [brush, setBrush] = useState<{ a: number; b: number } | null>(null);
  const [exporting, setExporting] = useState(false);
  const [note, setNote] = useState("");

  useIsoLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const apply = (w: number) => { const next = Math.max(260, Math.round(w)); if (next > 0) setW(next); };
    apply(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(entries => apply(entries[0].contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const fileName = "drop-shot-desk-" + slug(move.player) + "-" + (Number.isFinite(model.tA) ? new Date(model.tA).toISOString().slice(0, 16).replace(/[-:]/g, "").replace("T", "-") : "chart") + ".png";
  useEffect(() => {
    if (!exporting) return;
    let live = true;
    (async () => {
      try {
        if (!exportRef.current) throw new Error("missing");
        await savePng(exportRef.current, 1200, 675, fileName);
        if (live) setNote("Chart saved as a PNG image.");
      } catch {
        if (live) setNote("The chart could not be downloaded.");
      } finally {
        if (live) setExporting(false);
      }
    })();
    return () => { live = false; };
  }, [exporting, fileName]);

  // Phones get a taller plot; wide stages keep roughly 2:1. Nothing is written above the plot, so it starts at the top.
  // The limit strip, when there is one, is added under the plot: the odds keep the height they always had.
  const plotH = Math.round(W < 480 ? Math.min(330, Math.max(270, W * 0.82)) : Math.min(440, Math.max(280, W * 0.46)));
  const H = plotH + (lim ? STRIP_H : 0);
  const g: Geo = { L: W < 480 ? 44 : 50, R: W - 10, T: 12, B: plotH - 42, s: 1, G: 2,
    strip: lim ? { cap: plotH - 42 + 16, T: plotH - 42 + 22, B: H - 42 } : undefined };
  const view: [number, number] = win ? [win.from, win.to] : full;
  const lay = layout(model, view, g);

  const fullSpan = full[1] - full[0];
  const minSpan = Math.min(fullSpan, 2 * MIN);
  const canZoom = model.last > model.first ? pts.length >= 2 : !!lim && lim.last > lim.first && pts.length >= 1;
  const clampView = (a: number, b: number): [number, number] => {
    const span = Math.min(fullSpan, Math.max(minSpan, b - a));
    let from = b - a < minSpan ? (a + b) / 2 - span / 2 : a;
    from = Math.max(full[0], Math.min(full[1] - span, from));
    return [from, from + span];
  };
  const applyView = (a: number, b: number, name: string) => {
    const [from, to] = clampView(a, b);
    if (to - from >= fullSpan - 1) setWin(null); else setWin({ from, to, name });
  };
  const reset = () => setWin(null);
  const zoom = (factor: number) => {
    const [a, b] = view;
    const p = active !== null ? pts[active] : undefined;
    const sp = lim && activeSpan !== null ? lim.spans[activeSpan] : undefined;
    const mid = sp ? (Math.max(a, sp.t0) + Math.min(b, sp.t1)) / 2 : NaN;
    // Zoom about whatever is in hand, the odds observation or the limit stretch, else about the middle.
    const c = p && p.t >= a && p.t <= b ? p.t : mid >= a && mid <= b ? mid : (a + b) / 2;
    applyView(c - (c - a) * factor, c + (b - c) * factor, "custom");
  };
  const pan = (dir: number) => {
    const shift = (view[1] - view[0]) * 0.3 * dir;
    applyView(view[0] + shift, view[1] + shift, "custom");
  };

  const presets: { name: string; label: string; range: [number, number] | null }[] = [{ name: "all", label: "All", range: null }];
  if (canZoom) {
    const { tA, tB } = model;
    if (Number.isFinite(tA) && Number.isFinite(tB)) {
      const margin = Math.max((tA - tB) * 1.5, 15 * MIN);
      const range = clampView(tB - margin, tA + margin);
      if (range[1] - range[0] < fullSpan - 1) presets.push({ name: "move", label: "Around the move", range });
    }
    if (Number.isFinite(tA) && model.last > tA) {
      const range = clampView(tA - Math.max(MIN, (model.last - tA) * 0.08), model.last);
      if (range[1] - range[0] < fullSpan - 1) presets.push({ name: "after", label: "Since the move", range });
    }
    // "Final 2 h" only when the axis really ends on the scheduled start; otherwise it is the last 2 h of captures.
    if (fullSpan > 2 * HOUR) presets.push({ name: "2h", label: model.toStart ? "Final 2 h" : "Last 2 h", range: [full[1] - 2 * HOUR, full[1]] });
  }
  const current = win ? win.name : "all";

  const svgX = (clientX: number, el: SVGSVGElement | null) => {
    if (!el) return 0;
    const box = el.getBoundingClientRect();
    return (clientX - box.left) * (W / Math.max(1, box.width));
  };
  const nearest = (px: number) => {
    let best: number | null = null, dist = Infinity;
    for (const p of pts) {
      if (!lay.inView(p.t)) continue;
      // The two captures of the move win a near tie, so they stay reachable where captures crowd (phones, long series).
      const d = Math.abs(lay.x(p.t) - px) - (p.i === model.iA || p.i === model.iB ? 3 : 0);
      if (d < dist) { dist = d; best = p.i; }
    }
    return best;
  };
  const onDown = (e: PointerEvent<SVGRectElement>) => {
    const px = svgX(e.clientX, svgRef.current);
    if (e.pointerType === "mouse" && e.button === 0 && canZoom) {
      drag.current = px;
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* capture is optional */ }
    }
    setActiveSpan(null);
    setActive(nearest(px));
  };
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const px = svgX(e.clientX, svgRef.current);
    if (drag.current !== null) setBrush({ a: drag.current, b: Math.max(g.L, Math.min(g.R, px)) });
    setActiveSpan(null);
    setActive(nearest(px));
  };
  const onUp = (e: PointerEvent<SVGRectElement>) => {
    if (drag.current === null) return;
    const a = drag.current, b = Math.max(g.L, Math.min(g.R, svgX(e.clientX, svgRef.current)));
    drag.current = null;
    setBrush(null);
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already released */ }
    if (Math.abs(b - a) >= 14) applyView(lay.tAt(Math.min(a, b)), lay.tAt(Math.max(a, b)), "custom");
  };
  const onLeave = (e: PointerEvent<SVGRectElement>) => {
    if (drag.current === null && e.pointerType === "mouse") setActive(null);
  };
  const onCancel = () => { drag.current = null; setBrush(null); };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const n = pts.length;
    if (!n) return;
    let next: number | null = null;
    if (e.key === "ArrowRight") next = active === null ? Math.max(0, pts.findIndex(p => lay.inView(p.t))) : Math.min(n - 1, active + 1);
    else if (e.key === "ArrowLeft") next = active === null ? n - 1 : Math.max(0, active - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else if (e.key === "+" || e.key === "=") { if (canZoom) zoom(0.5); }
    else if (e.key === "-" || e.key === "_") { if (canZoom) zoom(2); }
    else if (e.key === "0") reset();
    else if (e.key === "Escape") { setActive(null); setActiveSpan(null); }
    else return;
    e.preventDefault();
    if (next !== null) {
      setActiveSpan(null);
      setActive(next);
      const t = pts[next].t;
      if (t < view[0] || t > view[1]) { const span = view[1] - view[0]; applyView(t - span / 2, t + span / 2, "custom"); }
    }
  };

  // The limit strip is read the same three ways as the line: point, tap, or arrow keys once it has focus.
  const spanInView = (sp: Span) => sp.t1 >= view[0] && sp.t0 <= view[1];
  const spanNear = (px: number) => {
    if (!lim) return null;
    let best: number | null = null, score = Infinity;
    for (const sp of lim.spans) {
      if (!spanInView(sp)) continue;
      const a = lay.x(sp.t0), b = lay.x(sp.t1);
      // A recorded limit wins a near tie with the gap beside it, so a single-scan limit can still be picked.
      const d = (px < a ? a - px : px > b ? px - b : 0) - (sp.kind === "run" ? 6 : 0);
      if (d < score) { score = d; best = sp.k; }
    }
    return best;
  };
  const onStrip = (e: PointerEvent<HTMLDivElement>) => {
    setActive(null);
    setActiveSpan(spanNear(svgX(e.clientX, svgRef.current)));
  };
  const onStripKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!lim) return;
    const n = lim.spans.length;
    let next: number | null = null;
    if (e.key === "ArrowRight") next = activeSpan === null ? Math.max(0, lim.spans.findIndex(spanInView)) : Math.min(n - 1, activeSpan + 1);
    else if (e.key === "ArrowLeft") next = activeSpan === null ? lim.latest.k : Math.max(0, activeSpan - 1);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else if (e.key === "Escape") { setActiveSpan(null); e.preventDefault(); e.stopPropagation(); return; }
    else return; // plus, minus and zero carry on to the chart, which zooms about the stretch in hand
    e.preventDefault();
    e.stopPropagation();
    setActive(null);
    setActiveSpan(next);
    const sp = lim.spans[next];
    if (sp && !spanInView(sp)) { const span = view[1] - view[0], c = (sp.t0 + sp.t1) / 2; applyView(c - span / 2, c + span / 2, "custom"); }
  };

  // Overview strip: the whole series with the current window marked.
  const navH = 40;
  let navLo = Infinity, navHi = -Infinity;
  for (const p of pts) { if (p.price < navLo) navLo = p.price; if (p.price > navHi) navHi = p.price; }
  const navX = (t: number) => g.L + ((t - full[0]) / Math.max(1, fullSpan)) * (g.R - g.L);
  const navY = (p: number) => (navHi > navLo ? 7 + ((navHi - p) / (navHi - navLo)) * (navH - 14) : navH / 2);
  const navPath = pts.map((p, i) => (i === 0 || p.gap ? "M" : "L") + r2(navX(p.t)) + " " + r2(navY(p.price))).join(" ");
  const onNav = (e: PointerEvent<SVGSVGElement>) => {
    if (!win) return;
    const px = svgX(e.clientX, e.currentTarget);
    const t = full[0] + ((px - g.L) / Math.max(1, g.R - g.L)) * fullSpan;
    const span = win.to - win.from;
    applyView(t - span / 2, t + span / 2, "custom");
  };

  if (!pts.length) {
    return <figure className={styles.figure}>
      <p className={styles.empty} role="status">No recorded prices are available for this selection.</p>
    </figure>;
  }

  const latest = pts[model.iL];
  const latestDistinct = model.iL !== model.iA && model.iL !== model.iB;
  const broken = pts.some((p, i) => i > 0 && p.gap);
  const point = active !== null ? pts[active] : undefined;
  // What the readout says about the observation in hand: its role in the move, or where it sits around it.
  let role = "", roleKind: MarkRole | null = null;
  if (point) {
    const roles = [point.i === model.iB && "Earlier odds", point.i === model.iA && "Move observed", point.i === model.iL && "Latest odds"].filter(Boolean);
    roleKind = point.i === model.iA ? "detected" : point.i === model.iB ? "earlier" : point.i === model.iL ? "latest" : null;
    role = roles.length ? roles.join(" · ")
      : Number.isFinite(model.tA) && point.t > model.tA ? delta(point.price - move.new) + " since the move"
      : Number.isFinite(model.tB) && point.t < model.tB ? "Before the move" : "Recorded observation";
    if (point.gap && point.i > 0) role += " · first capture after a break";
  }
  // The limit stretch in hand, and, for an odds observation in hand, the limit recorded at that same moment.
  const span = lim && activeSpan !== null ? lim.spans[activeSpan] : undefined;
  const spanGlyph: KeyKind = !span || span.kind === "gap" || !span.plot ? "break" : span.change === "rise" ? "rise" : span.change === "fall" ? "fall" : "limit";
  const limitThen = lim && point ? lim.runs.find(r => point.t >= r.t0 && point.t <= r.t1) : undefined;
  const money = (sp: Span) => displayedLimit(sp.amount, sp.currency);
  const runCount = lim ? lim.runs.length : 0;
  const limitGaps = !!lim && lim.spans.some(sp => sp.kind === "gap");
  const spansInView = lim ? lim.spans.filter(spanInView).length : 0;

  const count = pts.length + " recorded " + (pts.length === 1 ? "observation" : "observations")
    + (lim ? " · " + runCount + " recorded " + (runCount === 1 ? "limit" : "limits") : "");
  const describe = `${pts.length} recorded observations from ${utcStamp(model.first, true)} to ${utcStamp(model.last, true)}. `
    + `Earlier odds ${price(move.old)} at ${utcStamp(move.before, true)}. Move observed at ${price(move.new)}, ${utcStamp(move.after, true)}. `
    + `Latest odds ${price(latest.price)} at ${utcStamp(latest.t, true)}. Every value is listed in the recorded odds table.`
    + (lim ? ` Under the odds, a ${LIMIT_NAME.toLowerCase()} strip on the same time axis: ${runCount} recorded ${runCount === 1 ? "limit" : "limits"} from ${utcStamp(lim.first, true)} to ${utcStamp(lim.last, true)}, `
      + `latest ${money(lim.latest)}. Every limit and every gap is listed in the recorded limits table.` : "");

  return <figure className={styles.figure}>
    {/* Tool row at first glance: the window segments and the export. Pan and zoom steps join only once the view is zoomed. */}
    <div className={styles.chartBar}>
      {presets.length > 1 && <div className={styles.ranges} role="group" aria-label="Chart range">
        {presets.map(p => <button key={p.name} type="button" aria-pressed={current === p.name} onClick={() => (p.range ? applyView(p.range[0], p.range[1], p.name) : reset())}>{p.label}</button>)}
      </div>}
      {canZoom && win && <div className={styles.steps} role="group" aria-label="Zoom and pan">
        <button type="button" aria-label="Pan earlier" disabled={!win || view[0] <= full[0] + 1} onClick={() => pan(-1)}><span aria-hidden="true">‹</span></button>
        <button type="button" aria-label="Zoom out" disabled={!win} onClick={() => zoom(2)}><span aria-hidden="true">−</span></button>
        <button type="button" aria-label="Zoom in" disabled={view[1] - view[0] <= minSpan + 1} onClick={() => zoom(0.5)}><span aria-hidden="true">+</span></button>
        <button type="button" aria-label="Pan later" disabled={!win || view[1] >= full[1] - 1} onClick={() => pan(1)}><span aria-hidden="true">›</span></button>
      </div>}
      <button type="button" className={styles.save} disabled={exporting} onClick={() => { setNote(""); setExporting(true); }}><DeskIcon name="download" />Save PNG<span className={styles.vh}> of this chart</span></button>
    </div>

    <div className={styles.plot} ref={boxRef} tabIndex={0} role="group" onKeyDown={onKey}
      aria-label="Odds chart explorer. Left and right arrows step through recorded observations, plus and minus zoom, zero shows the full series.">
      <div className={styles.canvas}>
        <svg ref={svgRef} className={styles.chart} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily={FONT}
          role="img" aria-label={move.player + " decimal odds, earlier " + price(move.old) + ", " + price(move.new) + " when the move was observed"} aria-describedby={uid + "-desc"}
          data-chart="odds" data-y-direction="higher-price-higher" data-point-count={pts.length}
          data-view-from={new Date(view[0]).toISOString()} data-view-to={new Date(view[1]).toISOString()} data-view={current}
          data-earlier-time={move.before} data-earlier-price={move.old} data-detected-time={move.after} data-detected-price={move.new}
          data-latest-time={latest.time} data-latest-price={latest.price}
          data-limit-runs={lim ? runCount : undefined} data-limit-currency={lim ? lim.currency : undefined}
          data-limit-latest={lim ? lim.latest.amount : undefined} data-limit-latest-time={lim ? lim.latest.end : undefined}>
          <desc id={uid + "-desc"}>{describe}</desc>
          <PlotLayer model={model} move={move} lay={lay} g={g} uid={uid} annotate active={active} brush={brush} />
          <LimitLayer model={model} lay={lay} g={g} uid={uid} annotate activeSpan={activeSpan} hoverT={point ? point.t : null} />
          <rect x={g.L} y={g.T} width={g.R - g.L} height={g.B - g.T} fill="transparent" pointerEvents="all"
            style={{ touchAction: "pan-y", cursor: canZoom ? "crosshair" : "default" }}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onLeave} onPointerCancel={onCancel} onDoubleClick={reset} />
        </svg>
        {/* The strip's own hit area and tab stop, laid over the drawing: the picture stays one image, the strip stays reachable. */}
        {lim && g.strip && <div className={styles.strip} tabIndex={0} role="group"
          aria-label={`${LIMIT_NAME} strip, ${lim.currency}. Left and right arrows step through each recorded limit and each gap; plus and minus zoom.`}
          style={{ left: pct(g.L / W), top: pct((g.B + 4) / H), width: pct((g.R - g.L) / W), height: pct((g.strip.B - g.B - 4) / H) }}
          onKeyDown={onStripKey} onPointerDown={onStrip} onPointerMove={onStrip}
          onPointerLeave={e => { if (e.pointerType === "mouse") setActiveSpan(null); }} />}
      </div>
      {win && canZoom && pts.length > 2 && <svg className={styles.nav} viewBox={`0 0 ${W} ${navH}`} width={W} height={navH} aria-hidden="true" focusable="false"
        style={{ touchAction: win ? "none" : "auto", cursor: win ? "ew-resize" : "default" }}
        onPointerDown={onNav} onPointerMove={e => { if (e.buttons & 1) onNav(e); }}>
        <rect x={g.L} y="2" width={g.R - g.L} height={navH - 4} rx="4" fill="none" stroke={C.grid} />
        <path d={navPath} fill="none" stroke={C.mute} strokeWidth="1.2" />
        {Number.isFinite(model.tA) && <path d={`M${r2(navX(model.tA))} 3V${navH - 3}`} stroke={C.mint} strokeWidth="1.5" />}
        <rect x={r2(navX(view[0]))} y="2" width={r2(Math.max(4, navX(view[1]) - navX(view[0])))} height={navH - 4} rx="4"
          fill={C.ink} fillOpacity={win ? 0.1 : 0} stroke={win ? C.text : "none"} strokeWidth="1.5" />
        <text x={g.L - 8} y={navH / 2 + 4} textAnchor="end" fontSize="11" fill={C.mute} fontFamily={FONT}>All</text>
      </svg>}
    </div>

    {/* One line under the plot. At rest it only says what is drawn; with an observation in hand
        (pointer, tap or arrow keys) it reads the actual capture time, the odds and the role.
        With a stretch of the limit strip in hand it reads that stretch instead: its recorded span, the limit, and what changed. */}
    <div className={styles.readout} aria-live="polite" aria-atomic="true" data-key={span ? undefined : roleKind ?? undefined}>
      {span
        ? <>
          <time dateTime={span.start}>{span.t1 - span.t0 < 1000 ? utcStamp(span.t0, true) : utcStamp(span.t0, true) + " → " + utcStamp(span.t1, true)}</time>
          <b>{span.kind === "run" ? money(span) : "—"}</b>
          <span className={styles.role}><KeyGlyph kind={spanGlyph} />{spanNote(span)}</span>
          {span.kind === "run" && span.t1 > span.t0 && <span>recorded over {spanText(span.t1 - span.t0)}</span>}
        </>
        : point
          ? <>
            <time dateTime={point.time}>{utcStamp(point.t, true)}</time>
            <b>{price(point.price)}</b>
            <span className={styles.role}>{roleKind && <KeyGlyph kind={roleKind} />}{role}</span>
            {point.other !== undefined && <span>{move.opponent} {price(point.other)}</span>}
            {lim && <span>{limitThen ? "Limit " + money(limitThen) : "No limit recorded then"}</span>}
          </>
          : <>
            <span>{count}{win ? " · " + lay.visible + " in view, " + utcStamp(view[0]) + " → " + utcStamp(view[1]) : ""} · decimal odds, UTC</span>
            <span className={styles.hint}>{lim ? "Point, tap or use ← → on the line or the limit strip to read it" : "Point, tap or use ← → to read time, odds and role"}</span>
          </>}
    </div>
    {note && <p className={styles.status} role="status">{note}</p>}

    <details className={styles.fold}>
      <summary>How to read this chart</summary>
      <ul className={styles.legend}>
        <li><KeyGlyph kind="earlier" />Earlier odds</li>
        <li><KeyGlyph kind="detected" />Move observed</li>
        {latestDistinct && <li><KeyGlyph kind="latest" />Latest odds</li>}
        {(broken || !!move.chartSummary || pts.length <= 6) && <li><KeyGlyph kind="sample" />Single recorded observation</li>}
        {broken && <li><KeyGlyph kind="break" />Break in capture</li>}
        {lim && <li><KeyGlyph kind="limit" />{LIMIT_NAME}, as recorded</li>}
        {lim && lim.runs.some(r => r.change === "rise") && <li><KeyGlyph kind="rise" />Limit raised</li>}
        {lim && lim.runs.some(r => r.change === "fall") && <li><KeyGlyph kind="fall" />Limit lowered</li>}
        {limitGaps && !broken && <li><KeyGlyph kind="break" />No limit recorded</li>}
      </ul>
      <p className={styles.caption}>
        Decimal odds on a linear axis, times in UTC: higher odds are drawn higher, so shortening odds fall and drifting odds rise. The tinted band spans the two captures that make the move.
        {move.chartSummary ? " This view connects the earlier odds, the move, the later low and high, and the latest odds. Gaps in recording stay open." : " The line connects consecutive scans. Each reading shows the odds at that scan. Gaps in recording stay open."}
        {canZoom ? " Drag across the chart with a mouse to zoom in, double-click to return to the full series; plus, minus and zero do the same from the keyboard." : ""}
      </p>
      {lim && <p className={styles.caption}>
        The strip under the odds is the {LIMIT_NAME.toLowerCase()} recorded for this selection, in {lim.currency}, on the same time axis. It is a separate record from the odds line: a limit can change while the odds stay flat, and every change is drawn.
        {" "}Each level runs only from the first to the last scan that recorded that amount. A thin join links two levels only where the change was seen with no gap between them, with an arrowhead pointing up for a raise and down for a cut.
        {" "}Hatching marks time with no recorded limit{lim.spans.some(sp => sp.why === "before") ? ", including the stretch before limits were tracked" : ""}; nothing is drawn or assumed there, and the latest level stops at its last scan.
        {" "}The strip is scaled from the lowest to the highest recorded limit in view, both written at its left edge, so it has no zero line. The limit is the maximum reported at each check. The amount actually wagered is unknown.
        {lim.assumed ? " Where the source names no currency, USD is assumed." : ""}
        {lim.mixed ? " Limits quoted in another currency are listed in the table and hatched on the strip, not converted." : ""}
        {" "}Tab to the strip and use ← → to step through each limit and gap.
      </p>}
    </details>

    <details className={styles.fold}>
      <summary>Recorded odds ({pts.length})</summary>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead><tr><th scope="col">Time (UTC)</th><th scope="col">{move.player}</th>{!move.chartSummary && <th scope="col">{move.opponent}</th>}<th scope="col">Note</th></tr></thead>
          <tbody>{pts.map(p => {
            const notes = [p.i === model.iB && "Earlier odds", p.i === model.iA && "Move observed", p.i === model.iL && "Latest", p.gap && p.i > 0 && "After a break"].filter(Boolean).join(" · ");
            return <tr key={p.i} data-key={p.i === model.iA ? "detected" : p.i === model.iB ? "earlier" : undefined}>
              <td><time dateTime={p.time}>{utcDate(p.t)} · {utcClock(p.t, true)}</time></td><td>{price(p.price)}</td>{!move.chartSummary && <td>{p.other === undefined ? "—" : price(p.other)}</td>}<td>{notes}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
    </details>

    {/* The strip as a list: every recorded limit and every gap in time order. Zoomed, the rows inside the window are marked. */}
    {lim && <details className={styles.fold}>
      <summary>Recorded limits ({runCount})</summary>
      {win && <p className={styles.fine}>Zoomed to {utcStamp(view[0])} → {utcStamp(view[1])}: {spansInView} of {lim.spans.length} rows fall inside the view and carry a bar at their left edge.</p>}
      <div className={styles.scroll}>
        <table className={styles.table} data-zoomed={win ? "" : undefined}>
          <thead><tr><th scope="col">From (UTC)</th><th scope="col">To (UTC)</th><th scope="col">Limit{lim.assumed ? " (USD assumed where unlabelled)" : ""}</th><th scope="col">Note</th></tr></thead>
          <tbody>{lim.spans.map(sp => <tr key={sp.k} data-kind={sp.kind} data-latest={sp.latest ? "" : undefined} data-view={win ? (spanInView(sp) ? "in" : "out") : undefined}>
            <td>{win && spanInView(sp) && <span className={styles.vh}>In view: </span>}<time dateTime={sp.start}>{utcDate(sp.t0)} · {utcClock(sp.t0, true)}</time></td>
            <td><time dateTime={sp.end}>{utcDate(sp.t1)} · {utcClock(sp.t1, true)}</time></td>
            <td>{sp.kind === "run" ? money(sp) : "—"}</td>
            <td>{spanNote(sp)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>}

    {exporting && <div hidden aria-hidden="true">
      <ExportCard svgRef={exportRef} model={model} move={move} view={view} archive={archive} uid={uid + "-x"} />
    </div>}
  </figure>;
}
