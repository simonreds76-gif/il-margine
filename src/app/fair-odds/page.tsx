"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { formatStake } from "@/lib/format";

/* Types */

interface FairOddsMatch {
  id: number;
  tournament: string;
  match_date?: string;
  kickoff_iso?: string;
  surface: string;
  league?: "ATP" | "Challenger";
  player1_id: number;
  player2_id: number;
  player1_name: string;
  player2_name: string;
  p1_win_prob: number;
  p2_win_prob: number;
  odds1: number;
  odds2: number;
  p1_serve?: number;
  p1_return?: number;
  p1_total?: number;
  p2_serve?: number;
  p2_return?: number;
  p2_total?: number;
  expected_total_games?: number;
  ou_line_1?: number;
  ou_over_1?: number;
  ou_under_1?: number;
  ou_line_2?: number;
  ou_over_2?: number;
  ou_under_2?: number;
  ou_line_3?: number;
  ou_over_3?: number;
  ou_under_3?: number;
  pinnacle_odds1?: number;
  pinnacle_odds2?: number;
  pinnacle_margin?: number;
  pinnacle_ou_line?: number;
  pinnacle_ou_over?: number;
  pinnacle_ou_under?: number;
  spread_line?: number;
  spread_odds1?: number;
  spread_odds2?: number;
  handicap_edge_p1?: number;
  handicap_edge_p2?: number;
  p_a?: number;
  p_b?: number;
  handicap_point_prob_source?: "stored_p_a_p_b" | "fallback_divergent_gap" | "fallback_missing";
  handicap_reverse_solve?: boolean;
  handicap_point_prob_gap?: number;
  value_p1?: number;
  value_p2?: number;
  confidence?: string;
  series_bucket?: string;
  policy_match?: boolean;
  shadow_match?: boolean;
  blocked_reason?: string;
  tournament_speed_signal?: number;
  fast_clay_flag?: boolean;
  fast_clay_selected_side?: "P1" | "P2";
  fast_clay_archetype?: "both" | "serve_led" | "return_led" | "contrarian";
  fast_clay_return_led_flag?: boolean;
  row_signals?: SignalSummary[];
}

interface SignalSummary {
  id: number;
  kind?: "clay_guarded" | "clay_2026" | "spread_v1" | "volume_200" | "volume_200_upgrade" | "volume_275";
  player1_id?: number;
  player2_id?: number;
  player1_name: string;
  player2_name: string;
  side: string;
  value_pct: number;
  pinnacle_odds?: number;
  stake_units?: number;
  stake_gbp?: number;
  bet_type: string;
  spread_line?: number;
  tournament: string;
  surface: string;
  league?: "ATP" | "Challenger";
  shadow_reason?: string;
  tournament_speed_signal?: number;
  clay_speed_tier?: "fast" | "normal";
  raw_value_p1?: number;
  raw_value_p2?: number;
  clay_2026_raw_value_same_side?: number;
  clay_2026_value_p1?: number;
  clay_2026_value_p2?: number;
  clay_2026_raw_odds1?: number;
  clay_2026_raw_odds2?: number;
  clay_2026_calibrated_odds1?: number;
  clay_2026_calibrated_odds2?: number;
  clay_2026_selected_prob?: number;
  clay_guarded_selected_elo_prob?: number;
  clay_guarded_selected_market_prob?: number;
  clay_guarded_selected_elo_gap_vs_market?: number;
  handicap_point_prob_source?: "stored_p_a_p_b" | "fallback_divergent_gap" | "fallback_missing";
}

interface StrictPolicyMeta {
  mode: "strict" | "off";
  production_mode?: "base" | "overlay";
  min_value_pct: number;
  allowed_segments: string[];
  allowed_confidence: string[];
  eligible_matches: number;
  signaled_matches: number;
  overlay?: {
    considered_matches: number;
    passed_matches: number;
    skipped_missing: number;
    skipped_min_n: number;
    skipped_min_roi: number;
  };
}

interface PinnacleOnlyMatch {
  tournament?: string;
  player1_name: string;
  player2_name: string;
  odds1: number;
  odds2: number;
  ou_line?: number;
  ou_over?: number;
  ou_under?: number;
  match_date?: string;
  kickoff_iso?: string;
}

interface ApiResponse {
  matches: FairOddsMatch[];
  matches_with_row_signals?: number;
  pinnacle_count: number;
  pinnacle_matched_count: number;
  pinnacle_only?: PinnacleOnlyMatch[];
  pinnacle_hint?: string;
  spread_hint?: string;
  policy?: StrictPolicyMeta;
  shadow_profile?: "off" | "volume_275" | "volume_200" | "volume_200_upgrade" | string;
  signals_strict?: SignalSummary[];
  signals_volume_profile?: SignalSummary[];
  signals_volume_overlap?: SignalSummary[];
  signals_volume_additional?: SignalSummary[];
  signals_volume?: SignalSummary[];
  signals_volume_200_live?: SignalSummary[];
  signals_volume_200_upgrade_live?: SignalSummary[];
  signals_clay_guarded?: SignalSummary[];
  signals_clay_2026?: SignalSummary[];
  signals_spread_v1?: SignalSummary[];
  signal_attachment?: {
    clay_guarded?: { loaded: number; attached: number; unmatched: number };
    clay_2026?: { loaded: number; attached: number; unmatched: number };
    spread_v1?: { loaded: number; attached: number; unmatched: number };
  };
  error?: string;
}

const SHOW_OU_COLUMNS = false;
const TABLE_BASE_COL_COUNT = SHOW_OU_COLUMNS ? 11 : 9;
const TABLE_MIN_WIDTH = SHOW_OU_COLUMNS ? 1460 : 980;

/* Helpers */

interface OULine {
  line: number;
  fairOver: number;
  fairUnder: number;
  pinnacleOver?: number;
  pinnacleUnder?: number;
}

type OULineKey =
  | "ou_line_1" | "ou_line_2" | "ou_line_3"
  | "ou_over_1" | "ou_over_2" | "ou_over_3"
  | "ou_under_1" | "ou_under_2" | "ou_under_3";

function parseOULines(match: FairOddsMatch): OULine[] {
  const lines: OULine[] = [];
  for (let i = 1; i <= 3; i++) {
    const line = match[`ou_line_${i}` as OULineKey];
    const over = match[`ou_over_${i}` as OULineKey];
    const under = match[`ou_under_${i}` as OULineKey];
    if (line != null && over != null && under != null) {
      lines.push({
        line,
        fairOver: over,
        fairUnder: under,
        ...(match.pinnacle_ou_line === line
          ? {
              pinnacleOver: match.pinnacle_ou_over,
              pinnacleUnder: match.pinnacle_ou_under,
            }
          : {}),
      });
    }
  }
  return lines;
}

function shadowProfileLabel(profile?: string): string {
  if (profile === "volume_200") return "Volume 200";
  if (profile === "volume_200_upgrade") return "Volume 200 Upgrade";
  if (profile === "volume_275") return "Volume 275";
  return "Volume";
}

function shadowProfileBadge(profile?: string): string {
  if (profile === "volume_200") return "VOL200";
  if (profile === "volume_200_upgrade") return "VOL200+";
  if (profile === "volume_275") return "VOL275";
  return "VOL";
}

function valueColor(v: number | undefined): string {
  if (v == null) return "text-slate-500";
  if (Math.abs(v) < 1) return "text-slate-400";
  if (v > 0) {
    if (v >= 5) return "text-emerald-300 font-bold";
    if (v >= 2) return "text-emerald-400 font-semibold";
    return "text-emerald-500/90";
  }
  if (v < 0) {
    if (v <= -10) return "text-red-400 font-bold";
    if (v <= -5) return "text-red-400 font-medium";
    return "text-red-400/80";
  }
  return "text-slate-400";
}

