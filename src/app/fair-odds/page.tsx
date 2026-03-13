"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { formatStake } from "@/lib/format";

/* â”€â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

interface FairOddsMatch {
  id: number;
  tournament: string;
  surface: string;
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
  value_p1?: number;
  value_p2?: number;
  confidence?: string;
  series_bucket?: string;
  policy_match?: boolean;
  shadow_match?: boolean;
  blocked_reason?: string;
}

interface SignalSummary {
  id: number;
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

interface ApiResponse {
  matches: FairOddsMatch[];
  pinnacle_count: number;
  pinnacle_matched_count: number;
  pinnacle_hint?: string;
  spread_hint?: string;
  policy?: StrictPolicyMeta;
  shadow_profile?: "off" | "volume_275" | "volume_200" | string;
  signals_strict?: SignalSummary[];
  signals_volume?: SignalSummary[];
  error?: string;
}

const SHOW_OU_COLUMNS = false;
const TABLE_COL_COUNT = SHOW_OU_COLUMNS ? 18 : 11; // 10 core + 1 Stats (consolidated)
const TABLE_MIN_WIDTH = SHOW_OU_COLUMNS ? 1550 : 1100;

/* â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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
  if (profile === "volume_275") return "Volume 275";
  return "Volume";
}

function shadowProfileBadge(profile?: string): string {
  if (profile === "volume_200") return "VOL200";
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

function fmtOdds(v: number | undefined): string {
  if (v == null || v <= 0) return "—";
  return v.toFixed(2);
}

function fmtPct(v: number | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function fmtProb(v: number | undefined): string {
  if (v == null || v <= 0) return "—";
  return `${(v * 100).toFixed(0)}%`;
}

function fmtSignedLine(v: number | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(1);
  return `${v >= 0 ? "+" : "−"}${body}`;
}

function formatSignalBet(s: SignalSummary): { matchLabel: string; betLine: string } {
  const player = s.side.startsWith("P1") ? s.player1_name : s.player2_name;
  const odds = s.pinnacle_odds != null ? s.pinnacle_odds.toFixed(2) : "—";
  const units = s.stake_units != null ? s.stake_units : 1;
  const gbp = s.stake_gbp != null ? Math.round(s.stake_gbp) : 100;
  const stakePart = `× ${formatStake(units)}u (or £${gbp})`;

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

function signalTypeCounts(signals?: SignalSummary[]): { total: number; ml: number; spread: number } {
  const total = signals?.length ?? 0;
  const spread = (signals ?? []).filter((s) => (s.bet_type ?? "match") === "spread").length;
  return { total, spread, ml: total - spread };
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

/* â”€â”€â”€ Page Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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

  // Group by tournament
  const grouped = new Map<string, FairOddsMatch[]>();
  for (const m of matches) {
    const key = m.tournament || "Unknown";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(m);
  }

  const now = new Date();
  const todayUTC = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}`;

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

        {/* Pinnacle status bar */}
        {data && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 mb-4 px-1">
            <span>
              Pinnacle snapshot (today UTC):{" "}
              <span className="text-slate-300">{data.pinnacle_count} matches loaded</span>
              {data.pinnacle_count > 0 && (
                <>, <span className="text-slate-300">{data.pinnacle_matched_count} matched</span></>
              )}
            </span>
            {data.pinnacle_hint && (
              <span className="text-amber-400/80">{data.pinnacle_hint}</span>
            )}
            {data.spread_hint && (
              <span className="text-amber-400/80">{data.spread_hint}</span>
            )}
            <span className="text-slate-600">
              Value % = (Pinnacle / Our odds) - 1; positive = value at Pinnacle.
            </span>
            <span className="text-slate-600">
              Spread: line is signed from P1 side (e.g. P1 −1.0 / P2 +1.0). Odds = Pinnacle; edge % = model vs market (positive = value).
            </span>
            {data.policy?.mode === "strict" && (
              <span className="text-emerald-300/90">
                Strict policy ON ({data.policy.production_mode ?? "base"}): {data.policy.allowed_segments.join(", ")}; value &gt;= {data.policy.min_value_pct.toFixed(1)}%; confidence {data.policy.allowed_confidence.join("/")}. Signals: {data.policy.signaled_matches}/{data.policy.eligible_matches} eligible matches.
                {data.policy.production_mode === "overlay" && data.policy.overlay && (
                  <>
                    {" "}
                    Overlay pass: {data.policy.overlay.passed_matches}/{data.policy.overlay.considered_matches} (skip missing={data.policy.overlay.skipped_missing}, n={data.policy.overlay.skipped_min_n}, roi={data.policy.overlay.skipped_min_roi}).
                  </>
                )}
              </span>
            )}
          </div>
        )}

        {/* Signal summary: Strict + Volume_275 */}
        {!loading && !error && data && matches.length > 0 && (
          <div className="mb-6 rounded-xl border border-slate-700/60 bg-slate-900/40 p-4">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">Today&apos;s recommended bets</h2>
            <p className="mb-3 text-[11px] text-slate-500">
              Active shadow profile: <span className="font-semibold text-amber-300">{shadowProfileLabel(data.shadow_profile)}</span>.
              {" "}Signals are mixed below but still counted separately as ML vs spread in tracking and weekly reports.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold text-emerald-400/90 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                  Strict policy
                </h3>
                <p className="mb-2 text-[11px] text-slate-500">
                  ML {signalTypeCounts(data.signals_strict).ml} | Spread {signalTypeCounts(data.signals_strict).spread}
                </p>
                {data.signals_strict?.length ? (
                  <ul className="space-y-1.5">
                    {data.signals_strict.map((s) => {
                      const { matchLabel, betLine } = formatSignalBet(s);
                      return (
                        <li key={s.id} className="text-sm py-2 px-3 rounded-lg bg-slate-800/60 border border-slate-700/40">
                          <div className="text-slate-400 text-[11px] font-medium truncate mb-0.5">{matchLabel}</div>
                          <div className="font-mono text-emerald-300 font-semibold tabular-nums text-[13px]">{betLine}</div>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-500 italic">No strict signals today</p>
                )}
              </div>
              <div>
                <h3 className="text-xs font-semibold text-amber-400/90 uppercase tracking-wider mb-2 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-500" />
                  {shadowProfileLabel(data.shadow_profile)} (shadow)
                </h3>
                <p className="mb-2 text-[11px] text-slate-500">
                  ML {signalTypeCounts(data.signals_volume).ml} | Spread {signalTypeCounts(data.signals_volume).spread}
                </p>
                {data.signals_volume?.length ? (
                  <ul className="space-y-1.5">
                    {data.signals_volume.map((s) => {
                      const { matchLabel, betLine } = formatSignalBet(s);
                      return (
                        <li key={s.id} className="text-sm py-2 px-3 rounded-lg bg-slate-800/60 border border-slate-700/40">
                          <div className="text-slate-400 text-[11px] font-medium truncate mb-0.5">{matchLabel}</div>
                          <div className="font-mono text-amber-300 font-semibold tabular-nums text-[13px]">{betLine}</div>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-500 italic">No {shadowProfileLabel(data.shadow_profile).toLowerCase()} signals today</p>
                )}
              </div>
            </div>
            <p className="mt-3 text-[11px] text-slate-500">
              Stake: value-tiered for match (5–10%→0.5u, 10–15%→1u, 15–20%→1.5u, 20%+→2u); spread 1u flat. 1u = £100.
            </p>
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
                <col style={{ width: 72 }} />
                <col style={{ width: 72 }} />
                <col style={{ width: 56 }} />
                <col style={{ width: 150 }} />
                {SHOW_OU_COLUMNS && <col style={{ width: 220 }} />}
                {SHOW_OU_COLUMNS && <col style={{ width: 220 }} />}
                <col style={{ width: 130 }} />
              </colgroup>
              <thead>
                <tr className="border-b-2 border-slate-700/70 bg-[#0d0f14]/90 text-slate-300 text-[11px] uppercase tracking-wider">
                  <th className="text-left px-3 py-3 font-semibold sticky left-0 bg-[#0d0f14]/95 z-10 border-r border-slate-800/50">Match</th>
                  <th className="text-center px-2 py-3 font-semibold">Surf</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Fair Odds</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Pinnacle</th>
                  <th className="text-center px-2 py-3 font-semibold text-emerald-500/70" colSpan={2}>Value %</th>
                  <th className="text-center px-2 py-3 font-semibold">E[G]</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-400">Spread</th>
                  {SHOW_OU_COLUMNS && <th className="text-left px-2 py-3 font-semibold">O/U Fair</th>}
                  {SHOW_OU_COLUMNS && <th className="text-left px-2 py-3 font-semibold">O/U Pin</th>}
                  <th className={`text-center px-2 py-3 font-medium text-[10px] ${!showStats ? "invisible" : ""}`} title="S% R% T (serve, return, total)">
                    <span className="block">Stats</span>
                    <span className="block text-[9px] text-slate-500 font-normal">S / R / T</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...grouped.entries()].map(([tournament, tMatches]) => (
                  <TournamentGroup
                    key={tournament}
                    tournament={tournament}
                    matches={tMatches}
                    showStats={showStats}
                    colSpan={TABLE_COL_COUNT}
                    shadowProfile={data?.shadow_profile}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-slate-800/50 text-xs text-slate-600 text-center">
          Il Margine &middot; Fair odds generated by Barnett-Clarke + K-M recursion model with serve volatility calibration (σ=0.035).
          <br />
          Pinnacle odds scraped for comparison only. Not financial advice.
        </footer>
      </div>
    </div>
  );
}

/* â”€â”€â”€ Tournament Group â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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
        <MatchRow key={m.id} match={m} showStats={showStats} shadowProfile={shadowProfile} />
      ))}
    </>
  );
}

/* â”€â”€â”€ Match Row â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

function MatchRow({
  match,
  showStats,
  shadowProfile,
}: {
  match: FairOddsMatch;
  showStats: boolean;
  shadowProfile?: string;
}) {
  const m = match;
  const ouLines = SHOW_OU_COLUMNS ? parseOULines(m) : [];
  const hasPinnacle = m.pinnacle_odds1 != null && m.pinnacle_odds1 > 0;

  return (
    <tr className={`border-b border-slate-800/40 hover:bg-slate-800/35 even:bg-slate-900/25 transition-colors ${
      m.confidence === 'none' ? 'opacity-40' : ''
    }`}>
      {/* Match (sticky) */}
      <td className="px-3 py-3 sticky left-0 bg-[#111520]/95 z-10 border-r border-slate-800/50 overflow-hidden">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="block text-slate-100 text-[13px] font-medium leading-snug break-words">
            {m.player1_name || "TBD"}
            <span className="text-slate-600 mx-1.5 font-normal text-xs">vs</span>
            {m.player2_name || "TBD"}
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] text-slate-400 font-mono tabular-nums">{fmtProb(m.p1_win_prob)} - {fmtProb(m.p2_win_prob)}</span>
            <span
              className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[9px] font-semibold tracking-wide ${confidenceMeta(m.confidence).cls}`}
              title={`Confidence: ${m.confidence ?? "n/a"}`}
            >
              {confidenceMeta(m.confidence).label}
            </span>
            {bestValueBadge(m) && (
              <span
                className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-semibold tabular-nums ${valueColor(bestValueBadge(m)!.value)} ${valueBg(bestValueBadge(m)!.value)}`}
                title="Value % = (Pinnacle / Our odds) - 1"
              >
                {bestValueBadge(m)!.side} {fmtPct(bestValueBadge(m)!.value)}
              </span>
            )}
            {m.policy_match && (
              <span className="inline-flex items-center rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-emerald-300">
                STRICT
              </span>
            )}
            {m.shadow_match && !m.policy_match && (
              <span className="inline-flex items-center rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-amber-300">
                {shadowProfileBadge(shadowProfile)}
              </span>
            )}
          </div>
          {m.blocked_reason && !m.policy_match && !m.shadow_match && (
            <div className="text-[10px] text-amber-300/75 leading-snug">
              {m.blocked_reason}
            </div>
          )}
        </div>
      </td>

      {/* Surface */}
      <td className="text-center px-2 py-2.5">
        <SurfaceBadge surface={m.surface} />
      </td>

      {/* Fair Odds */}
      <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds1)}</td>
      <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds2)}</td>

      {/* Pinnacle Odds */}
      <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] text-slate-300">
        {hasPinnacle ? fmtOdds(m.pinnacle_odds1) : <span className="text-slate-600">—</span>}
      </td>
      <td className="text-center px-2 py-3 font-mono tabular-nums text-[13px] text-slate-300">
        {hasPinnacle ? fmtOdds(m.pinnacle_odds2) : <span className="text-slate-600">—</span>}
      </td>

      {/* Value % */}
      <td className="text-center px-2.5 py-3 font-mono tabular-nums text-[13px]">
        <span className={`inline-flex rounded-md px-1.5 py-0.5 ${valueColor(m.value_p1)} ${valueBg(m.value_p1)}`}>
          {m.value_p1 != null ? fmtPct(m.value_p1) : "—"}
        </span>
      </td>
      <td className="text-center px-2.5 py-3 font-mono tabular-nums text-[13px]">
        <span className={`inline-flex rounded-md px-1.5 py-0.5 ${valueColor(m.value_p2)} ${valueBg(m.value_p2)}`}>
          {m.value_p2 != null ? fmtPct(m.value_p2) : "—"}
        </span>
      </td>

      {/* E[G] and O/U */}
      <td className="text-center px-2 py-2.5 font-mono tabular-nums text-sm text-slate-300 overflow-hidden">
        {m.expected_total_games != null ? m.expected_total_games.toFixed(1) : "—"}
      </td>

      {/* Spread (handicap): line, Pinnacle odds, model edge */}
      <td className="px-2 py-2.5 min-w-[140px]">
        {m.spread_line != null ? (
          <div className="text-[11px] font-mono tabular-nums space-y-1">
            <div className="text-slate-500 font-medium text-center">{fmtSignedLine(m.spread_line)}</div>
            <div className="grid grid-cols-[1fr_auto_auto] gap-x-2 gap-y-0.5 items-center">
              <span className="text-slate-400 truncate">P1 {fmtSignedLine(m.spread_line)}</span>
              <span className="text-slate-300">{m.spread_odds1 != null ? m.spread_odds1.toFixed(2) : "—"}</span>
              <span className={`min-w-[3rem] text-right ${valueColor(m.handicap_edge_p1)}`}>
                {m.handicap_edge_p1 != null ? `${m.handicap_edge_p1 > 0 ? "+" : ""}${m.handicap_edge_p1.toFixed(1)}%` : "—"}
              </span>
              <span className="text-slate-400 truncate">P2 {fmtSignedLine(-m.spread_line)}</span>
              <span className="text-slate-300">{m.spread_odds2 != null ? m.spread_odds2.toFixed(2) : "—"}</span>
              <span className={`min-w-[3rem] text-right ${valueColor(m.handicap_edge_p2)}`}>
                {m.handicap_edge_p2 != null ? `${m.handicap_edge_p2 > 0 ? "+" : ""}${m.handicap_edge_p2.toFixed(1)}%` : "—"}
              </span>
            </div>
          </div>
        ) : (
          <span className="text-slate-600 text-xs">—</span>
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

      {/* Stats: single consolidated cell when showStats */}
      <td className={`px-2 py-2.5 font-mono text-[11px] tabular-nums ${showStats ? "text-slate-200" : "text-slate-500 invisible"}`}>
        {showStats && (
          <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            <span className="text-slate-500 text-[10px]">P1</span>
            <span>{m.p1_serve != null ? m.p1_serve.toFixed(1) : "—"} / {m.p1_return != null ? m.p1_return.toFixed(1) : "—"} / {m.p1_total != null ? m.p1_total.toFixed(1) : "—"}</span>
            <span className="text-slate-500 text-[10px]">P2</span>
            <span>{m.p2_serve != null ? m.p2_serve.toFixed(1) : "—"} / {m.p2_return != null ? m.p2_return.toFixed(1) : "—"} / {m.p2_total != null ? m.p2_total.toFixed(1) : "—"}</span>
          </div>
        )}
      </td>
    </tr>
  );
}

const OU_ROW_CLASS =
  "grid grid-cols-[44px_86px_86px] items-center gap-x-2 text-[12px] leading-5 font-mono tabular-nums";

function OverUnderFairCell({ lines }: { lines: OULine[] }) {
  if (lines.length === 0) return <span className="text-slate-500 text-xs">—</span>;

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

  if (lines.length === 0) return <span className="text-slate-500 text-xs">—</span>;

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
