"use client";

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode, Ref } from "react";
import styles from "./board.module.css";
import { DeskIcon } from "./DeskIcon";
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
const MIN = 60000;
const HOUR = 60 * MIN;
const X_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 180, 360, 720, 1440, 2880, 10080].map(v => v * MIN);

type Pt = { i: number; t: number; time: string; price: number; other: number; gap: boolean };
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
  // Room above and below the extremes for the labelled price tags.
  const padY = 30 * g.s;
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
 * The pair that makes the move shares one colour: a hollow ring for the earlier
 * price, a solid dot inside a soft ring for the price at detection. The latest
 * observation is a plain ringed dot, so it never competes with the pair.
 */
function mark(role: MarkRole, cx: number, cy: number, s: number): ReactNode {
  if (role === "earlier") return <circle cx={cx} cy={cy} r={6 * s} fill={C.bg} stroke={C.mint} strokeWidth={2.5 * s} />;
  if (role === "detected") return <>
    <circle cx={cx} cy={cy} r={11 * s} fill="none" stroke={C.mint} strokeOpacity={0.45} strokeWidth={1.5 * s} />
    <circle cx={cx} cy={cy} r={6.5 * s} fill={C.mint} stroke={C.bg} strokeWidth={2 * s} />
  </>;
  return <>
    <circle cx={cx} cy={cy} r={7.5 * s} fill={C.bg} stroke={C.ink} strokeOpacity={0.7} strokeWidth={1.2 * s} />
    <circle cx={cx} cy={cy} r={3.6 * s} fill={C.ink} />
  </>;
}

function keyMark(kind: KeyKind, cx: number, cy: number, s: number): ReactNode {
  if (kind === "sample") return <circle cx={cx} cy={cy} r={3.2 * s} fill={C.ink} />;
  if (kind === "break") return <>
    <rect x={cx - 9 * s} y={cy - 7 * s} width={18 * s} height={14 * s} fill="none" stroke={C.hatch} strokeWidth={s} />
    <path d={`M${cx - 8 * s} ${cy + 2 * s}l${8 * s} ${-8 * s}M${cx - 4 * s} ${cy + 6 * s}l${12 * s} ${-12 * s}M${cx + 2 * s} ${cy + 6 * s}l${6 * s} ${-6 * s}`}
      fill="none" stroke={C.mute} strokeWidth={1.4 * s} />
  </>;
  return mark(kind, cx, cy, s);
}

