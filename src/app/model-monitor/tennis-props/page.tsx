import { promises as fs } from "fs";
import path from "path";
import { Fragment } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  HeroCard,
  SectionCard,
  StatCard,
  StatusPill,
  EmptyState,
  cn,
} from "../shared";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;
type ProjectionSortKey = "schedule" | "aces" | "dfs" | "match_tb" | "first_tb" | "breaks";
type SearchParamsInput = Promise<Record<string, string | string[] | undefined>>;
type TournamentRoundLog = {
  date?: string;
  round?: string;
  opponent?: string;
  result?: string;
  aces?: string;
  dfs?: string;
  breaks_for?: string;
  broken?: string;
  total_breaks?: string;
  first_set_tiebreak?: string;
  match_tiebreak?: string;
  svpt?: string;
};

const ROOT = process.cwd();
const PROPS_DIR = path.join(ROOT, "data", "tennis-props");
const BOARD_PATH = path.join(PROPS_DIR, "player-props-board.csv");
const BASELINE_PATH = path.join(PROPS_DIR, "player-props-baseline.csv");
const FACTORS_PATH = path.join(PROPS_DIR, "slam-venue-factors.csv");
const INBOX_DIR = path.join(PROPS_DIR, "inbox");
const SHADOW_DIR = path.join(PROPS_DIR, "shadow");
const SHADOW_SIGNALS_PATH = path.join(SHADOW_DIR, "aces-dfs-shadow-signals.csv");
const SHADOW_PERFORMANCE_PATH = path.join(SHADOW_DIR, "aces-dfs-shadow-performance.txt");

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }
    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i++;
      row.push(field);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      field = "";
      continue;
    }
    field += ch;
  }
  if (field || row.length) {
    row.push(field);
    if (row.some((value) => value.trim())) rows.push(row);
  }
  if (rows.length < 2) return [];
  const headers = rows[0].map((header) => header.trim());
  return rows.slice(1).map((values) => {
    const parsed: CsvRow = {};
    headers.forEach((header, index) => {
      parsed[header] = (values[index] ?? "").trim();
    });
    return parsed;
  });
}

async function readCsv(filePath: string): Promise<CsvRow[]> {
  try {
    return parseCsv(await fs.readFile(filePath, "utf8"));
  } catch {
    return [];
  }
}

async function fileStamp(filePath: string): Promise<string> {
  try {
    const stat = await fs.stat(filePath);
    return stat.mtime.toLocaleString("en-GB", { timeZone: "Europe/London" });
  } catch {
    return "missing";
  }
}

async function fileAgeHours(filePath: string): Promise<number | null> {
  try {
    const stat = await fs.stat(filePath);
    return (Date.now() - stat.mtimeMs) / 36e5;
  } catch {
    return null;
  }
}

async function latestCsv(prefix: string): Promise<string | null> {
  try {
    const files = await fs.readdir(prefix === "comparison" ? PROPS_DIR : INBOX_DIR);
    const dir = prefix === "comparison" ? PROPS_DIR : INBOX_DIR;
    const matches = files
      .filter((file) => file.startsWith(`${prefix}-`) && file.endsWith(".csv"))
      .map((file) => path.join(dir, file));
    if (!matches.length) return null;
    const stamped = await Promise.all(
      matches.map(async (file) => ({
        file,
        mtime: (await fs.stat(file)).mtimeMs,
      })),
    );
    return stamped.sort((a, b) => b.mtime - a.mtime)[0]?.file ?? null;
  } catch {
    return null;
  }
}

function n(value: string | undefined): number {
  const parsed = Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function fmt(value: string | number | undefined, digits = 1): string {
  const parsed = typeof value === "number" ? value : Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "-";
}

function pctText(value: string | number | undefined, digits = 1): string {
  const parsed = typeof value === "number" ? value : Number.parseFloat(value ?? "");
  return Number.isFinite(parsed) ? `${parsed.toFixed(digits)}%` : "-";
}

function factorMove(value: string | undefined, digits = 1): string {
  const parsed = Number.parseFloat(value ?? "");
  if (!Number.isFinite(parsed) || parsed <= 0) return "-";
  const pct = (parsed - 1) * 100;
  if (Math.abs(pct) < 0.05) return "flat";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(digits)}%`;
}

function factorProductMove(first: string | undefined, second: string | undefined, digits = 1): string {
  const a = Number.parseFloat(first ?? "");
  const b = Number.parseFloat(second ?? "");
  const product = (Number.isFinite(a) && a > 0 ? a : 1) * (Number.isFinite(b) && b > 0 ? b : 1);
  return factorMove(String(product), digits);
}

function confidenceTone(value: string | undefined): string {
  if (value === "HIGH") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (value === "MED") return "border-amber-500/25 bg-amber-500/10 text-amber-300";
  return "border-slate-700/70 bg-slate-800/60 text-slate-400";
}

function recTone(value: string | undefined): string {
  if (value === "OVER" || value === "UNDER") return "border-cyan-500/25 bg-cyan-500/10 text-cyan-200";
  return "border-slate-700/70 bg-slate-800/60 text-slate-500";
}

function maxValue(row: CsvRow): number {
  if (row.line_quality && row.line_quality !== "complete") return 0;
  return Math.max(n(row.value_over_pct), n(row.value_under_pct));
}

function boardSort(a: CsvRow, b: CsvRow): number {
  const aConf = a.ace_confidence === "HIGH" ? 2 : a.ace_confidence === "MED" ? 1 : 0;
  const bConf = b.ace_confidence === "HIGH" ? 2 : b.ace_confidence === "MED" ? 1 : 0;
  return bConf - aConf || n(b.projected_aces) - n(a.projected_aces);
}

function comparisonSort(a: CsvRow, b: CsvRow): number {
  const aRec = a.recommended_side ? 1 : 0;
  const bRec = b.recommended_side ? 1 : 0;
  return bRec - aRec || maxValue(b) - maxValue(a);
}

function shadowSort(a: CsvRow, b: CsvRow): number {
  const statusRank = (row: CsvRow) => row.settlement_status === "pending" ? 0 : row.settlement_status === "settled" ? 1 : 2;
  return statusRank(a) - statusRank(b) || (b.date || "").localeCompare(a.date || "") || n(b.value_pct) - n(a.value_pct);
}

function shadowStats(rows: CsvRow[]): { settled: number; pending: number; voided: number; pnl: number; roi: number } {
  const settledRows = rows.filter((row) => row.settlement_status === "settled");
  const pnl = settledRows.reduce((sum, row) => sum + n(row.pnl), 0);
  return {
    settled: settledRows.length,
    pending: rows.filter((row) => row.settlement_status === "pending").length,
    voided: rows.filter((row) => row.settlement_status === "void").length,
    pnl,
    roi: settledRows.length ? (pnl / settledRows.length) * 100 : 0,
  };
}

function countBy(rows: CsvRow[], field: string, value: string): number {
  return rows.filter((row) => row[field] === value).length;
}

function latestDate(rows: CsvRow[]): string {
  return [...new Set(rows.map((row) => row.date).filter(Boolean))].sort().at(-1) ?? "-";
}

function dateLabel(value: string): string {
  if (!value) return "Date missing";
  const parsed = new Date(`${value}T12:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(parsed);
}