function valueBg(v: number | undefined): string {
  if (v == null || Math.abs(v) < 1) return "";
  if (v >= 5) return "bg-emerald-500/10";
  if (v >= 2) return "bg-emerald-500/5";
  if (v > 0) return "bg-emerald-500/5";
  if (v <= -10) return "bg-red-500/10";
  if (v < 0) return "bg-red-500/5";
  return "";
}

function bestValueBadge(m: FairOddsMatch): { side: string; value: number } | null {
  const v1 = m.value_p1;
  const v2 = m.value_p2;
  if (v1 == null && v2 == null) return null;
  if (v1 == null) return v2 != null ? { side: "P2", value: v2 } : null;
  if (v2 == null) return { side: "P1", value: v1 };
  return v1 >= v2 ? { side: "P1", value: v1 } : { side: "P2", value: v2 };
}

type SignalFeedCategory =
  | "strict"
  | "shadow"
  | "volume_200"
  | "volume_200_upgrade"
  | "volume_275"
  | "clay_guarded"
  | "clay_2026"
  | "spread_v1";

interface SignalFeedItem {
  key: string;
  category: SignalFeedCategory;
  signal: SignalSummary;
}

function signalFeedMeta(category: SignalFeedCategory, shadowProfile?: string): {
  label: string;
  badgeClass: string;
  accentClass: string;
} {
  if (category === "strict") {
    return {
      label: "STRICT",
      badgeClass: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      accentClass: "text-emerald-300",
    };
  }
  if (category === "shadow") {
    return {
      label: shadowProfileBadge(shadowProfile),
      badgeClass: "border-amber-500/30 bg-amber-500/10 text-amber-300",
      accentClass: "text-amber-300",
    };
  }
  if (category === "volume_200") {
    return {
      label: "VOL200",
      badgeClass: "border-amber-500/30 bg-amber-500/10 text-amber-300",
      accentClass: "text-amber-300",
    };
  }
  if (category === "volume_200_upgrade") {
    return {
      label: "VOL200+",
      badgeClass: "border-yellow-400/35 bg-yellow-400/10 text-yellow-200",
      accentClass: "text-yellow-200",
    };
  }
  if (category === "volume_275") {
    return {
      label: "VOL275",
      badgeClass: "border-amber-500/30 bg-amber-500/10 text-amber-300",
      accentClass: "text-amber-300",
    };
  }
  if (category === "clay_guarded") {
    return {
      label: "CLAY GUARD",
      badgeClass: "border-lime-500/30 bg-lime-500/10 text-lime-200",
      accentClass: "text-lime-200",
    };
  }
  if (category === "clay_2026") {
    return {
      label: "CLAY 2026",
      badgeClass: "border-orange-500/30 bg-orange-500/10 text-orange-200",
      accentClass: "text-orange-200",
    };
  }
  return {
    label: "SPREAD V1",
    badgeClass: "border-cyan-500/25 bg-cyan-500/10 text-cyan-300",
    accentClass: "text-cyan-300",
  };
}

function primarySignalBadgeMeta(
  match: FairOddsMatch,
  rowSignals: SignalSummary[],
  shadowProfile?: string,
): { label: string; className: string; title?: string } | null {
  const clayGuardedSignal = rowSignals.find((signal) => signal.kind === "clay_guarded");
  const claySignal = rowSignals.find((signal) => signal.kind === "clay_2026");
  const spreadSignal = rowSignals.find((signal) => signal.kind === "spread_v1");

  if (match.policy_match) {
    return {
      label: "STRICT",
      className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
      title: "Strict policy match",
    };
  }

  if (clayGuardedSignal) {
    return {
      label: "CLAY GUARD",
      className: "border-lime-500/30 bg-lime-500/10 text-lime-200",
      title: `Clay guarded ATP250 dog${clayGuardedSignal.league ? ` | ${clayGuardedSignal.league}` : ""}`,
    };
  }

  if (claySignal) {
    return {
      label: "CLAY 2026",
      className: "border-orange-500/30 bg-orange-500/10 text-orange-200",
      title: `Clay 2026 calibrated ML${claySignal.league ? ` | ${claySignal.league}` : ""}`,
    };
  }

  if (spreadSignal) {
    return {
      label: "SPREAD V1",
      className: "border-cyan-500/25 bg-cyan-500/10 text-cyan-300",
      title: "Spread v1 signal attached",
    };
  }

  if (match.shadow_match) {
    return {
      label: shadowProfileBadge(shadowProfile),
      className: "border-amber-500/30 bg-amber-500/10 text-amber-300",
      title: `${shadowProfileLabel(shadowProfile)} shadow signal`,
    };
  }

  return null;
}

function clay2026SignalMeta(s: SignalSummary): {
  rawBestSide: "P1" | "P2";
  selectedSide: "P1" | "P2";
  marketOdds?: number;
  rawSameSideOdds?: number;
  adjustedOdds?: number;
  rawSameSide?: number;
  adjustedValue: number;
  adjustedProb?: number;
  flipped: boolean;
} | null {
  const calV1 = s.clay_2026_value_p1;
  const calV2 = s.clay_2026_value_p2;
  const rawV1 = s.raw_value_p1;
  const rawV2 = s.raw_value_p2;
  if (calV1 == null && calV2 == null) return null;
  const rawBestGuessSide =
    rawV1 != null || rawV2 != null
      ? ((rawV2 == null || (rawV1 != null && rawV1 >= (rawV2 ?? Number.NEGATIVE_INFINITY)) ? "P1" : "P2") as "P1" | "P2")
      : ((s.side === "P1" ? "P1" : "P2") as "P1" | "P2");
  const selectedSide = ((calV2 == null || (calV1 != null && calV1 >= (calV2 ?? Number.NEGATIVE_INFINITY)) ? "P1" : "P2") as "P1" | "P2");
  return {
    rawBestSide: rawBestGuessSide,
    selectedSide,
    marketOdds: s.pinnacle_odds,
    rawSameSideOdds: selectedSide === "P1" ? s.clay_2026_raw_odds1 : s.clay_2026_raw_odds2,
    adjustedOdds: selectedSide === "P1" ? s.clay_2026_calibrated_odds1 : s.clay_2026_calibrated_odds2,
    rawSameSide: s.clay_2026_raw_value_same_side,
    adjustedValue: s.value_pct,
    adjustedProb:
      s.clay_2026_selected_prob ??
      (selectedSide === "P1"
        ? s.clay_2026_calibrated_odds1 != null && s.clay_2026_calibrated_odds1 > 0
          ? 1 / s.clay_2026_calibrated_odds1
          : undefined
        : s.clay_2026_calibrated_odds2 != null && s.clay_2026_calibrated_odds2 > 0
          ? 1 / s.clay_2026_calibrated_odds2
          : undefined),
    flipped: rawBestGuessSide !== selectedSide,
  };
}

function categoryForShadowProfile(profile?: string): SignalFeedCategory {
  if (profile === "volume_200") return "volume_200";
  if (profile === "volume_200_upgrade") return "volume_200_upgrade";
  if (profile === "volume_275") return "volume_275";
  return "shadow";
}

function rowSignalKindOrder(kind?: SignalSummary["kind"]): number {
  if (kind === "clay_guarded") return 0;
  if (kind === "clay_2026") return 1;
  if (kind === "spread_v1") return 2;
  return 3;
}

function rowSignalSort(signals: SignalSummary[]): SignalSummary[] {
  return [...signals].sort((a, b) => {
    if ((a.kind ?? "") !== (b.kind ?? "")) return rowSignalKindOrder(a.kind) - rowSignalKindOrder(b.kind);
    if ((a.bet_type ?? "") !== (b.bet_type ?? "")) return a.bet_type === "match" ? -1 : 1;
    return (a.side ?? "").localeCompare(b.side ?? "");
  });
}

