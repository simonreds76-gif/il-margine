"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

/* ─── Types ─────────────────────────────────────────────────────── */

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
  value_p1?: number;
  value_p2?: number;
}

interface ApiResponse {
  matches: FairOddsMatch[];
  pinnacle_count: number;
  pinnacle_matched_count: number;
  pinnacle_hint?: string;
  error?: string;
}

/* ─── Helpers ───────────────────────────────────────────────────── */

interface OULine {
  line: number;
  fairOver: number;
  fairUnder: number;
  pinnacleOver?: number;
  pinnacleUnder?: number;
}

function parseOULines(match: FairOddsMatch): OULine[] {
  const lines: OULine[] = [];
  for (let i = 1; i <= 3; i++) {
    const line = (match as any)[`ou_line_${i}`];
    const over = (match as any)[`ou_over_${i}`];
    const under = (match as any)[`ou_under_${i}`];
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

function valueColor(v: number | undefined): string {
  if (v == null) return "text-slate-600";
  if (v >= 5) return "text-emerald-300 font-bold drop-shadow-[0_0_6px_rgba(52,211,153,0.3)]";
  if (v >= 2) return "text-emerald-400 font-semibold";
  if (v < -10) return "text-red-400 font-bold";
  if (v < -5) return "text-red-400/90 font-medium";
  if (v < -2) return "text-red-400/60";
  return "text-slate-400";
}

function valueBg(v: number | undefined): string {
  if (v == null) return "";
  if (v >= 5) return "bg-emerald-500/10";
  if (v >= 2) return "bg-emerald-500/5";
  if (v < -10) return "bg-red-500/10";
  return "";
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

/* ─── Page Component ────────────────────────────────────────────── */

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
      const res = await fetch("/api/fair-odds");
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
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
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
              {loading ? "Loading…" : "Refresh"}
            </button>
          </div>
        </div>

        {/* Pinnacle status bar */}
        {data && (
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 mb-4 px-1">
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
            <span className="text-slate-600">
              Value % = (Pinnacle / Our odds) − 1; positive = Pinnacle offering more than our fair price (value bet at Pinnacle).
            </span>
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
              Loading fair odds…
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

        {/* Table */}
        {!loading && matches.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-800/70" style={{ scrollbarGutter: "stable" }}>
            <p className="text-[10px] text-slate-600 px-3 py-1.5 border-b border-slate-800/50 bg-slate-900/30">
              Scroll horizontally if needed to see the full O/U column.
            </p>
            <table className="w-full text-sm" style={{ minWidth: showStats ? "1400px" : "1080px" }}>
              <thead>
                <tr className="border-b-2 border-slate-700/60 bg-[#0d0f14] text-slate-400 text-[11px] uppercase tracking-wider">
                  <th className="text-left px-3 py-3 font-semibold sticky left-0 bg-[#0d0f14] z-10 border-r border-slate-800/40">Match</th>
                  <th className="text-center px-2 py-3 font-semibold w-[50px]">Surf</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Fair Odds</th>
                  <th className="text-center px-2 py-3 font-semibold text-slate-300" colSpan={2}>Pinnacle</th>
                  <th className="text-center px-2 py-3 font-semibold text-emerald-500/70" colSpan={2}>Value %</th>
                  {showStats && (
                    <>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P1 S%</th>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P1 R%</th>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P1 T</th>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P2 S%</th>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P2 R%</th>
                      <th className="text-center px-1.5 py-3 font-medium text-[10px]">P2 T</th>
                    </>
                  )}
                  <th className="text-center px-2 py-3 font-semibold">E[G]</th>
                  <th className="text-left px-2 py-3 font-semibold min-w-[180px] w-[17%]">O/U Fair</th>
                  <th className="text-left px-2 py-3 font-semibold min-w-[140px]">O/U Pin</th>
                </tr>
              </thead>
              <tbody>
                {[...grouped.entries()].map(([tournament, tMatches]) => (
                  <TournamentGroup
                    key={tournament}
                    tournament={tournament}
                    matches={tMatches}
                    showStats={showStats}
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

/* ─── Tournament Group ──────────────────────────────────────────── */

function TournamentGroup({
  tournament,
  matches,
  showStats,
}: {
  tournament: string;
  matches: FairOddsMatch[];
  showStats: boolean;
}) {
  return (
    <>
      <tr className="bg-[#0c0e14]">
        <td
          colSpan={showStats ? 17 : 11}
          className="px-3 py-2.5 text-[11px] font-semibold text-slate-300 uppercase tracking-widest border-b-2 border-slate-700/50 border-t border-slate-700/30"
        >
          {tournament}
        </td>
      </tr>
      {matches.map((m) => (
        <MatchRow key={m.id} match={m} showStats={showStats} />
      ))}
    </>
  );
}

/* ─── Match Row ─────────────────────────────────────────────────── */

function MatchRow({ match, showStats }: { match: FairOddsMatch; showStats: boolean }) {
  const m = match;
  const ouLines = parseOULines(m);
  const hasPinnacle = m.pinnacle_odds1 != null && m.pinnacle_odds1 > 0;

  return (
    <tr className="border-b border-slate-800/30 hover:bg-slate-800/25 even:bg-slate-900/20 transition-colors">
      {/* Match (sticky) */}
      <td className="px-3 py-3 sticky left-0 bg-[#0f1117] z-10 border-r border-slate-800/40">
        <div className="flex flex-col gap-0.5">
          <span className="text-slate-100 text-[13px] font-medium leading-tight tracking-tight">
            {m.player1_name || "TBD"}
            <span className="text-slate-600 mx-1.5 font-normal text-xs">vs</span>
            {m.player2_name || "TBD"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono">
            {fmtProb(m.p1_win_prob)} – {fmtProb(m.p2_win_prob)}
          </span>
        </div>
      </td>

      {/* Surface */}
      <td className="text-center px-2 py-2.5">
        <SurfaceBadge surface={m.surface} />
      </td>

      {/* Fair Odds */}
      <td className="text-center px-2 py-3 font-mono text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds1)}</td>
      <td className="text-center px-2 py-3 font-mono text-[13px] font-semibold text-slate-100">{fmtOdds(m.odds2)}</td>

      {/* Pinnacle Odds */}
      <td className="text-center px-2 py-3 font-mono text-[13px] text-slate-300">
        {hasPinnacle ? fmtOdds(m.pinnacle_odds1) : <span className="text-slate-600">—</span>}
      </td>
      <td className="text-center px-2 py-3 font-mono text-[13px] text-slate-300">
        {hasPinnacle ? fmtOdds(m.pinnacle_odds2) : <span className="text-slate-600">—</span>}
      </td>

      {/* Value % */}
      <td className={`text-center px-2.5 py-3 font-mono text-[13px] ${valueColor(m.value_p1)} ${valueBg(m.value_p1)}`}>
        {m.value_p1 != null ? fmtPct(m.value_p1) : "—"}
      </td>
      <td className={`text-center px-2.5 py-3 font-mono text-[13px] ${valueColor(m.value_p2)} ${valueBg(m.value_p2)}`}>
        {m.value_p2 != null ? fmtPct(m.value_p2) : "—"}
      </td>

      {/* Stats (togglable) */}
      {showStats && (
        <>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p1_serve?.toFixed(1) ?? "—"}</td>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p1_return?.toFixed(1) ?? "—"}</td>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p1_total?.toFixed(1) ?? "—"}</td>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p2_serve?.toFixed(1) ?? "—"}</td>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p2_return?.toFixed(1) ?? "—"}</td>
          <td className="text-center px-1.5 py-2.5 font-mono text-xs text-slate-500">{m.p2_total?.toFixed(1) ?? "—"}</td>
        </>
      )}

      {/* Expected Total Games */}
      <td className="text-center px-2 py-2.5 font-mono text-sm text-slate-400">
        {m.expected_total_games != null ? m.expected_total_games.toFixed(1) : "—"}
      </td>

      {/* O/U Fair */}
      <td className="px-2 py-2 min-w-[180px] w-[17%]">
        <OverUnderFairCell lines={ouLines} />
      </td>

      {/* O/U Pinnacle */}
      <td className="px-2 py-2 min-w-[140px]">
        <OverUnderPinCell match={m} lines={ouLines} />
      </td>
    </tr>
  );
}

/* ─── O/U Cells ─────────────────────────────────────────────────── */

function OverUnderFairCell({ lines }: { lines: OULine[] }) {
  if (lines.length === 0) return <span className="text-slate-600 text-xs">—</span>;

  return (
    <div className="space-y-1" style={{ overflow: "visible", whiteSpace: "nowrap" }}>
      {lines.map((ou) => (
        <div key={ou.line} className="grid gap-1.5 text-xs" style={{ gridTemplateColumns: "32px 1fr 1fr" }}>
          <span className="text-slate-500 font-mono">{ou.line}</span>
          <span className="text-slate-300 font-mono">
            <span className="text-slate-600 mr-0.5">O</span>
            {ou.fairOver.toFixed(2)}
          </span>
          <span className="text-slate-300 font-mono">
            <span className="text-slate-600 mr-0.5">U</span>
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

  if (pinLine == null || pinOver == null || pinUnder == null) {
    return <span className="text-slate-600 text-xs">—</span>;
  }

  const fairMatch = lines.find((l) => l.line === pinLine);
  const overValue = fairMatch ? ((pinOver / fairMatch.fairOver - 1) * 100) : null;
  const underValue = fairMatch ? ((pinUnder / fairMatch.fairUnder - 1) * 100) : null;

  return (
    <div style={{ overflow: "visible", whiteSpace: "nowrap" }}>
      <div className="grid gap-1.5 text-xs" style={{ gridTemplateColumns: "32px 1fr 1fr" }}>
        <span className="text-slate-500 font-mono">{pinLine}</span>
        <span className="font-mono">
          <span className="text-slate-600 mr-0.5">O</span>
          <span className="text-slate-400">{pinOver.toFixed(2)}</span>
          {overValue != null && (
            <span className={`ml-1 text-[10px] ${valueColor(overValue)}`}>
              {overValue > 0 ? "+" : ""}{overValue.toFixed(1)}%
            </span>
          )}
        </span>
        <span className="font-mono">
          <span className="text-slate-600 mr-0.5">U</span>
          <span className="text-slate-400">{pinUnder.toFixed(2)}</span>
          {underValue != null && (
            <span className={`ml-1 text-[10px] ${valueColor(underValue)}`}>
              {underValue > 0 ? "+" : ""}{underValue.toFixed(1)}%
            </span>
          )}
        </span>
      </div>
    </div>
  );
}