function groupRowsByDate(rows: CsvRow[]): { date: string; rows: CsvRow[] }[] {
  const grouped = new Map<string, CsvRow[]>();
  for (const row of rows) {
    const key = row.date || "unscheduled";
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }
  return [...grouped.entries()]
    .sort(([a], [b]) => {
      if (a === "unscheduled") return 1;
      if (b === "unscheduled") return -1;
      return a.localeCompare(b);
    })
    .map(([date, groupedRows]) => ({ date, rows: groupedRows }));
}

function validProjectionSort(value: string | string[] | undefined): ProjectionSortKey {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === "aces" || raw === "dfs" || raw === "match_tb" || raw === "first_tb" || raw === "breaks") return raw;
  return "schedule";
}

function projectionSortValue(rows: CsvRow[], sortKey: ProjectionSortKey): number {
  if (sortKey === "aces") return Math.max(...rows.map((row) => n(row.projected_aces)));
  if (sortKey === "dfs") return Math.max(...rows.map((row) => n(row.projected_dfs)));
  if (sortKey === "match_tb") return Math.max(...rows.map((row) => n(row.match_tiebreak_pct)));
  if (sortKey === "first_tb") return Math.max(...rows.map((row) => n(row.first_set_tiebreak_pct)));
  if (sortKey === "breaks") return Math.max(...rows.map((row) => n(row.projected_total_breaks)));
  return 0;
}

function matchKey(row: CsvRow): string {
  const players = [row.player || "", row.opponent || ""].sort((a, b) => a.localeCompare(b)).join(" v ");
  return [row.date || "", row.tour || "", row.tournament || "", players].join("|");
}

function fixtureName(rows: CsvRow[]): string {
  const first = rows[0] ?? {};
  return `${first.player || "-"} vs ${first.opponent || "-"}`;
}

function groupRowsByDateAndMatch(rows: CsvRow[], sortKey: ProjectionSortKey): { date: string; matches: { key: string; rows: CsvRow[] }[] }[] {
  return groupRowsByDate(rows).map((dateGroup) => {
    const matchMap = new Map<string, CsvRow[]>();
    for (const row of dateGroup.rows) {
      const key = matchKey(row);
      matchMap.set(key, [...(matchMap.get(key) ?? []), row]);
    }
    const matches = [...matchMap.entries()].map(([key, matchRows]) => ({
      key,
      rows: [...matchRows].sort((a, b) => (a.player || "").localeCompare(b.player || "")),
    }));
    matches.sort((a, b) => {
      if (sortKey !== "schedule") {
        return projectionSortValue(b.rows, sortKey) - projectionSortValue(a.rows, sortKey)
          || fixtureName(a.rows).localeCompare(fixtureName(b.rows));
      }
      return fixtureName(a.rows).localeCompare(fixtureName(b.rows));
    });
    return { date: dateGroup.date, matches };
  });
}

function parseTournamentRoundLog(value: string | undefined): TournamentRoundLog[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function MiniBadge({ label, tone }: { label: string; tone: string }) {
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]", tone)}>
      {label}
    </span>
  );
}

function factorTone(value: string | undefined): string {
  const parsed = Number.parseFloat(value ?? "");
  if (!Number.isFinite(parsed)) return "border-slate-700 bg-slate-900 text-slate-500";
  if (parsed >= 1.03) return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (parsed <= 0.97) return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  return "border-slate-700/70 bg-slate-800/60 text-slate-400";
}

function factorProductTone(first: string | undefined, second: string | undefined): string {
  const a = Number.parseFloat(first ?? "");
  const b = Number.parseFloat(second ?? "");
  const product = (Number.isFinite(a) && a > 0 ? a : 1) * (Number.isFinite(b) && b > 0 ? b : 1);
  return factorTone(String(product));
}

function NoteBadges({ value }: { value: string }) {
  const notes = value
    .split("|")
    .map((note) => note.trim())
    .filter(Boolean)
    .slice(0, 5);
  if (!notes.length) return <span className="text-xs text-slate-600">clear</span>;
  return (
    <div className="flex max-w-[300px] flex-wrap gap-1.5">
      {notes.map((note) => (
        <span key={note} className="rounded-full border border-slate-800 bg-slate-950/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          {note.replaceAll("_", " ")}
        </span>
      ))}
    </div>
  );
}