function signalSideBadgeText(signal: SignalSummary): string {
  if (signal.kind === "spread_v1" && signal.bet_type === "spread") {
    const signedLine =
      signal.side === "P1+"
        ? signal.spread_line
        : signal.spread_line != null
          ? -signal.spread_line
          : undefined;
    return signedLine != null ? `${signal.side.startsWith("P1") ? "P1" : "P2"} ${fmtSignedLine(signedLine)}` : signal.side;
  }
  return signal.side;
}

function MatchSignalsStrip({ signals }: { signals: SignalSummary[] }) {
  if (!signals.length) return null;

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {signals.map((signal) => {
        const clayMeta = signal.kind === "clay_2026" ? clay2026SignalMeta(signal) : null;
        const clayGuardGap = signal.kind === "clay_guarded" ? signal.clay_guarded_selected_elo_gap_vs_market : undefined;
        const handicapShape =
          signal.kind === "spread_v1" ? handicapShapeMeta(signal.handicap_point_prob_source) : null;
        const challengerLabel = signal.league === "Challenger" ? "CH" : null;
        const stakeUnits = signal.stake_units != null ? formatStake(signal.stake_units) : "1.0";
        const stakeGbp = signal.stake_gbp != null ? Math.round(signal.stake_gbp) : 100;

        return (
          <div
            key={`${signal.kind ?? signal.bet_type}-${signal.id}`}
            className={`w-full min-w-0 rounded-xl border px-3 py-3 ${
              signal.kind === "clay_guarded"
                ? "border-lime-500/25 bg-lime-500/8"
                : signal.kind === "clay_2026"
                  ? "border-orange-500/25 bg-orange-500/8"
                  : "border-cyan-500/20 bg-cyan-500/8"
            }`}
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                      signal.kind === "clay_2026"
                        ? "border-orange-500/30 bg-orange-500/10 text-orange-200"
                        : "border-cyan-500/25 bg-cyan-500/10 text-cyan-300"
                    }`}
                  >
                    {signal.kind === "clay_2026" ? "Clay 2026 ML" : "Spread v1"}
                  </span>
                  <span className="rounded border border-slate-700/70 bg-slate-950/70 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-200">
                    {signalSideBadgeText(signal)}
                  </span>
                  {challengerLabel ? (
                    <span className="rounded border border-slate-700/70 bg-slate-950/70 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-300">
                      {challengerLabel}
                    </span>
                  ) : null}
                  {signal.kind === "clay_2026" && signal.league === "Challenger" ? (
                    <span
                      className="rounded border border-amber-500/25 bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-amber-200"
                      title="Challenger is observational only in Clay 2026. ATP is the validated cohort."
                    >
                      UNVALIDATED CH
                    </span>
                  ) : null}
                  {signal.clay_speed_tier === "fast" ? (
                    <span
                      className="rounded border border-cyan-500/25 bg-cyan-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-cyan-300"
                      title={
                        signal.tournament_speed_signal != null
                          ? `Fast clay (${signal.tournament_speed_signal > 0 ? "+" : ""}${signal.tournament_speed_signal.toFixed(3)})`
                          : "Fast clay"
                      }
                    >
                      FAST CLAY
                    </span>
                  ) : null}
                  {clayMeta?.flipped ? (
                    <span className="rounded border border-orange-500/25 bg-orange-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-orange-200">
                      CAL FLIP
                    </span>
                  ) : null}
                  {handicapShape ? (
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] ${handicapShape.cls}`}
                      title={handicapShape.title}
                    >
                      {handicapShape.label}
                    </span>
                  ) : null}
                </div>
                <div className="mt-2 text-[13px] font-semibold text-slate-100">
                  {(signal.side.startsWith("P1") ? signal.player1_name : signal.player2_name)}{" "}
                  {signal.bet_type === "spread" && signal.spread_line != null
                    ? `${fmtSignedLine(signal.side === "P1+" ? signal.spread_line : -signal.spread_line)} HC`
                    : "ML"}{" "}
                  @ {fmtOdds(signal.pinnacle_odds)}
                </div>
              </div>
              <div className="shrink-0 rounded-lg border border-slate-800/60 bg-slate-950/40 px-3 py-2 text-left lg:min-w-[132px] lg:text-right">
                <div className={`font-mono text-[16px] font-semibold tabular-nums ${valueColor(signal.value_pct)}`}>
                  {fmtPct(signal.value_pct)}
                </div>
                <div className="mt-1 text-[11px] text-slate-500">
                  {stakeUnits}u / GBP{stakeGbp}
                </div>
              </div>
            </div>

            {clayMeta ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <div className="rounded-md bg-slate-950/35 px-2 py-1.5">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500">Market</div>
                  <div className="font-mono text-[12px] text-slate-100">
                    {claySideLabel(clayMeta.selectedSide, signal.player1_name, signal.player2_name)} @ {fmtOdds(clayMeta.marketOdds)}
                  </div>
                </div>
                <div className="rounded-md bg-slate-950/35 px-2 py-1.5">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500">Raw Fair</div>
                  <div className="font-mono text-[12px] text-slate-100">
                    {claySideLabel(clayMeta.selectedSide, signal.player1_name, signal.player2_name)} @ {fmtOdds(clayMeta.rawSameSideOdds)}
                  </div>
                  <div className={`mt-0.5 text-[11px] ${valueColor(clayMeta.rawSameSide)}`}>{fmtPct(clayMeta.rawSameSide)}</div>
                </div>
                <div className="rounded-md bg-slate-950/35 px-2 py-1.5">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500">Adjusted Fair</div>
                  <div className="font-mono text-[12px] text-orange-100">
                    {claySideLabel(clayMeta.selectedSide, signal.player1_name, signal.player2_name)} @ {fmtOdds(clayMeta.adjustedOdds)}
                  </div>
                  <div className={`mt-0.5 text-[11px] ${valueColor(clayMeta.adjustedValue)}`}>
                    {fmtPct(clayMeta.adjustedValue)} | {fmtProb(clayMeta.adjustedProb)}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function fmtOdds(v: number | undefined): string {
  if (v == null || v <= 0) return "--";
  return v.toFixed(2);
}

function fmtPct(v: number | undefined): string {
  if (v == null) return "--";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function fmtSignedPct(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "--";
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}pp`;
}

function fmtProb(v: number | undefined): string {
  if (v == null || v <= 0) return "--";
  return `${(v * 100).toFixed(0)}%`;
}

function claySideLabel(side: "P1" | "P2", player1: string, player2: string): string {
  return side === "P1" ? player1 : player2;
}

function fmtSignedLine(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "--";
  const abs = Math.abs(v);
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(1);
  return `${v >= 0 ? "+" : "-"}${body}`;
}

function matchDateKey(match: Pick<FairOddsMatch, "kickoff_iso" | "match_date">): string {
  const kickoffKey = (match.kickoff_iso || "").slice(0, 10);
  if (kickoffKey) return kickoffKey;
  const matchKey = (match.match_date || "").slice(0, 10);
  if (matchKey) return matchKey;
  return "undated";
}

function parseDateKeyUtc(value: string): number {
  if (!value || value === "undated") return Number.MAX_SAFE_INTEGER;
  const parsed = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}

function formatDateSectionLabel(dateKey: string, todayUtc: string): string {
  if (dateKey === "undated") return "Schedule Pending";
  if (dateKey === todayUtc) return "Today";
  const tomorrow = new Date(Date.parse(`${todayUtc}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10);
  if (dateKey === tomorrow) return "Tomorrow";
  const parsed = Date.parse(`${dateKey}T00:00:00Z`);
  if (!Number.isFinite(parsed)) return dateKey;
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(parsed));
}