/** Legend swatch that reuses the exact marks drawn on the chart. */
export function KeyGlyph({ kind }: { kind: KeyKind }) {
  return <svg className={styles.glyph} width="22" height="22" viewBox="-13 -13 26 26" aria-hidden="true" focusable="false">
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
  const dense = lay.visible > (R - L) / 7;
  const rDot = (dense ? 2.2 : 3.2) * s;
  const segments = 1 + pts.filter((p, i) => i > 0 && p.gap).length;

  // The move itself: a shaded band from the earlier price to the price at detection,
  // bracketed above the plot with the two times and the gap between them.
  const hasA = Number.isFinite(tA), hasB = Number.isFinite(tB);
  const pair = hasA && hasB && tA > tB;
  const xA = hasA ? x(tA) : NaN, xB = hasB ? x(tB) : NaN;
  const seenA = hasA && inView(tA), seenB = pair && inView(tB);
  const bandOn = pair && tA >= lay.t0 && tB <= lay.t1;
  const yb = T - 8 * s;
  const clock = (t: number) => (model.multiDay ? utcDate(t) + " " : "") + utcClock(t);
  let note: { text: string; at: number; anchor: "start" | "middle" | "end" } | null = null;
  if (hasA) {
    const base = pair
      ? (small ? "earlier → detected · " + spanText(tA - tB) : "earlier " + clock(tB) + " – detected " + clock(tA) + " UTC · " + spanText(tA - tB) + " apart")
      : "detected " + clock(tA) + " UTC";
    if (tA < lay.t0) note = { text: "← " + base, at: L, anchor: "start" };
    else if ((pair ? tB : tA) > lay.t1) note = { text: base + " →", at: R, anchor: "end" };
    else {
      const mid = pair ? (clampX(xB) + clampX(xA)) / 2 : clampX(xA);
      const half = base.length * 3.3 * s;
      note = mid + half > R ? { text: base, at: R, anchor: "end" } : mid - half < L ? { text: base, at: L, anchor: "start" } : { text: base, at: mid, anchor: "middle" };
    }
  }

  // Labelled price tags beside the key marks: small caps caption, then the price, haloed off the line.
  const tag = (id: string, cap: string, val: string, k: { x: number; y: number }, above: boolean, fill: string) => {
    const w = (cap.length * 7.6 + val.length * 10.5 + 8) * s;
    const anchor = k.x + w / 2 > R ? "end" : k.x - w / 2 < L ? "start" : "middle";
    const tx = anchor === "end" ? Math.min(R, k.x + 9 * s) : anchor === "start" ? Math.max(L, k.x - 9 * s) : k.x;
    let ty = above ? k.y - 15 * s : k.y + 27 * s;
    if (above && ty < T + 14 * s) ty = k.y + 27 * s;
    else if (!above && ty > B - 3 * s) ty = k.y - 15 * s;
    return <text key={id} x={r2(tx)} y={r2(ty)} textAnchor={anchor} fontSize={17 * s} fontWeight={700} fill={fill}
      stroke={C.bg} strokeWidth={4 * s} strokeLinejoin="round" paintOrder="stroke">
      <tspan fontSize={11 * s} fontWeight={600} letterSpacing={0.6 * s}>{cap}</tspan><tspan dx={5 * s}>{val}</tspan>
    </text>;
  };
  const showB = !!kB && inView(kB.t), showA = !!kA && inView(kA.t), showL = !!kL && inView(kL.t);
  const up = move.old >= move.new;
  let latestTag: ReactNode = null;
  if (kL && showL) {
    const reach = (small ? 100 : 150) * s;
    const dy = kA && showA && Math.abs(kL.x - kA.x) < reach ? kL.y - kA.y : NaN;
    const above = !(dy > 24 * s && dy < 62 * s);
    const hitsB = !!(above && kB && showB && Math.abs(kL.x - kB.x) < reach && Math.abs(kL.y - kB.y) < 20 * s);
    if (!hitsB) latestTag = tag("l", "LATEST", price(pts[iL].price), kL, above, C.ink);
  }

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

    <text x={r2(Math.max(2 * s, L - 52 * s))} y={r2(T - 38 * s)} fontSize={10.5 * s} fontWeight={600} letterSpacing={0.8 * s} fill={C.mute}>
      {"DECIMAL ODDS" + (small ? "" : " · " + clipText(move.player, 32).toUpperCase())}
    </text>

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
      <path d={`M${r2(xS)} ${T}V${B + 5 * s}`} stroke={C.text} strokeWidth={1.3 * s} />
      <text x={r2(startAt)} y={B + 19 * s} textAnchor={startAnchor} fontSize={fs} fill={C.ink}>{small ? "Start" : "Scheduled start"}</text>
      <text x={r2(startAt)} y={B + 33 * s} textAnchor={startAnchor} fontSize={fs * 0.92} fill={C.mute}>{utcClock(tS) + " UTC"}</text>
    </g>}

    <g clipPath={`url(#${clipId})`}>
      {pts.map((p, i) => i > 0 && p.gap
        ? <rect key={"gap" + p.i} x={r2(x(pts[i - 1].t))} y={T} width={r2(Math.max(0, x(p.t) - x(pts[i - 1].t)))} height={B - T} fill={`url(#${hatchId})`}
          {...(annotate ? { "data-role": "capture-break", "data-from": pts[i - 1].time, "data-to": p.time } : {})} />
        : null)}
      {bandOn && <rect x={r2(clampX(xB))} y={T} width={r2(Math.max(0, clampX(xA) - clampX(xB)))} height={B - T} fill={C.mint} fillOpacity={0.13}
        {...(annotate ? { "data-role": "move-interval", "data-from": move.before, "data-to": move.after } : {})} />}
      {seenB && <path d={`M${r2(xB)} ${T}V${B}`} stroke={C.mint} strokeOpacity={0.75} strokeWidth={s} strokeDasharray={`${3 * s} ${4 * s}`} />}
      {hasA && <path d={`M${r2(xA)} ${T}V${B}`} stroke={C.mint} strokeOpacity={0.9} strokeWidth={1.2 * s}
        {...(annotate ? { "data-role": "detection-line", "data-time": move.after } : {})} />}
      {kA && <path d={`M${r2(kA.x)} ${r2(kA.y)}H${R}`} stroke={C.mint} strokeOpacity={0.5} strokeWidth={s} strokeDasharray={`${2 * s} ${5 * s}`} />}
      <path d={seg(0, pts.length - 1)} fill="none" stroke={C.ink} strokeOpacity={0.6} strokeWidth={1.6 * s} strokeLinejoin="round" strokeLinecap="round"
        {...(annotate ? { "data-role": "series", "data-segments": segments, "data-interpolation": "straight-between-consecutive-captures" } : {})} />
      {iB >= 0 && iA > iB && <path d={seg(iB, iA)} fill="none" stroke={C.mint} strokeWidth={3 * s} strokeLinejoin="round" strokeLinecap="round"
        {...(annotate ? { "data-role": "move" } : {})} />}
      {pts.map(p => {
        const roles = [p.i === iB && "earlier", p.i === iA && "detected", p.i === iL && "latest"].filter(Boolean).join(" ") || "sample";
        const after = hasA && p.t > tA;
        const data = annotate ? {
          "data-index": p.i, "data-time": p.time, "data-price": p.price, "data-other": p.other, "data-role": roles,
          "data-phase": after ? "after-detection" : "to-detection", "data-gap": p.gap ? "true" : undefined, "data-in-view": String(inView(p.t)),
        } : {};
        return <circle key={p.i} cx={r2(x(p.t))} cy={r2(y(p.price))} r={rDot} fill={C.ink} stroke={C.bg} strokeWidth={1.2 * s} {...data}>
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

    {kB && showB && tag("b", small ? "EARLIER" : "EARLIER PRICE", price(move.old), kB, up, C.ink)}
    {kA && showA && tag("a", small ? "DETECTED" : "PRICE AT DETECTION", price(move.new), kA, !up, C.mint)}
    {latestTag}

    {bandOn && <path fill="none" stroke={C.mint} strokeWidth={1.5 * s}
      d={`M${r2(clampX(xB))} ${r2(yb)}H${r2(clampX(xA))}`
        + (seenB ? `M${r2(xB)} ${r2(yb - 4 * s)}v${8 * s}` : "")
        + (seenA ? `M${r2(xA)} ${r2(yb - 4 * s)}v${8 * s}` : "")} />}
    {note && <text x={r2(note.at)} y={r2(yb - 9 * s)} textAnchor={note.anchor} fontSize={11.5 * s} fill={C.mint}>{note.text}</text>}

    {hover && <g pointerEvents="none">
      <path d={`M${r2(x(hover.t))} ${T}V${B}`} stroke={C.ink} strokeOpacity={0.35} strokeWidth={s} />
      <circle cx={r2(x(hover.t))} cy={r2(y(hover.price))} r={14 * s} fill="none" stroke={C.ink} strokeWidth={1.5 * s} strokeDasharray={`${3 * s} ${3 * s}`} />
    </g>}
    {brush && <rect x={r2(Math.min(brush.a, brush.b))} y={T} width={r2(Math.abs(brush.b - brush.a))} height={B - T} fill={C.ink} fillOpacity={0.1} stroke={C.text} strokeWidth={s} pointerEvents="none" />}
  </g>;
}

/**
 * The fixed 1200 × 675 share card, rendered only while a download is in progress.
 * One flat panel under a 6 px mode stripe: brand line, the player, the move in
 * large figures, the chart, its key, then the facts and the result.
 */
function ExportCard({ svgRef, model, move, view, archive, uid }: {
  svgRef: Ref<SVGSVGElement>; model: Model; move: DeskMove; view: [number, number]; archive: boolean; uid: string;
}) {
  const W = 1200, H = 675;
  const g: Geo = { L: 120, R: 1150, T: 224, B: 472, s: 1.4 };
  const lay = layout(model, view, g);
  const latest = model.iL >= 0 ? model.pts[model.iL] : null;
  const latestDistinct = model.iL >= 0 && model.iL !== model.iA && model.iL !== model.iB;
  const outcome = outcomeOf(move.result), pl = paper(move);
  const tone = outcome === "won" ? C.mint : outcome === "lost" ? C.loss : C.text;
  const nameSize = move.player.length > 30 ? 32 : move.player.length > 24 ? 38 : 44;
  const between = model.tA - model.tB, lead = Date.parse(move.start) - model.tA;
  const facts = ["Detected " + utcStamp(move.after, true)];
  if (Number.isFinite(lead) && lead >= 0) facts.push(spanText(lead) + " before scheduled start");
  if (Number.isFinite(between) && between > 0) facts.push("captures " + spanText(between) + " apart");
  const replayNote = archive && pl !== null ? "Historical replay: 1u at the price at detection" : "";
  const side = [replayNote, move.score ? clipText(move.score, 40) : ""].filter(Boolean).join(" · ");

  const keys: { kind: KeyKind; label: string; at: number }[] = [];
  const labels: [KeyKind, string][] = [["earlier", "Earlier price"], ["detected", "Price at detection"]];
  if (latestDistinct) labels.push(["latest", "Latest observation"]);
  labels.push(["sample", "Recorded observation"]);
  if (model.pts.some((p, i) => i > 0 && p.gap)) labels.push(["break", "Break in capture"]);
  let at = 60;
  for (const [kind, label] of labels) { keys.push({ kind, label, at }); at += 46 + label.length * 8.6; }

  return <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" width={W} height={H} viewBox={`0 0 ${W} ${H}`} fontFamily={FONT}>
    <rect width={W} height={H} fill={C.bg} />
    <rect width={W} height="6" fill={archive ? C.amber : C.mint} />
    <text x="48" y="48" fontSize="16" fontWeight="700" letterSpacing="2" fill={C.mint}>
      IL MARGINE<tspan fill={C.mute} fontWeight="400">{" · DROP SHOT DESK · " + (archive ? "HISTORICAL REPLAY" : "DAILY MOVES")}</tspan>
    </text>
    <text x={W - 48} y="48" textAnchor="end" fontSize="15" letterSpacing="1" fill={C.mute}>{clipText(move.tour + " · " + move.league, 46).toUpperCase()}</text>
    <text x="48" y="104" fontSize={nameSize} fontWeight="700" letterSpacing={r2(-nameSize * 0.03)} fill={C.ink}>{clipText(move.player, 34)}</text>
    <text x="48" y="136" fontSize="21" fill={C.text}>{clipText(move.fixtureLabel ?? ("vs " + move.opponent), 40)}</text>
    <text x={W - 48} y="106" textAnchor="end" fontSize="62" fontWeight="700" fill={C.mint}>
      <tspan fill={C.mute} fontWeight="400">{price(move.old) + " → "}</tspan>{price(move.new)}
    </text>
    <text x={W - 48} y="138" textAnchor="end" fontSize="18" fill={C.ink}>
      {`Decimal odds · earlier ${utcClock(move.before)} → detected ${utcClock(move.after)} UTC · ${utcDate(move.after)}`}
    </text>
    <PlotLayer model={model} move={move} lay={lay} g={g} uid={uid} annotate={false} />
    {keys.map(k => <g key={k.kind}>
      {keyMark(k.kind, k.at, 551, 1.1)}
      <text x={k.at + 20} y="556" fontSize="15" fill={C.text}>{k.label}</text>
    </g>)}
    <rect x="48" y="570" width={W - 96} height="1" fill={C.grid} />
    <text x="48" y="600" fontSize="18" fill={C.ink}>{facts.join(" · ")}</text>
    {outcome !== "pending" && <text x={W - 48} y="602" textAnchor="end" fontSize="27" fontWeight="700" letterSpacing="1" fill={tone}>
      {clipText(outcomeLabel(move), 12).toUpperCase() + (archive && pl !== null ? " " + units(pl) : "")}
    </text>}
    <text x="48" y="626" fontSize="14" fill={C.text}>
      {latest ? `Latest observation ${price(latest.price)} at ${utcStamp(latest.t, true)} · scheduled start ${utcStamp(move.start)}` : `Scheduled start ${utcStamp(move.start)}`}
    </text>
    {side && <text x={W - 48} y="626" textAnchor="end" fontSize="14" fill={C.text}>{side}</text>}
    <text x="48" y="650" fontSize="14" fill={C.mute}>Decimal odds as recorded at each observation (UTC). Lines join consecutive captures only; breaks are left open.</text>
  </svg>;
}

async function savePng(svg: SVGSVGElement, w: number, h: number, name: string) {
  const xml = new XMLSerializer().serializeToString(svg);
  const url = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    await new Promise<void>((done, fail) => {
      image.onload = () => done();
      image.onerror = () => fail(new Error("image"));
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas");
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
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

  // Phones get the taller plot of the original (290–360 px); wide stages keep roughly 2:1.
  const H = Math.round(W < 480 ? Math.min(360, Math.max(300, W * 0.9)) : Math.min(480, Math.max(300, W * 0.52)));
  // 52 px of head room holds the axis caption and the earlier → detected bracket.
  const g: Geo = { L: W < 480 ? 44 : 50, R: W - 10, T: 52, B: H - 42, s: 1 };
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
      if (range[1] - range[0] < fullSpan - 1) presets.push({ name: "after", label: "Since detection", range });
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
      const d = Math.abs(lay.x(p.t) - px);
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
  let pointNote = "";
  if (point) {
    const roles = [point.i === model.iB && "Earlier price", point.i === model.iA && "Price at detection", point.i === model.iL && "Latest observation"].filter(Boolean);
    pointNote = roles.length ? roles.join(" · ")
      : Number.isFinite(model.tA) && point.t > model.tA ? delta(point.price - move.new) + " vs price at detection"
      : "Before the move";
  }
  const describe = `${pts.length} recorded observations from ${utcStamp(model.first, true)} to ${utcStamp(model.last, true)}. `
    + `Earlier price ${price(move.old)} at ${utcStamp(move.before, true)}. Price at detection ${price(move.new)} at ${utcStamp(move.after, true)}. `
    + `Latest observation ${price(latest.price)} at ${utcStamp(latest.t, true)}. Every value is listed in the recorded prices table.`;

  return <figure className={styles.figure}>
    {/* Original tool row: window segments, the captures-in-view label, then the export on the far right. */}
    <div className={styles.chartBar}>
      {presets.length > 1 && <div className={styles.ranges} role="group" aria-label="Chart range">
        {presets.map(p => <button key={p.name} type="button" aria-pressed={current === p.name} onClick={() => (p.range ? applyView(p.range[0], p.range[1], p.name) : reset())}>{p.label}</button>)}
      </div>}
      {canZoom && <div className={styles.steps} role="group" aria-label="Zoom and pan">
        <button type="button" aria-label="Pan earlier" disabled={!win || view[0] <= full[0] + 1} onClick={() => pan(-1)}><span aria-hidden="true">‹</span></button>
        <button type="button" aria-label="Zoom out" disabled={!win} onClick={() => zoom(2)}><span aria-hidden="true">−</span></button>
        <button type="button" aria-label="Zoom in" disabled={view[1] - view[0] <= minSpan + 1} onClick={() => zoom(0.5)}><span aria-hidden="true">+</span></button>
        <button type="button" aria-label="Pan later" disabled={!win || view[1] >= full[1] - 1} onClick={() => pan(1)}><span aria-hidden="true">›</span></button>
      </div>}
      <p className={styles.chartTitle}><strong>Price chart</strong><span>{lay.visible} of {pts.length} recorded {pts.length === 1 ? "observation" : "observations"} in view</span></p>
      <button type="button" className={styles.save} disabled={exporting} onClick={() => { setNote(""); setExporting(true); }}><DeskIcon name="download" />Save chart PNG</button>
    </div>

    <div className={styles.plot} ref={boxRef} tabIndex={0} role="group" onKeyDown={onKey}
      aria-label="Odds chart explorer. Left and right arrows step through recorded observations, plus and minus zoom, zero shows the full series.">
      <svg ref={svgRef} className={styles.chart} xmlns="http://www.w3.org/2000/svg" viewBox={`0 0 ${W} ${H}`} width={W} height={H} fontFamily={FONT}
        role="img" aria-label={move.player + " decimal odds, earlier " + price(move.old) + ", at detection " + price(move.new)} aria-describedby={uid + "-desc"}
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
      {canZoom && pts.length > 2 && <svg className={styles.nav} viewBox={`0 0 ${W} ${navH}`} width={W} height={navH} aria-hidden="true" focusable="false"
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

    {/* As in the original: one plain line under the plot, the selected player's price in the accent. */}
    <div className={styles.readout} aria-live="polite" aria-atomic="true">
      {point
        ? <><strong>{utcStamp(point.t, true)}</strong><span>{move.player} <b>{price(point.price)}</b></span><span>{move.opponent} <b>{price(point.other)}</b></span><span>{pointNote}</span></>
        : <><strong>{win ? "Zoomed view" : "Full series"}</strong><span>{utcStamp(view[0])} → {utcStamp(view[1])}</span><span>Hover or tap a dot to read its exact recorded price</span></>}
    </div>

    <ul className={styles.legend}>
      <li><KeyGlyph kind="earlier" />Earlier price</li>
      <li><KeyGlyph kind="detected" />Price at detection</li>
      {latestDistinct && <li><KeyGlyph kind="latest" />Latest observation</li>}
      <li><KeyGlyph kind="sample" />Recorded observation</li>
      {broken && <li><KeyGlyph kind="break" />Break in capture</li>}
    </ul>
    <figcaption className={styles.caption}>
      Decimal odds on a linear axis: a higher price is drawn higher, so a shorter price falls. The shaded band runs from the earlier price to the price at detection.
      Every dot is one recorded observation, timed in UTC. Lines join consecutive captures only and breaks are left open; prices between dots were not observed.
      {canZoom ? " Drag across the chart with a mouse to zoom in, double-click to return to the full series." : ""}
    </figcaption>
    {note && <p className={styles.status} role="status">{note}</p>}

    <details className={styles.fold}>
      <summary>Recorded prices ({pts.length})</summary>
      <div className={styles.scroll}>
        <table className={styles.table}>
          <thead><tr><th scope="col">Time (UTC)</th><th scope="col">{move.player}</th><th scope="col">{move.opponent}</th><th scope="col">Note</th></tr></thead>
          <tbody>{pts.map(p => {
            const notes = [p.i === model.iB && "Earlier price", p.i === model.iA && "Detected", p.i === model.iL && "Latest", p.gap && p.i > 0 && "After a break"].filter(Boolean).join(" · ");
            return <tr key={p.i} data-key={p.i === model.iA ? "detected" : p.i === model.iB ? "earlier" : undefined}>
              <td><time dateTime={p.time}>{utcDate(p.t)} · {utcClock(p.t, true)}</time></td><td>{price(p.price)}</td><td>{price(p.other)}</td><td>{notes}</td>
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