function TournamentRoundDetails({ row }: { row: CsvRow }) {
  const logs = parseTournamentRoundLog(row.tournament_round_log);
  return (
    <details className="group mt-1 rounded-xl border border-slate-800/80 bg-slate-950/50 px-2 py-1">
      <summary className="cursor-pointer list-none text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 transition group-open:text-emerald-300">
        Round aces / DFs / breaks / TB
      </summary>
      {logs.length ? (
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-[520px] text-[11px]">
            <thead className="text-left uppercase tracking-[0.12em] text-slate-600">
              <tr>
                <th className="py-1 pr-3 font-semibold">Round</th>
                <th className="py-1 pr-3 font-semibold">Opponent</th>
                <th className="py-1 pr-3 font-semibold">Aces</th>
                <th className="py-1 pr-3 font-semibold">DFs</th>
                <th className="py-1 pr-3 font-semibold">Brk+</th>
                <th className="py-1 pr-3 font-semibold">Brk-</th>
                <th className="py-1 pr-3 font-semibold">Tot brk</th>
                <th className="py-1 pr-3 font-semibold">1st TB</th>
                <th className="py-1 pr-3 font-semibold">Match TB</th>
                <th className="py-1 pr-3 font-semibold">Result</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => (
                <tr key={`${log.date}-${log.round}-${log.opponent}-${index}`} className="border-t border-slate-900">
                  <td className="py-1 pr-3 font-mono text-slate-300">{log.round || "-"}</td>
                  <td className="py-1 pr-3 text-slate-400">{log.opponent || "-"}</td>
                  <td className="py-1 pr-3 font-mono text-emerald-300">{log.aces || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-rose-300">{log.dfs || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-cyan-300">{log.breaks_for || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-amber-300">{log.broken || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-slate-300">{log.total_breaks || "0"}</td>
                  <td className="py-1 pr-3 font-mono text-violet-300">{log.first_set_tiebreak === "1" ? "Y" : "N"}</td>
                  <td className="py-1 pr-3 font-mono text-violet-300">{log.match_tiebreak === "1" ? "Y" : "N"}</td>
                  <td className="py-1 pr-3 font-mono text-slate-500">{log.result || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-2 text-[11px] leading-relaxed text-slate-600">
          No completed same-tournament stat row found yet.
        </div>
      )}
    </details>
  );
}

function TieBreakCell({ row }: { row: CsvRow }) {
  const items = [
    {
      label: "1st set",
      probability: row.first_set_tiebreak_pct,
      fairOdds: row.first_set_tiebreak_fair_yes,
      venueActual: row.venue_first_set_tiebreak_actual_pct,
      liveActual: row.current_env_first_set_tiebreak_actual_pct,
      accent: "text-violet-200",
      border: "border-violet-500/20 bg-violet-500/10",
    },
    {
      label: "Any set",
      probability: row.match_tiebreak_pct,
      fairOdds: row.match_tiebreak_fair_yes,
      venueActual: row.venue_match_tiebreak_actual_pct,
      liveActual: row.current_env_match_tiebreak_actual_pct,
      accent: "text-fuchsia-200",
      border: "border-fuchsia-500/20 bg-fuchsia-500/10",
    },
  ];

  return (
    <div className="min-w-[176px] space-y-1.5">
      {items.map((item) => (
        <div key={item.label} className={cn("rounded-xl border px-2.5 py-2", item.border)}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[10px] font-black uppercase tracking-[0.13em] text-slate-500">{item.label}</span>
            <span className={cn("font-mono text-lg font-black leading-none", item.accent)}>
              {fmt(item.fairOdds, 2)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between gap-2 border-t border-white/5 pt-1 text-[10px] uppercase tracking-[0.11em] text-slate-500">
            <span>YES prob</span>
            <span className="font-mono text-slate-300">{fmt(item.probability, 1)}%</span>
          </div>
          <div className="mt-1 grid grid-cols-2 gap-1 text-[10px] uppercase tracking-[0.09em] text-slate-600">
            <span>hist {pctText(item.venueActual, 1)}</span>
            <span>live {pctText(item.liveActual, 1)}</span>
          </div>
        </div>
      ))}
      <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-amber-300">
        Research only · no odds feed · not a pick
      </div>
      <div className="px-1 text-[10px] leading-snug text-slate-600">
        Any set = tie-break anywhere in the match.
      </div>
    </div>
  );
}

function ProjectionSortControls({ active }: { active: ProjectionSortKey }) {
  const options: { key: ProjectionSortKey; label: string }[] = [
    { key: "schedule", label: "Schedule" },
    { key: "match_tb", label: "Highest match TB" },
    { key: "first_tb", label: "Highest 1st-set TB" },
    { key: "aces", label: "Highest aces" },
    { key: "dfs", label: "Highest DFs" },
    { key: "breaks", label: "Highest breaks" },
  ];
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {options.map((option) => (
        <Link
          key={option.key}
          href={`/model-monitor/tennis-props?propsSort=${option.key}`}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs font-bold uppercase tracking-[0.12em] transition",
            active === option.key
              ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-200"
              : "border-slate-800 bg-slate-950/70 text-slate-400 hover:border-slate-600 hover:text-slate-200",
          )}
        >
          {option.label}
        </Link>
      ))}
    </div>
  );
}

function MetricTile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
      <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={cn("mt-1 font-mono text-2xl font-black leading-none", tone)}>{value}</div>
      {sub ? <div className="mt-1 text-[11px] leading-snug text-slate-500">{sub}</div> : null}
    </div>
  );
}

