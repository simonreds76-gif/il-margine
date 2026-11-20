"use client";

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode, Ref } from "react";
import styles from "./board.module.css";
import { DeskIcon, marketIcon } from "./DeskIcon";
import { marketName } from "./DeskParts";
import { delta, outcomeLabel, outcomeOf, paper, price, slug, units, utcClock, utcDate, utcStamp } from "./desk";
import type { DeskMove } from "./desk";

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

type Pt = { i: number; t: number; time: string; price: number; other?: number; gap: boolean };
type Model = {
  pts: Pt[]; first: number; last: number; full: [number, number];
  tB: number; tA: number; tS: number; toStart: boolean; iB: number; iA: number; iL: number; multiDay: boolean;
};
type Geo = { L: number; R: number; T: number; B: number; s: number };
type MarkRole = "earlier" | "detected" | "latest";
type KeyKind = MarkRole | "sample" | "break";

const r2 = (n: number) => Math.round(n * 100) / 100;
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
  if (!pts.length) { first = Number.isFinite(tB) ? tB : 0; last = Number.isFinite(tA) ? tA : first; }
  // As in the original templates the axis ends on the scheduled start, but only when the
  // empty tail that adds is at most half the recorded span, so the move is never squeezed.
  const toStart = pts.length > 1 && Number.isFinite(tS) && tS > last && tS - last <= 0.5 * (last - first);
  const full: [number, number] = toStart ? [first, tS] : last > first ? [first, last] : [first - 30 * MIN, first + 30 * MIN];
  return { pts, first, last, full, tB, tA, tS, toStart, iB: find(tB), iA: find(tA), iL: pts.length - 1, multiDay: utcDate(full[0]) !== utcDate(full[1]) };
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