function formatDateSectionSubLabel(dateKey: string): string {
  if (dateKey === "undated") return "No kickoff in Pinnacle yet";
  return `${dateKey} UTC`;
}

function kickoffSortValue(match: Pick<FairOddsMatch, "kickoff_iso" | "match_date">): number {
  const kickoffMs = Date.parse(match.kickoff_iso || "");
  if (Number.isFinite(kickoffMs)) return kickoffMs;
  return parseDateKeyUtc(matchDateKey(match));
}

function leagueSortRank(league?: FairOddsMatch["league"]): number {
  if (league === "ATP") return 0;
  if (league === "Challenger") return 1;
  return 2;
}

function tournamentLeagueSortRank(matches: FairOddsMatch[]): number {
  return matches.reduce((best, match) => Math.min(best, leagueSortRank(match.league)), 2);
}

function formatKickoffLabel(kickoffIso?: string, matchDate?: string): string | null {
  if (kickoffIso) {
    const parsed = Date.parse(kickoffIso);
    if (Number.isFinite(parsed)) {
      return `${new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "UTC",
      }).format(new Date(parsed))} UTC`;
    }
  }
  if (matchDate) return `${matchDate.slice(0, 10)} UTC`;
  return null;
}

function formatSignalBet(s: SignalSummary): { matchLabel: string; betLine: string } {
  const player = s.side.startsWith("P1") ? s.player1_name : s.player2_name;
  const odds = s.pinnacle_odds != null ? s.pinnacle_odds.toFixed(2) : "--";
  const units = s.stake_units != null ? s.stake_units : 1;
  const gbp = s.stake_gbp != null ? Math.round(s.stake_gbp) : 100;
  const stakePart = `x ${formatStake(units)}u (or GBP${gbp})`;

  if (s.bet_type === "spread" && s.spread_line != null) {
    const line = s.side === "P1+" ? s.spread_line : -s.spread_line;
    return {
      matchLabel: `${s.player1_name} vs ${s.player2_name}`,
      betLine: `${player} ${fmtSignedLine(line)}HC ${odds} ${stakePart}`,
    };
  }

  return {
    matchLabel: `${s.player1_name} vs ${s.player2_name}`,
    betLine: `${player} ML ${odds} ${stakePart}`,
  };
}

function sortSignalFeedItems(items: SignalFeedItem[]): SignalFeedItem[] {
  return [...items].sort(
    (a, b) => (b.signal.value_pct ?? Number.NEGATIVE_INFINITY) - (a.signal.value_pct ?? Number.NEGATIVE_INFINITY),
  );
}