function FactorCluster({ row }: { row: CsvRow }) {
  return (
    <div className="grid gap-2 text-[11px] sm:grid-cols-2">
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-emerald-300">Aces</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`venue ${factorMove(row.venue_ace_factor)}`} tone={factorTone(row.venue_ace_factor)} />
          <MiniBadge label={`live ${factorMove(row.current_env_ace_factor)}`} tone={factorTone(row.current_env_ace_factor)} />
          <MiniBadge label={`net ${factorProductMove(row.venue_ace_factor, row.current_env_ace_factor)}`} tone={factorProductTone(row.venue_ace_factor, row.current_env_ace_factor)} />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-rose-300">Double faults</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`venue ${factorMove(row.venue_df_factor)}`} tone={factorTone(row.venue_df_factor)} />
          <MiniBadge label={`live ${factorMove(row.current_env_df_factor)}`} tone={factorTone(row.current_env_df_factor)} />
          <MiniBadge label={`net ${factorProductMove(row.venue_df_factor, row.current_env_df_factor)}`} tone={factorProductTone(row.venue_df_factor, row.current_env_df_factor)} />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-cyan-300">Breaks</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`live ${factorMove(row.current_env_break_factor)}`} tone={factorTone(row.current_env_break_factor)} />
          <MiniBadge label={`for +${row.same_tournament_breaks_for || "0"}`} tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
          <MiniBadge label={`against -${row.same_tournament_broken || "0"}`} tone="border-amber-500/25 bg-amber-500/10 text-amber-200" />
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
        <div className="mb-1 font-black uppercase tracking-[0.14em] text-violet-300">Tie-breaks</div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={`1st venue ${factorMove(row.venue_first_set_tiebreak_factor)}`} tone={factorTone(row.venue_first_set_tiebreak_factor)} />
          <MiniBadge label={`1st live ${factorMove(row.current_env_first_set_tiebreak_factor)}`} tone={factorTone(row.current_env_first_set_tiebreak_factor)} />
          <MiniBadge label={`match venue ${factorMove(row.venue_match_tiebreak_factor)}`} tone={factorTone(row.venue_match_tiebreak_factor)} />
          <MiniBadge label={`match live ${factorMove(row.current_env_match_tiebreak_factor)}`} tone={factorTone(row.current_env_match_tiebreak_factor)} />
        </div>
      </div>
    </div>
  );
}

function ProjectionPlayerCard({ row }: { row: CsvRow }) {
  return (
    <article className="rounded-3xl border border-slate-800/80 bg-[linear-gradient(145deg,rgba(15,23,42,0.92),rgba(2,6,23,0.92))] p-4 shadow-2xl shadow-black/20">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <MiniBadge label={row.tour || "-"} tone={row.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
            <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{row.tournament || "Tennis"} {row.round ? `- ${row.round}` : ""}</span>
          </div>
          <h4 className="mt-2 text-xl font-black tracking-tight text-slate-50">{row.player || "-"}</h4>
          <p className="text-sm text-slate-400">vs {row.opponent || "-"}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <MiniBadge label={row.ace_confidence || "LOW"} tone={confidenceTone(row.ace_confidence)} />
          <MiniBadge label={row.df_confidence || "LOW"} tone={confidenceTone(row.df_confidence)} />
          <MiniBadge label={row.tiebreak_confidence || "LOW"} tone={confidenceTone(row.tiebreak_confidence)} />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricTile label="Aces projection" value={fmt(row.projected_aces, 1)} sub={`sample ${row.player_surface_matches || "0"}m / ${row.player_surface_svpt_sample || "0"} svpt`} tone="text-emerald-300" />
        <MetricTile label="Double faults" value={fmt(row.projected_dfs, 1)} sub={`same event ${row.same_tournament_matches || "0"}m`} tone="text-rose-300" />
        <MetricTile label="Breaks total" value={fmt(row.projected_total_breaks, 1)} sub={`for +${fmt(row.projected_breaks_for, 1)} / against -${fmt(row.projected_broken, 1)}`} tone="text-cyan-300" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[220px_1fr]">
        <TieBreakCell row={row} />
        <div className="space-y-3">
          <details className="group rounded-2xl border border-slate-800/80 bg-slate-950/55 p-3">
            <summary className="cursor-pointer list-none text-xs font-black uppercase tracking-[0.14em] text-slate-400 transition group-open:text-emerald-300">
              Model inputs, venue factors, notes
            </summary>
            <div className="mt-3 space-y-3">
              <div className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
                  <div className="font-mono text-emerald-300">expected games {fmt(row.expected_match_games, 1)}</div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.1em] text-slate-600">{row.expected_match_games_source || "fallback"}{row.expected_match_games_confidence ? ` / ${row.expected_match_games_confidence}` : ""}</div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-2">
                  <div className="font-mono text-slate-300">current event {row.current_env_matches || "0"} matches</div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.1em] text-slate-600">live weight {fmt(row.current_env_weight, 2)}</div>
                </div>
              </div>
              <FactorCluster row={row} />
              <NoteBadges value={[row.notes, row.break_notes, row.tiebreak_notes].filter(Boolean).join("|")} />
            </div>
          </details>
          <TournamentRoundDetails row={row} />
        </div>
      </div>
    </article>
  );
}