function keyMark(kind: KeyKind, cx: number, cy: number, s: number): ReactNode {
  if (kind === "sample") return <circle cx={cx} cy={cy} r={2.6 * s} fill={C.text} />;
  if (kind === "break") return <>
    <rect x={cx - 9 * s} y={cy - 7 * s} width={18 * s} height={14 * s} fill="none" stroke={C.hatch} strokeWidth={s} />
    <path d={`M${cx - 8 * s} ${cy + 2 * s}l${8 * s} ${-8 * s}M${cx - 4 * s} ${cy + 6 * s}l${12 * s} ${-12 * s}M${cx + 2 * s} ${cy + 6 * s}l${6 * s} ${-6 * s}`}
      fill="none" stroke={C.mute} strokeWidth={1.4 * s} />
  </>;
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
          <path d={`M${px} ${T}V${B + 5 * s}`} stroke={C.grid} strokeWidth={s} strokeDasharray={`${s} ${4 * s}`} />
          {!nearStart(px) && <text x={px} y={B + 19 * s} textAnchor="middle" fill={C.ink}>{dayStep ? utcDate(t) : utcClock(t)}</text>}
          {withDate && !nearStart(px) && <text x={px} y={B + 33 * s} textAnchor="middle" fill={C.mute} fontSize={fs * 0.92}>{utcDate(t)}</text>}
        </g>;
      })}
      {edgeOnly && <>
        <text x={L + 12 * s} y={B + 19 * s} fill={C.ink}>{utcClock(lay.t0, true)}</text>
        <text x={L + 12 * s} y={B + 33 * s} fill={C.mute} fontSize={fs * 0.92}>{utcDate(lay.t0)}</text>
        {!nearStart(R - 12 * s) && <text x={R - 12 * s} y={B + 19 * s} textAnchor="end" fill={C.ink}>{utcClock(lay.t1, true)}</text>}
      </>}
      <text x={L - 8 * s} y={B + 19 * s} textAnchor="end" fill={C.mute} fontSize={fs * 0.92}>UTC</text>
    </g>

    {startOn && <g {...(annotate ? { "data-role": "scheduled-start", "data-time": move.start } : {})}>
      <path d={`M${r2(xS)} ${T}V${B + 5 * s}`} stroke={C.mute} strokeWidth={s} />
      <text x={r2(startAt)} y={B + 19 * s} textAnchor={startAnchor} fontSize={fs} fill={C.ink}>{small ? "Start" : "Scheduled start"}</text>
      <text x={r2(startAt)} y={B + 33 * s} textAnchor={startAnchor} fontSize={fs * 0.92} fill={C.mute}>{utcClock(tS) + " UTC"}</text>
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
 * The fixed 1200 × 675 share card, rendered only while a download is in progress.
 * It stands alone on one grid: a three-row head (caption, figure, detail) with the
 * selection on the left and one pair of odds, each over its own capture time, on the
 * right; the plotted line across the full measure; one footer line. The pair carries
 * the same two marks as the line, so the card needs no key and repeats no figure.
 */
function ExportCard({ svgRef, model, move, view, archive, uid }: {
  svgRef: Ref<SVGSVGElement>; model: Model; move: DeskMove; view: [number, number]; archive: boolean; uid: string;
}) {
  const W = 1200, H = 675, M = SHARE_MARGIN;
  const g: Geo = { L: 112, R: W - M, T: 240, B: 528, s: 1.4 };
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
  const method = move.chartSummary
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
  const { pts, full } = model;
  const boxRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const exportRef = useRef<SVGSVGElement>(null);
  const drag = useRef<number | null>(null);
  const [W, setW] = useState(720);
  const [win, setWin] = useState<{ from: number; to: number; name: string } | null>(null);
  const [active, setActive] = useState<number | null>(null);
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
  const H = Math.round(W < 480 ? Math.min(330, Math.max(270, W * 0.82)) : Math.min(440, Math.max(280, W * 0.46)));
  const g: Geo = { L: W < 480 ? 44 : 50, R: W - 10, T: 12, B: H - 42, s: 1 };
  const view: [number, number] = win ? [win.from, win.to] : full;
  const lay = layout(model, view, g);

  const fullSpan = full[1] - full[0];
  const minSpan = Math.min(fullSpan, 2 * MIN);
  const canZoom = pts.length >= 2 && model.last > model.first;
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
    const c = p && p.t >= a && p.t <= b ? p.t : (a + b) / 2;
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
    setActive(nearest(px));
  };
  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const px = svgX(e.clientX, svgRef.current);
    if (drag.current !== null) setBrush({ a: drag.current, b: Math.max(g.L, Math.min(g.R, px)) });
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
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
    if (next !== null) {
      setActive(next);
      const t = pts[next].t;
      if (t < view[0] || t > view[1]) { const span = view[1] - view[0]; applyView(t - span / 2, t + span / 2, "custom"); }
    }
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
  const count = pts.length + " recorded " + (pts.length === 1 ? "observation" : "observations");
  const describe = `${pts.length} recorded observations from ${utcStamp(model.first, true)} to ${utcStamp(model.last, true)}. `
    + `Earlier odds ${price(move.old)} at ${utcStamp(move.before, true)}. Move observed at ${price(move.new)}, ${utcStamp(move.after, true)}. `
    + `Latest odds ${price(latest.price)} at ${utcStamp(latest.t, true)}. Every value is listed in the recorded odds table.`;

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
      <svg ref={svgRef} className={styles.chart} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily={FONT}
        role="img" aria-label={move.player + " decimal odds, earlier " + price(move.old) + ", " + price(move.new) + " when the move was observed"} aria-describedby={uid + "-desc"}
        data-chart="odds" data-y-direction="higher-price-higher" data-point-count={pts.length}
        data-view-from={new Date(view[0]).toISOString()} data-view-to={new Date(view[1]).toISOString()} data-view={current}
        data-earlier-time={move.before} data-earlier-price={move.old} data-detected-time={move.after} data-detected-price={move.new}
        data-latest-time={latest.time} data-latest-price={latest.price}>
        <desc id={uid + "-desc"}>{describe}</desc>
        <PlotLayer model={model} move={move} lay={lay} g={g} uid={uid} annotate active={active} brush={brush} />
        <rect x={g.L} y={g.T} width={g.R - g.L} height={g.B - g.T} fill="transparent" pointerEvents="all"
          style={{ touchAction: "pan-y", cursor: canZoom ? "crosshair" : "default" }}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onLeave} onPointerCancel={onCancel} onDoubleClick={reset} />
      </svg>
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
        (pointer, tap or arrow keys) it reads the actual capture time, the odds and the role. */}
    <div className={styles.readout} aria-live="polite" aria-atomic="true" data-key={roleKind ?? undefined}>
      {point
        ? <>
          <time dateTime={point.time}>{utcStamp(point.t, true)}</time>
          <b>{price(point.price)}</b>
          <span className={styles.role}>{roleKind && <KeyGlyph kind={roleKind} />}{role}</span>
          {point.other !== undefined && <span>{move.opponent} {price(point.other)}</span>}
        </>
        : <>
          <span>{count}{win ? " · " + lay.visible + " in view, " + utcStamp(view[0]) + " → " + utcStamp(view[1]) : ""} · decimal odds, UTC</span>
          <span className={styles.hint}>Point, tap or use ← → to read time, odds and role</span>
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
      </ul>
      <p className={styles.caption}>
        Decimal odds on a linear axis, times in UTC: higher odds are drawn higher, so shortening odds fall and drifting odds rise. The tinted band spans the two captures that make the move.
        {move.chartSummary ? " This view connects the earlier odds, the move, the later low and high, and the latest odds. Gaps in recording stay open." : " The line connects consecutive scans. Each reading shows the odds at that scan. Gaps in recording stay open."}
        {canZoom ? " Drag across the chart with a mouse to zoom in, double-click to return to the full series; plus, minus and zero do the same from the keyboard." : ""}
      </p>
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

    {exporting && <div hidden aria-hidden="true">
      <ExportCard svgRef={exportRef} model={model} move={move} view={view} archive={archive} uid={uid + "-x"} />
    </div>}
  </figure>;
}