function SignalFeedList({
  items,
  emptyLabel,
  shadowProfile,
}: {
  items: SignalFeedItem[];
  emptyLabel: string;
  shadowProfile?: string;
}) {
  if (!items.length) {
    return <p className="text-[13px] text-slate-500 italic">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-2">
      {items.map(({ key, category, signal }) => {
        const meta = signalFeedMeta(category, shadowProfile);
        const clayMeta = signal.kind === "clay_2026" ? clay2026SignalMeta(signal) : null;
        const clayGuardGap =
          signal.kind === "clay_guarded" ? signal.clay_guarded_selected_elo_gap_vs_market : undefined;
        const { matchLabel, betLine } = formatSignalBet(signal);
        return (
          <li key={key} className="rounded-xl border border-slate-700/50 bg-slate-900/55 px-3 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${meta.badgeClass}`}>
                    {meta.label}
                  </span>
                  {signal.league === "Challenger" ? (
                    <span className="rounded border border-slate-700/70 bg-slate-950/70 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-300">
                      CH
                    </span>
                  ) : null}
                  {signal.kind === "clay_2026" && signal.league === "Challenger" ? (
                    <span className="rounded border border-amber-500/25 bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-amber-200">
                      UNVALIDATED CH
                    </span>
                  ) : null}
                  {signal.kind === "clay_2026" && signal.clay_speed_tier === "fast" ? (
                    <span className="rounded border border-cyan-500/25 bg-cyan-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-cyan-300">
                      FAST CLAY
                    </span>
                  ) : null}
                  {signal.kind === "spread_v1" && signal.shadow_reason ? (
                    <span className="rounded border border-cyan-500/25 bg-cyan-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-cyan-300">
                      {signalReasonLabel(signal.shadow_reason)}
                    </span>
                  ) : null}
                  {signal.kind === "clay_guarded" && signal.shadow_reason ? (
                    <span className="rounded border border-lime-500/25 bg-lime-500/10 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-[0.12em] text-lime-200">
                      {signalReasonLabel(signal.shadow_reason)}
                    </span>
                  ) : null}
                </div>
                <div className="mt-1 text-[11px] font-medium text-slate-500 truncate">{matchLabel}</div>
                <div className={`mt-1 font-mono text-[13px] font-semibold tabular-nums ${meta.accentClass}`}>{betLine}</div>
                {clayMeta ? (
                  <div className="mt-1 text-[11px] text-slate-500">
                    Adjusted fair {fmtOdds(clayMeta.adjustedOdds)} | {fmtProb(clayMeta.adjustedProb)}
                  </div>
                ) : null}
                {signal.kind === "clay_guarded" && clayGuardGap != null ? (
                  <div className="mt-1 text-[11px] text-slate-500">
                    Elo vs market {fmtSignedPct(clayGuardGap * 100)}
                  </div>
                ) : null}
              </div>
              <div className={`shrink-0 font-mono text-[16px] font-semibold tabular-nums ${valueColor(signal.value_pct)}`}>
                {fmtPct(signal.value_pct)}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}


function signalReasonLabel(reason?: string): string {
  if (reason === "clay_non_policy") return "Clay + non-policy";
  if (reason === "clay") return "Clay";
  if (reason === "non_policy") return "Non-policy";
  if (reason === "allow_tier_dog_elo_ge_market_15") return "Allow + Elo>=Mkt";
  if (reason === "new_after_calibration_favorite_55_65") return "Clay 2026";
  if (reason === "strict_first_atp_bo3_hard_clay") return "Strict-first ATP";
  return "Spread v1";
}

function handicapShapeMeta(source?: SignalSummary["handicap_point_prob_source"] | FairOddsMatch["handicap_point_prob_source"]) {
  if (source === "stored_p_a_p_b") {
    return {
      label: "HC-STORED",
      cls: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
      title: "Handicap uses stored player-specific point probabilities",
    };
  }
  if (source === "fallback_divergent_gap") {
    return {
      label: "HC-FALLBACK",
      cls: "border-rose-500/25 bg-rose-500/10 text-rose-200",
      title: "Handicap fell back to reverse-solved point probabilities because stored shape diverged from final match probability",
    };
  }
  if (source === "fallback_missing") {
    return {
      label: "HC-FALLBACK",
      cls: "border-rose-500/25 bg-rose-500/10 text-rose-200",
      title: "Handicap fell back to reverse-solved point probabilities because stored point probabilities were missing",
    };
  }
  return null;
}

const SURFACE_COLORS: Record<string, string> = {
  Hard: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  Clay: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  Grass: "bg-green-500/15 text-green-400 border-green-500/25",
  Carpet: "bg-purple-500/15 text-purple-400 border-purple-500/25",
};

function SurfaceBadge({ surface }: { surface: string }) {
  const cls = SURFACE_COLORS[surface] ?? "bg-slate-700/40 text-slate-400 border-slate-600/30";
  return (
    <span className={`inline-block text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded border ${cls}`}>
      {surface || "?"}
    </span>
  );
}

function confidenceMeta(conf?: string): { label: string; cls: string } {
  if (conf === "high") return { label: "HIGH", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" };
  if (conf === "medium") return { label: "MED", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" };
  if (conf === "low") return { label: "LOW", cls: "bg-orange-500/15 text-orange-300 border-orange-500/30" };
  if (conf === "none") return { label: "NONE", cls: "bg-red-500/15 text-red-300 border-red-500/30" };
  return { label: "N/A", cls: "bg-slate-700/40 text-slate-400 border-slate-600/30" };
}

/* Page Component */

export default function FairOddsPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/fair-odds?ts=${Date.now()}`, { cache: "no-store" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const json: ApiResponse = await res.json();
      if (json.error) throw new Error(json.error);
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load fair odds");
    } finally {
      setLoading(false);
    }
  }

  const matches = data?.matches ?? [];

  const now = new Date();
  const todayUTC = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}`;
  const groupedByDate = Array.from(
    matches.reduce((dateMap, match) => {
      const dateKey = matchDateKey(match);
      const tournamentKey = match.tournament || "Unknown";
      const tournamentMap = dateMap.get(dateKey) ?? new Map<string, FairOddsMatch[]>();
      const tournamentRows = tournamentMap.get(tournamentKey) ?? [];
      tournamentRows.push(match);
      tournamentMap.set(tournamentKey, tournamentRows);
      dateMap.set(dateKey, tournamentMap);
      return dateMap;
    }, new Map<string, Map<string, FairOddsMatch[]>>()).entries()
  )
    .sort(([left], [right]) => parseDateKeyUtc(left) - parseDateKeyUtc(right))
    .map(([dateKey, tournamentMap]) => ({
      dateKey,
      label: formatDateSectionLabel(dateKey, todayUTC),
      subLabel: formatDateSectionSubLabel(dateKey),
      tournaments: Array.from(tournamentMap.entries())
        .map(([tournament, rows]) => ({
          tournament,
          matches: [...rows].sort((a, b) => {
            const leagueDelta = leagueSortRank(a.league) - leagueSortRank(b.league);
            if (leagueDelta !== 0) return leagueDelta;
            const kickoffDelta = kickoffSortValue(a) - kickoffSortValue(b);
            if (kickoffDelta !== 0) return kickoffDelta;
            return `${a.player1_name}|${a.player2_name}`.localeCompare(`${b.player1_name}|${b.player2_name}`);
          }),
        }))
        .sort((a, b) => {
          const leagueDelta = tournamentLeagueSortRank(a.matches) - tournamentLeagueSortRank(b.matches);
          if (leagueDelta !== 0) return leagueDelta;
          const kickoffDelta =
            kickoffSortValue(a.matches[0] ?? { match_date: undefined, kickoff_iso: undefined }) -
            kickoffSortValue(b.matches[0] ?? { match_date: undefined, kickoff_iso: undefined });
          if (kickoffDelta !== 0) return kickoffDelta;
          return a.tournament.localeCompare(b.tournament);
        }),
    }));
  const shadowOnlySignals = data?.signals_volume_additional ?? data?.signals_volume ?? [];
  const strictFeedItems = sortSignalFeedItems(
    (data?.signals_strict ?? []).map((signal) => ({
      key: `strict-${signal.id}`,
      category: "strict" as const,
      signal,
    })),
  );
  const activeShadowCategory = categoryForShadowProfile(data?.shadow_profile);
  const shadowFeedItems = sortSignalFeedItems(
    shadowOnlySignals.map((signal) => ({
      key: `shadow-${signal.id}`,
      category: activeShadowCategory,
      signal,
    })),
  );
  const volume200CompareFeedItems = sortSignalFeedItems(
    (data?.signals_volume_200_live ?? []).map((signal) => ({
      key: `volume200-${signal.id}`,
      category: "volume_200" as const,
      signal,
    })),
  );
  const volume200UpgradeFeedItems = sortSignalFeedItems(
    (data?.signals_volume_200_upgrade_live ?? []).map((signal) => ({
      key: `volume200u-${signal.id}`,
      category: "volume_200_upgrade" as const,
      signal,
    })),
  );
  const clayGuardedFeedItems = sortSignalFeedItems(
    (data?.signals_clay_guarded ?? []).map((signal) => ({
      key: `clay-guarded-${signal.id}`,
      category: "clay_guarded" as const,
      signal,
    })),
  );
  const clayFeedItems = sortSignalFeedItems(
    (data?.signals_clay_2026 ?? []).map((signal) => ({
      key: `clay-${signal.id}`,
      category: "clay_2026" as const,
      signal,
    })),
  );
  const spreadFeedItems = sortSignalFeedItems(
    (data?.signals_spread_v1 ?? []).map((signal) => ({
      key: `spread-${signal.id}`,
      category: "spread_v1" as const,
      signal,
    })),
  );
  const signalSections = [
    {
      key: "strict",
      category: "strict" as const,
      title: "Strict",
      subtitle: "Main strict policy",
      items: strictFeedItems,
      emptyLabel: "No strict signals today",
    },
    {
      key: "shadow",
      category: activeShadowCategory,
      title: shadowProfileLabel(data?.shadow_profile),
      subtitle: "Shadow-only ML additions",
      items: shadowFeedItems,
      emptyLabel: `No ${shadowProfileLabel(data?.shadow_profile).toLowerCase()} shadow-only signals today`,
    },
    ...(data?.shadow_profile !== "volume_200" && volume200CompareFeedItems.length
      ? [
          {
            key: "volume200-compare",
            category: "volume_200" as const,
            title: "Volume 200",
            subtitle:
              data?.shadow_profile === "volume_200"
                ? "Active volume lane"
                : "Parallel baseline lane",
            items: volume200CompareFeedItems,
            emptyLabel: "No Volume 200 signals today",
          },
        ]
      : []),
    ...(data?.shadow_profile !== "volume_200_upgrade" && volume200UpgradeFeedItems.length
      ? [
          {
            key: "volume200u-compare",
            category: "volume_200_upgrade" as const,
            title: "Volume 200 Upgrade",
            subtitle:
              data?.shadow_profile === "volume_200_upgrade"
                ? "Active upgraded volume lane"
                : "Parallel candidate lane",
            items: volume200UpgradeFeedItems,
            emptyLabel: "No Volume 200 Upgrade signals today",
          },
        ]
      : []),
    {
      key: "clay-guarded",
      category: "clay_guarded" as const,
      title: "Clay Guard",
      subtitle: "Allow-tier ATP250 dogs with Elo >= market",
      items: clayGuardedFeedItems,
      emptyLabel: "No Clay Guard signals today",
    },
    {
      key: "clay",
      category: "clay_2026" as const,
      title: "Clay 2026",
      subtitle: "Calibrated clay ML lane",
      items: clayFeedItems,
      emptyLabel: "No Clay 2026 signals today",
    },
    {
      key: "spread",
      category: "spread_v1" as const,
      title: "Spread v1",
      subtitle: "Strict-first ATP bo3 hard/clay research spreads",
      items: spreadFeedItems,
      emptyLabel: "No spread v1 signals today",
    },
  ];

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_20%_0%,#1a2235_0%,#0f1117_45%,#0c0e14_100%)] text-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumbs */}
        <nav className="flex items-center gap-2 text-sm text-slate-500 mb-6">
          <Link href="/" className="hover:text-slate-300 transition-colors">Home</Link>
          <span>/</span>
          <span className="text-slate-300">Fair Odds</span>
        </nav>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100 tracking-tight">
              Daily Matches &amp; Fair Odds
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {todayUTC} UTC &middot; Barnett-Clarke model with serve volatility calibration
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowStats(!showStats)}
              className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                showStats
                  ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                  : "border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600"
              }`}
            >
              {showStats ? "Hide Stats" : "Show Stats"}
            </button>
            <button
              onClick={fetchData}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded border border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600 transition-colors disabled:opacity-40"
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
          </div>
        </div>

        {data && (
          <div className="mb-4 rounded-xl border border-slate-700/60 bg-slate-900/35 px-3 py-2.5 text-[11px] text-slate-400">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span>Pinnacle <span className="text-slate-200">{data.pinnacle_count}</span> loaded</span>
              <span><span className="text-slate-200">{data.pinnacle_matched_count}</span> matched</span>
              {data.signal_attachment && (
                <>
                  <span className={data.signal_attachment.clay_guarded?.unmatched ? "text-amber-300" : ""}>
                    Clay Guard <span className="text-slate-200">{data.signal_attachment.clay_guarded?.attached ?? 0}/{data.signal_attachment.clay_guarded?.loaded ?? 0}</span>
                  </span>
                  <span className={data.signal_attachment.clay_2026?.unmatched ? "text-amber-300" : ""}>
                    Clay 2026 <span className="text-slate-200">{data.signal_attachment.clay_2026?.attached ?? 0}/{data.signal_attachment.clay_2026?.loaded ?? 0}</span>
                  </span>
                  <span className={data.signal_attachment.spread_v1?.unmatched ? "text-amber-300" : ""}>
                    Spread v1 <span className="text-slate-200">{data.signal_attachment.spread_v1?.attached ?? 0}/{data.signal_attachment.spread_v1?.loaded ?? 0}</span>
                  </span>
                </>
              )}
              {data.matches_with_row_signals != null && (
                <span>Across <span className="text-slate-200">{data.matches_with_row_signals}</span> matches with signals</span>
              )}
              <div className="ml-auto">
                <details className="group">
                  <summary className="cursor-pointer list-none rounded border border-slate-700/70 bg-slate-950/60 px-2 py-1 text-[11px] text-slate-300 transition-colors hover:border-slate-600 hover:text-slate-100">
                    Policy & diagnostics
                  </summary>
                  <div className="mt-2 max-w-3xl rounded-lg border border-slate-700/60 bg-slate-950/80 p-3 text-[11px] leading-5 text-slate-400 shadow-xl">
                    {data.policy?.mode === "strict" ? (
                      <p>
                        Strict policy on ({data.policy.production_mode ?? "base"}): {data.policy.allowed_segments.join(", ")} | value &gt;= {data.policy.min_value_pct.toFixed(1)}% | confidence {data.policy.allowed_confidence.join("/")} | signals {data.policy.signaled_matches}/{data.policy.eligible_matches}.
                        {data.policy.production_mode === "overlay" && data.policy.overlay ? ` Overlay ${data.policy.overlay.passed_matches}/${data.policy.overlay.considered_matches} (skip missing=${data.policy.overlay.skipped_missing}, n=${data.policy.overlay.skipped_min_n}, roi=${data.policy.overlay.skipped_min_roi}).` : ""}
                      </p>
                    ) : null}
                    {data.pinnacle_hint ? <p className="mt-2 text-amber-300/80">{data.pinnacle_hint}</p> : null}
                    {data.spread_hint ? <p className="mt-2 text-amber-300/80">{data.spread_hint}</p> : null}
                  </div>
                </details>
              </div>
            </div>
          </div>
        )}

        {!loading && !error && data && matches.length > 0 && (
          <div className="mb-6 rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4 shadow-[0_10px_40px_rgba(0,0,0,0.25)]">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-base font-semibold tracking-tight text-slate-100">Signals</h2>
                <p className="mt-1 text-[13px] text-slate-500">
                  Click a policy to expand its signals. Each section stays sorted by highest value first.
                </p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {signalSections.map((section) => {
                const meta = signalFeedMeta(section.category, data.shadow_profile);
                const topSignal = section.items[0]?.signal;
                return (
                  <details
                    key={section.key}
                    className="group rounded-xl border border-slate-700/50 bg-slate-950/35"
                  >
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] ${meta.badgeClass}`}>
                            {meta.label}
                          </span>
                          <span className="text-[14px] font-medium text-slate-100">{section.title}</span>
                          <span className="text-[12px] text-slate-500">{section.subtitle}</span>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-[11px]">
                        <span className="text-slate-400">
                          <span className="text-slate-200">{section.items.length}</span> signals
                        </span>
                        {topSignal ? (
                          <span className={`font-mono ${valueColor(topSignal.value_pct)}`}>
                            Top {fmtPct(topSignal.value_pct)}
                          </span>
                        ) : null}
                        <span className="text-slate-500 transition-transform group-open:rotate-180">v</span>
                      </div>
                    </summary>
                    <div className="border-t border-slate-800/70 px-3 pb-3 pt-3">
                      <SignalFeedList
                        items={section.items}
                        emptyLabel={section.emptyLabel}
                        shadowProfile={data.shadow_profile}
                      />
                    </div>
                  </details>
                );
              })}
            </div>

            {data.signal_attachment && (
              <div className="mt-4 border-t border-slate-800/70 pt-3 text-[11px] text-slate-500">
                Clay Guard {data.signal_attachment.clay_guarded?.attached ?? 0}/{data.signal_attachment.clay_guarded?.loaded ?? 0}
                {" | "}
                Clay 2026 {data.signal_attachment.clay_2026?.attached ?? 0}/{data.signal_attachment.clay_2026?.loaded ?? 0}
                {" | "}
                Spread v1 {data.signal_attachment.spread_v1?.attached ?? 0}/{data.signal_attachment.spread_v1?.loaded ?? 0}
                {data.matches_with_row_signals != null ? ` | ${data.matches_with_row_signals} matches with signals` : ""}
              </div>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-24">
            <div className="flex items-center gap-3 text-slate-500">
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Loading fair odds...
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-5 py-4 mb-6">
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={fetchData}
              className="mt-2 text-xs text-red-300 underline hover:text-red-200"
            >
              Try again
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && matches.length === 0 && (
          <div className="text-center py-24 text-slate-500">
            <p className="text-lg mb-2">No matches for today</p>
            <p className="text-sm">Run <code className="text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded font-mono text-xs">python scripts/oncourt-compute-fair-odds.py</code> to compute fair odds, then refresh.</p>
          </div>
        )}

        {/* Table: 9 core + optional 2 O/U + 6 stat columns */}
        {!loading && matches.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-700/60 bg-slate-900/35 shadow-[0_10px_40px_rgba(0,0,0,0.35)] min-w-0 w-full" style={{ scrollbarGutter: "stable" }}>
            <p className="text-[10px] text-slate-600 px-3 py-1.5 border-b border-slate-800/50 bg-slate-900/30">
              Scroll horizontally if needed. Pinnacle odds from public API each run.
            </p>
            <table className="w-full text-sm table-fixed" style={{ minWidth: TABLE_MIN_WIDTH }}>
              <colgroup>
                <col style={{ width: 320 }} />
                <col style={{ width: 58 }} />
              <col style={{ width: 68 }} />
              <col style={{ width: 68 }} />
              <col style={{ width: 68 }} />
              <col style={{ width: 68 }} />
                <col style={{ width: 90 }} />
                <col style={{ width: 56 }} />
                <col style={{ width: 150 }} />
                {SHOW_OU_COLUMNS && <col style={{ width: 220 }} />}
                {SHOW_OU_COLUMNS && <col style={{ width: 220 }} />}
                {showStats && <col style={{ width: 130 }} />}
              </colgroup>
              <thead>
                <tr className="border-b-2 border-slate-700/70 bg-[#0d0f14]/90 text-slate-300 text-[11px] uppercase tracking-wider">
                  <th className="text-left px-3 py-3 font-semibold sticky left-0 bg-[#0d0f14]/95 z-10 border-r border-slate-800/50">Match</th>
                  <th className="text-center px-2 py-3 font-semibold">Surf</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Fair Odds</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Pinnacle</th>
                  <th className="text-center px-2 py-3 font-semibold text-emerald-500/70" title="Value % = (Pinnacle / Our odds) - 1; positive = value at Pinnacle">Best Value</th>
                  <th className="text-center px-2 py-3 font-semibold">E[G]</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-400">Spread</th>
                  {SHOW_OU_COLUMNS && <th className="text-left px-2 py-3 font-semibold">O/U Fair</th>}
                  {SHOW_OU_COLUMNS && <th className="text-left px-2 py-3 font-semibold">O/U Pin</th>}
                  {showStats && (
                    <th className="text-center px-2 py-3 font-medium text-[10px]" title="S% R% T (serve, return, total)">
                      <span className="block">Stats</span>
                      <span className="block text-[10px] text-slate-500 font-normal">S / R / T</span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {groupedByDate.map((group) => (
                  <DateSection
                    key={group.dateKey}
                    dateKey={group.dateKey}
                    label={group.label}
                    subLabel={group.subLabel}
                    tournaments={group.tournaments}
                    showStats={showStats}
                    colSpan={TABLE_BASE_COL_COUNT + (showStats ? 1 : 0)}
                    shadowProfile={data?.shadow_profile}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pinnacle only: matches in Pinnacle but not in our fair-odds (e.g. not in OnCourt today) */}
        {!loading && !error && data?.pinnacle_only && data.pinnacle_only.length > 0 && (
          <div className="mt-8 rounded-xl border border-slate-700/50 bg-slate-900/25 p-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Pinnacle only ({data.pinnacle_only.length} matches)
            </h2>
            <p className="text-[11px] text-slate-500 mb-3">
              These matches are in Pinnacle&apos;s snapshot but not in our fair-odds data (e.g. not in OnCourt today, or tournament not synced). Pinnacle odds and O/U only; no model value.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[400px]">
                <thead>
                  <tr className="border-b border-slate-700/80 text-slate-500 text-[11px] uppercase">
                    <th className="text-left py-2 px-2">When</th>
                    <th className="text-left py-2 px-2">Tournament</th>
                    <th className="text-left py-2 px-2">Match</th>
                    <th className="text-center py-2 px-2">Pinnacle Odds</th>
                    <th className="text-center py-2 px-2">O/U</th>
                  </tr>
                </thead>
                <tbody>
                  {data.pinnacle_only.map((m, i) => (
                    <tr key={i} className="border-b border-slate-800/50 text-slate-400">
                      <td className="py-2 px-2 text-[11px] text-slate-500">
                        {formatKickoffLabel(m.kickoff_iso, m.match_date) ?? "--"}
                      </td>
                      <td className="py-2 px-2 text-[11px] text-slate-500">
                        {m.tournament || "--"}
                      </td>
                      <td className="py-2 px-2">{(m.player1_name || "--")} vs {(m.player2_name || "--")}</td>
                      <td className="py-2 px-2 text-center font-mono tabular-nums">
                        {m.odds1 > 0 && m.odds2 > 0 ? `${m.odds1.toFixed(2)} / ${m.odds2.toFixed(2)}` : "--"}
                      </td>
                      <td className="py-2 px-2 text-center font-mono tabular-nums">
                        {m.ou_line != null && m.ou_over != null && m.ou_under != null
                          ? `${m.ou_line} (${m.ou_over.toFixed(2)} / ${m.ou_under.toFixed(2)})`
                          : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-slate-800/50 text-xs text-slate-600 text-center">
          Il Margine &middot; Fair odds generated by Barnett-Clarke + K-M recursion model with serve volatility calibration (sigma=0.035).
          <br />
          Pinnacle odds scraped for comparison only. Not financial advice.
        </footer>
      </div>
    </div>
  );
}

/* Tournament Group */

function DateSection({
  dateKey,
  label,
  subLabel,
  tournaments,
  showStats,
  colSpan,
  shadowProfile,
}: {
  dateKey: string;
  label: string;
  subLabel: string;
  tournaments: Array<{ tournament: string; matches: FairOddsMatch[] }>;
  showStats: boolean;
  colSpan: number;
  shadowProfile?: string;
}) {
  return (
    <>
      <tr className="bg-[#090b11]">
        <td
          colSpan={colSpan}
          className="px-3 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-200 border-y border-cyan-500/20 bg-[linear-gradient(90deg,rgba(34,211,238,0.12),rgba(34,211,238,0.03),transparent)]"
        >
          <div className="flex items-center justify-between gap-3">
            <span>{label}</span>
            <span className="text-[10px] font-medium tracking-[0.16em] text-cyan-300/60">{subLabel}</span>
          </div>
        </td>
      </tr>
      {tournaments.map(({ tournament, matches }) => (
        <TournamentGroup
          key={`${dateKey}-${tournament}`}
          tournament={tournament}
          matches={matches}
          showStats={showStats}
          colSpan={colSpan}
          shadowProfile={shadowProfile}
        />
      ))}
    </>
  );
}

function TournamentGroup({
  tournament,
  matches,
  showStats,
  colSpan,
  shadowProfile,
}: {
  tournament: string;
  matches: FairOddsMatch[];
  showStats: boolean;
  colSpan: number;
  shadowProfile?: string;
}) {
  return (
    <>
      <tr className="bg-[#0c0e14]">
        <td
          colSpan={colSpan}
          className="px-3 py-2.5 text-[11px] font-semibold text-slate-300 uppercase tracking-widest border-b-2 border-slate-700/50 border-t border-slate-700/30"
        >
          {tournament}
        </td>
      </tr>
      {matches.map((m) => (
        <MatchRow key={m.id} match={m} showStats={showStats} shadowProfile={shadowProfile} colSpan={colSpan} />
      ))}
    </>
  );
}

/* Match Row */

function MatchRow({
  match,
  showStats,
  shadowProfile,
  colSpan,
}: {
  match: FairOddsMatch;
  showStats: boolean;
  shadowProfile?: string;
  colSpan: number;
}) {
  const m = match;
  const ouLines = SHOW_OU_COLUMNS ? parseOULines(m) : [];
  const hasPinnacle = m.pinnacle_odds1 != null && m.pinnacle_odds1 > 0;
  const handicapShape = handicapShapeMeta(m.handicap_point_prob_source);
  const rowSignals = rowSignalSort(m.row_signals ?? []);
  const bestValue = bestValueBadge(m);
  const primaryBadge = primarySignalBadgeMeta(m, rowSignals, shadowProfile);
  const blockedDetail =
    m.blocked_reason && !m.policy_match && !m.shadow_match && bestValue && bestValue.value > 0
      ? m.blocked_reason
      : null;
  const hasDetailRow = rowSignals.length > 0 || !!blockedDetail;
  const kickoffLabel = formatKickoffLabel(m.kickoff_iso, m.match_date);

  return (
    <>
      <tr className={`${hasDetailRow ? "border-b-0" : "border-b"} border-slate-800/40 hover:bg-slate-800/35 even:bg-slate-900/25 transition-colors ${
        m.confidence === "none" ? "opacity-40" : ""
      }`}>
        <td className="px-3 py-3 sticky left-0 bg-[#111520]/95 z-10 border-r border-slate-800/50">
          <div className="flex flex-col gap-1 min-w-0">
            <span
              className="block truncate text-[13px] font-medium leading-snug text-slate-100"
              title={`${m.player1_name || "TBD"} vs ${m.player2_name || "TBD"} | ${fmtProb(m.p1_win_prob)} / ${fmtProb(m.p2_win_prob)}`}
            >
              {m.player1_name || "TBD"}
              <span className="mx-1.5 text-xs font-normal text-slate-600">vs</span>
              {m.player2_name || "TBD"}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${confidenceMeta(m.confidence).cls}`}
                title={`Confidence: ${m.confidence ?? "n/a"}`}
              >
                {confidenceMeta(m.confidence).label}
              </span>
              {primaryBadge ? (
                <span
                  className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${primaryBadge.className}`}
                  title={primaryBadge.title}
                >
                  {primaryBadge.label}
                </span>
              ) : null}
              {kickoffLabel ? (
                <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                  {kickoffLabel}
                </span>
              ) : null}
            </div>
          </div>
        </td>

        <td className="text-center px-2 py-2.5">
          <SurfaceBadge surface={m.surface} />
        </td>

        <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds1)}</td>
        <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds2)}</td>

        <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] text-slate-300">
          {hasPinnacle ? fmtOdds(m.pinnacle_odds1) : <span className="text-slate-600">--</span>}
        </td>
        <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] text-slate-300">
          {hasPinnacle ? fmtOdds(m.pinnacle_odds2) : <span className="text-slate-600">--</span>}
        </td>

        <td className="text-center px-2.5 py-3 font-mono tabular-nums text-[13px]">
          <span
            className={`inline-flex rounded-md px-1.5 py-0.5 ${bestValue ? `${valueColor(bestValue.value)} ${valueBg(bestValue.value)}` : "text-slate-500"}`}
            title="Best-side value % = (Pinnacle / Our odds) - 1"
          >
            {bestValue ? `${bestValue.side} ${fmtPct(bestValue.value)}` : "--"}
          </span>
        </td>

        <td className="text-center px-2 py-2.5 font-mono tabular-nums text-sm text-slate-300 overflow-hidden">
          {m.expected_total_games != null ? m.expected_total_games.toFixed(1) : "--"}
        </td>

        <td className="px-2 py-2.5 min-w-[140px]">
          {m.spread_line != null ? (
            <div className="text-[11px] font-mono tabular-nums space-y-1">
              <div className="flex items-center justify-between gap-2">
                <div className="text-slate-500 font-medium">{fmtSignedLine(m.spread_line)}</div>
                {handicapShape ? (
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${handicapShape.cls}`}
                    title={`${handicapShape.title}${m.handicap_point_prob_gap != null ? ` | gap ${m.handicap_point_prob_gap > 0 ? "+" : ""}${m.handicap_point_prob_gap.toFixed(3)}` : ""}`}
                  >
                    {handicapShape.label}
                  </span>
                ) : null}
              </div>
              <div className="grid grid-cols-[1fr_auto_auto] gap-x-2 gap-y-0.5 items-center">
                <span className="text-slate-400 truncate">P1 {fmtSignedLine(m.spread_line)}</span>
                <span className="text-slate-300">{m.spread_odds1 != null ? m.spread_odds1.toFixed(2) : "--"}</span>
                <span className={`min-w-[3rem] text-right ${valueColor(m.handicap_edge_p1)}`}>
                  {m.handicap_edge_p1 != null ? `${m.handicap_edge_p1 > 0 ? "+" : ""}${m.handicap_edge_p1.toFixed(1)}%` : "--"}
                </span>
                <span className="text-slate-400 truncate">P2 {fmtSignedLine(-m.spread_line)}</span>
                <span className="text-slate-300">{m.spread_odds2 != null ? m.spread_odds2.toFixed(2) : "--"}</span>
                <span className={`min-w-[3rem] text-right ${valueColor(m.handicap_edge_p2)}`}>
                  {m.handicap_edge_p2 != null ? `${m.handicap_edge_p2 > 0 ? "+" : ""}${m.handicap_edge_p2.toFixed(1)}%` : "--"}
                </span>
              </div>
            </div>
          ) : (
            <span className="text-slate-600 text-xs">--</span>
          )}
        </td>
        {SHOW_OU_COLUMNS && (
          <td className="px-2 py-2.5 align-top">
            <OverUnderFairCell lines={ouLines} />
          </td>
        )}
        {SHOW_OU_COLUMNS && (
          <td className="px-2 py-2.5 align-top">
            <OverUnderPinCell match={m} lines={ouLines} />
          </td>
        )}
        {showStats && (
          <td className="px-2 py-2.5 font-mono text-[11px] tabular-nums text-slate-200">
            <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
              <span className="text-slate-500 text-[10px]">P1</span>
              <span>{m.p1_serve != null ? m.p1_serve.toFixed(1) : "--"} / {m.p1_return != null ? m.p1_return.toFixed(1) : "--"} / {m.p1_total != null ? m.p1_total.toFixed(1) : "--"}</span>
              <span className="text-slate-500 text-[10px]">P2</span>
              <span>{m.p2_serve != null ? m.p2_serve.toFixed(1) : "--"} / {m.p2_return != null ? m.p2_return.toFixed(1) : "--"} / {m.p2_total != null ? m.p2_total.toFixed(1) : "--"}</span>
            </div>
          </td>
        )}
      </tr>
      {rowSignals.length > 0 && (
        <tr className="border-b border-slate-800/40 bg-slate-950/35">
          <td colSpan={colSpan} className="px-3 py-3">
            {blockedDetail ? (
              <div className="mb-2 text-[11px] text-amber-300/75">
                {blockedDetail}
              </div>
            ) : null}
            <MatchSignalsStrip signals={rowSignals} />
          </td>
        </tr>
      )}
      {!rowSignals.length && blockedDetail && (
        <tr className="border-b border-slate-800/40 bg-slate-950/20">
          <td colSpan={colSpan} className="px-3 py-2 text-[11px] text-amber-300/75">
            {blockedDetail}
          </td>
        </tr>
      )}
    </>
  );
}

const OU_ROW_CLASS =
  "grid grid-cols-[44px_86px_86px] items-center gap-x-2 text-[12px] leading-5 font-mono tabular-nums";

function OverUnderFairCell({ lines }: { lines: OULine[] }) {
  if (lines.length === 0) return <span className="text-slate-500 text-xs">--</span>;

  return (
    <div className="space-y-1">
      {lines.map((ou) => (
        <div key={ou.line} className={OU_ROW_CLASS}>
          <span className="text-slate-400">{ou.line.toFixed(1)}</span>
          <span className="text-slate-200">
            <span className="text-slate-500 mr-1">O</span>
            {ou.fairOver.toFixed(2)}
          </span>
          <span className="text-slate-200">
            <span className="text-slate-500 mr-1">U</span>
            {ou.fairUnder.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}

function OverUnderPinCell({ match, lines }: { match: FairOddsMatch; lines: OULine[] }) {
  const pinLine = match.pinnacle_ou_line;
  const pinOver = match.pinnacle_ou_over;
  const pinUnder = match.pinnacle_ou_under;
  const hasPin = pinLine != null && pinOver != null && pinUnder != null;

  if (lines.length === 0) return <span className="text-slate-500 text-xs">--</span>;

  const isSameLine = (line: number) => hasPin && Math.abs(line - (pinLine as number)) < 1e-6;

  return (
    <div className="space-y-1">
      {lines.map((ou) => {
        const showPin = isSameLine(ou.line);

        return (
          <div key={ou.line} className={OU_ROW_CLASS}>
            <span className={showPin ? "text-amber-300 font-semibold" : "text-slate-500/80"}>
              {ou.line.toFixed(1)}
            </span>

            <span className={showPin ? "text-slate-200" : "text-slate-500/70"}>
              {showPin ? (
                <>
                  <span className="text-slate-500 mr-1">O</span>
                  {pinOver!.toFixed(2)}
                </>
              ) : (
                <span className="text-slate-600">-</span>
              )}
            </span>

            <span className={showPin ? "text-slate-200" : "text-slate-500/70"}>
              {showPin ? (
                <>
                  <span className="text-slate-500 mr-1">U</span>
                  {pinUnder!.toFixed(2)}
                </>
              ) : (
                <span className="text-slate-600">-</span>
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