function ProjectionTable({ rows, sortKey }: { rows: CsvRow[]; sortKey: ProjectionSortKey }) {
  if (!rows.length) return <EmptyState message="No aces/DF projection board found. Run python scripts/run-tennis-props-daily.py after OnCourt extract." />;
  const groupedRows = groupRowsByDateAndMatch(rows, sortKey);
  return (
    <div className="space-y-4">
      <ProjectionSortControls active={sortKey} />
      {groupedRows.map((group) => (
        <section key={group.date} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">{dateLabel(group.date)}</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.matches.length} matches / {group.matches.reduce((sum, match) => sum + match.rows.length, 0)} player rows</span>
          </div>
          {group.matches.map((match) => {
            const first = match.rows[0] ?? {};
            const matchTbFair = Math.min(...match.rows.map((row) => n(row.match_tiebreak_fair_yes)).filter((value) => value > 0));
            const firstSetFair = Math.min(...match.rows.map((row) => n(row.first_set_tiebreak_fair_yes)).filter((value) => value > 0));
            return (
              <details key={`${group.date}-${match.key}`} open className="group rounded-[2rem] border border-slate-800/80 bg-slate-950/55 shadow-2xl shadow-black/20">
                <summary className="cursor-pointer list-none p-4 sm:p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <MiniBadge label={first.tour || "-"} tone={first.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{first.tournament || "Tennis"} {first.round ? `- ${first.round}` : ""}</span>
                      </div>
                      <h3 className="text-2xl font-black tracking-tight text-slate-50">{fixtureName(match.rows)}</h3>
                      <p className="mt-1 text-sm text-slate-500">Click to collapse. Aces, double faults, breaks and tie-break pricing stay grouped by match.</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[470px]">
                      <MetricTile label="Any-set TB odds" value={Number.isFinite(matchTbFair) ? matchTbFair.toFixed(2) : "-"} sub={`prob ${fmt(projectionSortValue(match.rows, "match_tb"), 1)}%`} tone="text-fuchsia-200" />
                      <MetricTile label="1st-set TB odds" value={Number.isFinite(firstSetFair) ? firstSetFair.toFixed(2) : "-"} sub={`prob ${fmt(projectionSortValue(match.rows, "first_tb"), 1)}%`} tone="text-violet-200" />
                      <MetricTile label="Max aces" value={fmt(projectionSortValue(match.rows, "aces"), 1)} tone="text-emerald-300" />
                      <MetricTile label="Max DFs" value={fmt(projectionSortValue(match.rows, "dfs"), 1)} tone="text-rose-300" />
                    </div>
                  </div>
                </summary>
                <div className="grid gap-4 border-t border-slate-800/80 p-4 sm:p-5 xl:grid-cols-2">
                  {match.rows.map((row, index) => (
                    <ProjectionPlayerCard key={`${group.date}-${row.tour}-${row.player}-${row.opponent}-${index}`} row={row} />
                  ))}
                </div>
              </details>
            );
          })}
        </section>
      ))}
    </div>
  );
}

function resultTone(value: string | undefined): string {
  if (value === "win") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (value === "loss") return "border-rose-500/25 bg-rose-500/10 text-rose-300";
  if (value === "push" || value === "void") return "border-slate-600/70 bg-slate-800/60 text-slate-400";
  return "border-amber-500/25 bg-amber-500/10 text-amber-300";
}

function ShadowEvidenceTable({ rows }: { rows: CsvRow[] }) {
  if (!rows.length) {
    return <EmptyState message="No shadow signals yet. Add Bet365 aces/DF lines, run the comparison, then run python scripts/tennis-props-shadow-tracker.py." />;
  }
  const groupedRows = groupRowsByDate(rows.slice(0, 80));
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-3 py-3 font-semibold">Status</th>
            <th className="px-3 py-3 font-semibold">Player</th>
            <th className="px-3 py-3 font-semibold">Market</th>
            <th className="px-3 py-3 font-semibold">Line</th>
            <th className="px-3 py-3 font-semibold">Side</th>
            <th className="px-3 py-3 font-semibold">Odds</th>
            <th className="px-3 py-3 font-semibold">Value</th>
            <th className="px-3 py-3 font-semibold">Actual</th>
            <th className="px-3 py-3 font-semibold">PnL</th>
            <th className="px-3 py-3 font-semibold">Conf</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map((group) => (
            <Fragment key={group.date}>
              <tr className="border-y border-slate-800 bg-slate-950/80">
                <td colSpan={10} className="px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase tracking-[0.18em] text-amber-300">{dateLabel(group.date)}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.rows.length} shadow rows</span>
                  </div>
                </td>
              </tr>
              {group.rows.map((row, index) => (
                <tr key={`${row.signal_id}-${index}`} className="border-b border-slate-900/80 text-slate-300">
                  <td className="px-3 py-3"><MiniBadge label={row.result || row.settlement_status || "pending"} tone={resultTone(row.result || row.settlement_status)} /></td>
                  <td className="px-3 py-3">
                    <div className="font-semibold text-slate-100">{row.player}</div>
                    <div className="text-xs text-slate-500">vs {row.opponent}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-300">{row.market}</td>
                  <td className="px-3 py-3 font-mono text-slate-100">{fmt(row.line, 1)}</td>
                  <td className="px-3 py-3"><MiniBadge label={row.side || "-"} tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" /></td>
                  <td className="px-3 py-3 font-mono text-slate-300">{fmt(row.selected_odds, 2)}</td>
                  <td className="px-3 py-3 font-mono text-emerald-300">{fmt(row.value_pct, 1)}%</td>
                  <td className="px-3 py-3 font-mono text-slate-300">{row.actual || "-"}</td>
                  <td className={cn("px-3 py-3 font-mono", n(row.pnl) > 0 ? "text-emerald-300" : n(row.pnl) < 0 ? "text-rose-300" : "text-slate-500")}>{row.pnl ? `${n(row.pnl).toFixed(2)}u` : "-"}</td>
                  <td className="px-3 py-3"><MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} /></td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function comparisonMatchKey(row: CsvRow): string {
  const players = [row.player || "", row.opponent || ""].sort((a, b) => a.localeCompare(b)).join(" v ");
  return [row.date || "", row.tour || "", row.tournament || "", players].join("|");
}

function groupComparisonByMatch(rows: CsvRow[]): { date: string; matches: { key: string; rows: CsvRow[] }[] }[] {
  return groupRowsByDate(rows).map((dateGroup) => {
    const matchMap = new Map<string, CsvRow[]>();
    for (const row of dateGroup.rows) {
      const key = comparisonMatchKey(row);
      matchMap.set(key, [...(matchMap.get(key) ?? []), row]);
    }
    const matches = [...matchMap.entries()].map(([key, matchRows]) => ({
      key,
      rows: [...matchRows].sort((a, b) => maxValue(b) - maxValue(a) || (a.market || "").localeCompare(b.market || "")),
    }));
    matches.sort((a, b) => Math.max(...b.rows.map(maxValue)) - Math.max(...a.rows.map(maxValue)) || fixtureName(a.rows).localeCompare(fixtureName(b.rows)));
    return { date: dateGroup.date, matches };
  });
}

function ComparisonLineCard({ row }: { row: CsvRow }) {
  const trustedLine = row.matched_board === "yes" && row.line_quality === "complete";
  const bestSide = n(row.value_under_pct) > n(row.value_over_pct) ? "UNDER" : "OVER";
  const bestValue = trustedLine ? Math.max(n(row.value_over_pct), n(row.value_under_pct)) : 0;
  const bestNovigEdge = bestSide === "UNDER" ? n(row.edge_under_novig_pp) : n(row.edge_over_novig_pp);
  const blockedReason = row.blocked_reason || rowRejectionReason(row);
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <MiniBadge label={row.recommended_side || "watch"} tone={recTone(row.recommended_side)} />
            <MiniBadge label={row.matched_board === "yes" ? "matched" : "unmatched"} tone={row.matched_board === "yes" ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-rose-500/25 bg-rose-500/10 text-rose-300"} />
            <MiniBadge label={row.line_quality || "line"} tone={row.line_quality === "complete" ? "border-cyan-500/25 bg-cyan-500/10 text-cyan-200" : "border-amber-500/25 bg-amber-500/10 text-amber-300"} />
            <MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} />
            {!row.recommended_side && blockedReason ? <MiniBadge label={blockedReason.replaceAll("_", " ")} tone="border-amber-500/25 bg-amber-500/10 text-amber-300" /> : null}
          </div>
          <div className="mt-2 font-semibold text-slate-100">{row.player || "-"} - {row.market?.replaceAll("_", " ") || "market"} {fmt(row.line, 1)}</div>
          <div className="text-xs text-slate-500">projection {fmt(row.projection_mean, 1)} - {row.distribution || "model"}</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">{trustedLine ? "best value" : "audit only"}</div>
          <div className={cn("font-mono text-2xl font-black", trustedLine && bestValue > 0 ? "text-emerald-300" : "text-slate-500")}>
            {trustedLine ? `${bestSide} ${fmt(bestValue, 1)}%` : (row.line_quality || "watch").replaceAll("_", " ")}
          </div>
          {trustedLine ? <div className="mt-1 font-mono text-[11px] text-slate-500">no-vig edge {bestNovigEdge > 0 ? "+" : ""}{fmt(bestNovigEdge, 1)}pp</div> : null}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricTile label="Over price" value={fmt(row.over_odds, 2)} sub={`fair ${fmt(row.fair_over_odds, 2)}`} tone="text-slate-100" />
        <MetricTile label="Under price" value={fmt(row.under_odds, 2)} sub={`fair ${fmt(row.fair_under_odds, 2)}`} tone="text-slate-100" />
        <MetricTile label="Over value" value={trustedLine ? `${fmt(row.value_over_pct, 1)}%` : "audit"} sub={trustedLine ? `no-vig ${n(row.edge_over_novig_pp) > 0 ? "+" : ""}${fmt(row.edge_over_novig_pp, 1)}pp` : undefined} tone={trustedLine && n(row.value_over_pct) > 0 ? "text-emerald-300" : "text-slate-500"} />
        <MetricTile label="Under value" value={trustedLine ? `${fmt(row.value_under_pct, 1)}%` : "audit"} sub={trustedLine ? `no-vig ${n(row.edge_under_novig_pp) > 0 ? "+" : ""}${fmt(row.edge_under_novig_pp, 1)}pp` : undefined} tone={trustedLine && n(row.value_under_pct) > 0 ? "text-emerald-300" : "text-slate-500"} />
      </div>
      {row.model_market_gap_pp ? <div className="mt-2 text-[11px] text-slate-500">Model-market gap: {fmt(row.model_market_gap_pp, 1)}pp. Rows above the guard are blocked, even if raw EV looks large.</div> : null}
      {n(row.fair_p_push) > 0 ? <div className="mt-2 text-[11px] text-amber-300/80">Integer-line push mass: {(n(row.fair_p_push) * 100).toFixed(1)}%</div> : null}
    </div>
  );
}

function ComparisonTable({ rows, hasLinesFile }: { rows: CsvRow[]; hasLinesFile: boolean }) {
  if (!rows.length) {
    return (
      <EmptyState
        message={
          hasLinesFile
            ? "Bet365 lines file exists, but no aces/DF market rows matched the board. Check the audit/manual CSV."
            : "No Bet365 aces/DF lines available yet. The API audit can run daily, but a manual CSV drop may be needed if the provider does not expose tennis player props."
        }
      />
    );
  }
  const groupedRows = groupComparisonByMatch(rows);
  return (
    <div className="space-y-4">
      {groupedRows.map((group) => (
        <section key={group.date} className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-cyan-300">{dateLabel(group.date)}</span>
            <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.matches.length} matches / {group.matches.reduce((sum, match) => sum + match.rows.length, 0)} line rows</span>
          </div>
          {group.matches.map((match) => {
            const first = match.rows[0] ?? {};
            const recommended = match.rows.filter((row) => row.recommended_side).length;
            const matched = match.rows.filter((row) => row.matched_board === "yes").length;
            const maxEdge = Math.max(...match.rows.map(maxValue));
            return (
              <details key={`${group.date}-${match.key}`} open={recommended > 0 || maxEdge > 0} className="group rounded-[2rem] border border-slate-800/80 bg-slate-950/55">
                <summary className="cursor-pointer list-none p-4 sm:p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <MiniBadge label={first.tour || "-"} tone={first.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{first.tournament || "Tennis"}</span>
                      </div>
                      <h3 className="text-xl font-black tracking-tight text-slate-50">{fixtureName(match.rows)}</h3>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <MiniBadge label={`${recommended} rec`} tone={recommended ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-slate-700/70 bg-slate-800/60 text-slate-400"} />
                      <MiniBadge label={`${matched}/${match.rows.length} matched`} tone={matched === match.rows.length ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-amber-500/25 bg-amber-500/10 text-amber-300"} />
                      <MiniBadge label={`top ${fmt(maxEdge, 1)}%`} tone={maxEdge > 0 ? "border-cyan-500/25 bg-cyan-500/10 text-cyan-200" : "border-slate-700/70 bg-slate-800/60 text-slate-400"} />
                    </div>
                  </div>
                </summary>
                <div className="grid gap-3 border-t border-slate-800/80 p-4 sm:p-5 lg:grid-cols-2">
                  {match.rows.map((row, index) => <ComparisonLineCard key={`${match.key}-${row.player}-${row.market}-${row.line}-${index}`} row={row} />)}
                </div>
              </details>
            );
          })}
        </section>
      ))}
    </div>
  );
}


function rowBestSide(row: CsvRow): string {
  return n(row.value_under_pct) > n(row.value_over_pct) ? "UNDER" : "OVER";
}

function rowBestValue(row: CsvRow): number {
  return Math.max(n(row.value_over_pct), n(row.value_under_pct));
}

function rowRejectionReason(row: CsvRow): string {
  if (row.blocked_reason) return row.blocked_reason.replaceAll("_", " ").toLowerCase();
  const confidence = (row.confidence || "LOW").toUpperCase();
  if (confidence !== "HIGH") return `confidence ${confidence} (needs HIGH)`;
  if (row.line_quality && row.line_quality !== "complete") return `line is ${row.line_quality}`;
  if (row.notes) return "notes flag present";
  return "gate did not pass";
}

function RecommendationPanel({
  actionableRows,
  watchRows,
  matchedCount,
  totalCount,
}: {
  actionableRows: CsvRow[];
  watchRows: CsvRow[];
  matchedCount: number;
  totalCount: number;
}) {
  if (actionableRows.length) {
    return (
      <SectionCard
        title="Recommended Bet365 Props"
        subtitle="These are the only lines passing every live gate: matched Bet365 line, complete two-way price, HIGH confidence, clean notes, and edge threshold."
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {actionableRows.slice(0, 8).map((row, index) => <ComparisonLineCard key={`${row.player}-${row.market}-${row.line}-${index}`} row={row} />)}
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard
      title="Recommended Bet365 Props"
      subtitle="This is the actual betting decision layer, above the audit board."
    >
      <div className="rounded-[2rem] border border-amber-500/25 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.16),transparent_34%),rgba(15,23,42,0.84)] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-300">No bet suggested right now</div>
            <h3 className="mt-2 text-2xl font-black tracking-tight text-slate-50">0 official aces/DF recommendations</h3>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
              Bet365 is being compared now: {matchedCount} of {totalCount} line rows matched the board. None pass the full gate, so anything below is watch/audit only, not a bet.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <MetricTile label="Recommended" value="0" sub="official bets" tone="text-slate-400" />
            <MetricTile label="Matched lines" value={`${matchedCount}`} sub={`${totalCount} captured`} tone="text-cyan-300" />
            <MetricTile label="Required conf" value="HIGH" sub="aces/DF gate" tone="text-emerald-300" />
            <MetricTile label="Line type" value="clean" sub="complete two-way" tone="text-amber-300" />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <MiniBadge label="needs HIGH confidence" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
          <MiniBadge label="needs complete line" tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
          <MiniBadge label="needs clean notes" tone="border-slate-700/70 bg-slate-800/60 text-slate-300" />
          <MiniBadge label="needs value threshold" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
        </div>
      </div>
      {watchRows.length ? (
        <div className="mt-4">
          <div className="mb-2 text-xs font-black uppercase tracking-[0.16em] text-slate-500">Rejected audit examples, not bets</div>
          <div className="grid gap-3 lg:grid-cols-3">
            {watchRows.slice(0, 3).map((row, index) => (
              <div key={`${row.player}-${row.market}-${row.line}-${index}`} className="rounded-2xl border border-slate-800/80 bg-slate-950/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <MiniBadge label="rejected" tone="border-rose-500/25 bg-rose-500/10 text-rose-300" />
                  <MiniBadge label={row.confidence || "LOW"} tone={confidenceTone(row.confidence)} />
                </div>
                <div className="mt-2 font-semibold text-slate-100">{row.player} {rowBestSide(row)} {row.line} {row.market?.replaceAll("_", " ")}</div>
                <div className="mt-1 text-xs text-slate-500">vs {row.opponent} - projection {fmt(row.projection_mean, 1)}</div>
                <div className="mt-3 text-xs font-black uppercase tracking-[0.14em] text-rose-300">Blocked: {rowRejectionReason(row)}</div>
                <div className="mt-1 text-[11px] text-slate-500">Raw model edge {rowBestValue(row).toFixed(1)}%, kept audit-only.</div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </SectionCard>
  );
}

export default async function TennisPropsMonitorPage({ searchParams }: { searchParams?: SearchParamsInput }) {
  if (!MODEL_MONITOR_ENABLED) notFound();
  const resolvedSearchParams: Record<string, string | string[] | undefined> = searchParams ? await searchParams : {};
  const projectionSortKey = validProjectionSort(resolvedSearchParams.propsSort);

  const [
    boardRows,
    boardStamp,
    boardAgeHours,
    baselineStamp,
    factorsStamp,
    latestComparisonPath,
    latestLinesPath,
    shadowRows,
    shadowStamp,
    shadowPerformanceStamp,
  ] = await Promise.all([
    readCsv(BOARD_PATH),
    fileStamp(BOARD_PATH),
    fileAgeHours(BOARD_PATH),
    fileStamp(BASELINE_PATH),
    fileStamp(FACTORS_PATH),
    latestCsv("comparison"),
    latestCsv("bet365-lines"),
    readCsv(SHADOW_SIGNALS_PATH),
    fileStamp(SHADOW_SIGNALS_PATH),
    fileStamp(SHADOW_PERFORMANCE_PATH),
  ]);
  const comparisonRows = latestComparisonPath ? await readCsv(latestComparisonPath) : [];
  const lineRows = latestLinesPath ? await readCsv(latestLinesPath) : [];
  const lineStamp = latestLinesPath ? await fileStamp(latestLinesPath) : "missing";
  const comparisonStamp = latestComparisonPath ? await fileStamp(latestComparisonPath) : "missing";
  const sortedBoard = [...boardRows].sort(boardSort);
  const sortedComparison = [...comparisonRows].sort(comparisonSort);
  const matchedComparisonRows = sortedComparison.filter((row) => row.matched_board === "yes");
  const actionableRows = matchedComparisonRows.filter((row) => row.recommended_side);
  const cleanWatchRows = matchedComparisonRows
    .filter((row) => !row.recommended_side && row.line_quality === "complete")
    .sort((a, b) => rowBestValue(b) - rowBestValue(a));
  const sortedShadowRows = [...shadowRows].sort(shadowSort);
  const shadow = shadowStats(shadowRows);
  const boardStale = boardAgeHours == null || boardAgeHours > 24;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_24%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <MonitorNav current="tennis-props" />
        </div>

        <HeroCard title="Tennis Aces / Double-Faults Board" eyebrow="Tennis player props research">
          <p className="text-slate-300">
            Local OnCourt schedule plus Sackmann service stats. This is a research board for Bet365 aces and double-fault lines, not a public record lane yet.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label="OnCourt schedule" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
            <StatusPill label="ATP + WTA" tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
            <StatusPill label="Research only" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
          </div>
        </HeroCard>

        <section className="my-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <StatCard label="Projection rows" value={String(boardRows.length)} detail={`${countBy(boardRows, "tour", "ATP")} ATP / ${countBy(boardRows, "tour", "WTA")} WTA`} />
          <StatCard label="High ace conf" value={String(countBy(boardRows, "ace_confidence", "HIGH"))} detail="Sample + event history gate" tone="text-emerald-300" />
          <StatCard label="High DF conf" value={String(countBy(boardRows, "df_confidence", "HIGH"))} detail="Harder gate, noisier market" tone="text-rose-300" />
          <StatCard label="Bet365 rows" value={String(comparisonRows.length)} detail={`${matchedComparisonRows.length} matched / ${lineStamp}`} tone={comparisonRows.length ? "text-cyan-300" : "text-slate-400"} />
          <StatCard label="Actionable" value={String(actionableRows.length)} detail="HIGH confidence + edge gate" tone={actionableRows.length ? "text-emerald-300" : "text-slate-400"} />
          <StatCard label="Shadow evidence" value={String(shadowRows.length)} detail={`${shadow.settled} settled / ${shadow.pending} pending`} tone={shadowRows.length ? "text-amber-300" : "text-slate-400"} />
        </section>

        <section className="mb-6 grid gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-400 md:grid-cols-4">
          <div><span className="text-slate-500">Board:</span> <span className="text-slate-200">{boardStamp}</span></div>
          <div><span className="text-slate-500">Baseline:</span> <span className="text-slate-200">{baselineStamp}</span></div>
          <div><span className="text-slate-500">Venue factors:</span> <span className="text-slate-200">{factorsStamp}</span></div>
          <div><span className="text-slate-500">Comparison:</span> <span className="text-slate-200">{comparisonStamp}</span></div>
          <div><span className="text-slate-500">Shadow:</span> <span className="text-slate-200">{shadowStamp}</span></div>
          <div><span className="text-slate-500">Shadow perf:</span> <span className="text-slate-200">{shadowPerformanceStamp}</span></div>
        </section>

        {boardStale ? (
          <section className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
            Projection board is stale or missing. Run <span className="font-mono text-amber-50">python scripts/run-tennis-props-daily.py</span> after the OnCourt extract before trusting today&apos;s props board.
          </section>
        ) : null}

        <div className="grid gap-6">
          <RecommendationPanel
            actionableRows={actionableRows}
            watchRows={cleanWatchRows}
            matchedCount={matchedComparisonRows.length}
            totalCount={comparisonRows.length}
          />

          <SectionCard
            title="Bet365 Comparison"
            subtitle="Appears when data/tennis-props/comparison-YYYY-MM-DD.csv exists. Recommended side is gated hard; most rows should stay watch-only."
          >
            <ComparisonTable rows={matchedComparisonRows} hasLinesFile={lineRows.length > 0} />
          </SectionCard>

          <SectionCard
            title="Shadow Evidence"
            subtitle={`Append-only Bet365 line evidence. ROI is research-only until 300+ settled lines. Current shadow PnL ${shadow.pnl >= 0 ? "+" : ""}${shadow.pnl.toFixed(2)}u / ROI ${shadow.roi >= 0 ? "+" : ""}${shadow.roi.toFixed(1)}%.`}
          >
            <ShadowEvidenceTable rows={sortedShadowRows} />
          </SectionCard>

          <SectionCard
            title={`Projection Board (${latestDate(boardRows)})`}
            subtitle="Expected aces and double faults for each scheduled player. This is the simulation layer you asked for."
          >
            <ProjectionTable rows={sortedBoard} sortKey={projectionSortKey} />
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
