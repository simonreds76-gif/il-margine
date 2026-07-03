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

function ProjectionTable({ rows, sortKey }: { rows: CsvRow[]; sortKey: ProjectionSortKey }) {
  if (!rows.length) return <EmptyState message="No aces/DF projection board found. Run python scripts/run-tennis-props-daily.py after OnCourt extract." />;
  const groupedRows = groupRowsByDateAndMatch(rows, sortKey);
  return (
    <div className="overflow-x-auto">
      <ProjectionSortControls active={sortKey} />
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-3 py-3 font-semibold">Tour</th>
            <th className="px-3 py-3 font-semibold">Player</th>
            <th className="px-3 py-3 font-semibold">Opponent</th>
            <th className="px-3 py-3 font-semibold">Aces</th>
            <th className="px-3 py-3 font-semibold">DFs</th>
            <th className="px-3 py-3 font-semibold">Breaks</th>
            <th className="px-3 py-3 font-semibold">Tie-break %</th>
            <th className="px-3 py-3 font-semibold">Aces conf</th>
            <th className="px-3 py-3 font-semibold">DF conf</th>
            <th className="px-3 py-3 font-semibold">Break conf</th>
            <th className="px-3 py-3 font-semibold">TB conf</th>
            <th className="px-3 py-3 font-semibold">Model inputs</th>
            <th className="px-3 py-3 font-semibold">Live event</th>
            <th className="px-3 py-3 font-semibold">Notes</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map((group) => (
            <Fragment key={group.date}>
              <tr className="border-y border-slate-800 bg-slate-950/80">
                <td colSpan={14} className="px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">{dateLabel(group.date)}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.matches.length} matches / {group.matches.reduce((sum, match) => sum + match.rows.length, 0)} player rows</span>
                  </div>
                </td>
              </tr>
              {group.matches.map((match) => (
                <Fragment key={`${group.date}-${match.key}`}>
                  <tr className="border-b border-slate-900/80 bg-slate-950/45">
                    <td colSpan={14} className="px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="font-semibold text-slate-100">{fixtureName(match.rows)}</div>
                        <div className="flex flex-wrap gap-2 font-mono text-[11px]">
                          <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-violet-200">match TB {fmt(projectionSortValue(match.rows, "match_tb"), 1)}%</span>
                          <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-emerald-200">max aces {fmt(projectionSortValue(match.rows, "aces"), 1)}</span>
                          <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-rose-200">max DF {fmt(projectionSortValue(match.rows, "dfs"), 1)}</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                  {match.rows.map((row, index) => (
                    <tr key={`${group.date}-${row.tour}-${row.player}-${row.opponent}-${index}`} className="border-b border-slate-900/80 text-slate-300">
                      <td className="px-3 py-3">
                        <MiniBadge label={row.tour || "-"} tone={row.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-semibold text-slate-100">{row.player}</div>
                        <TournamentRoundDetails row={row} />
                      </td>
                      <td className="px-3 py-3 text-slate-400">{row.opponent}</td>
                      <td className="px-3 py-3 font-mono text-lg text-emerald-300">{fmt(row.projected_aces, 1)}</td>
                      <td className="px-3 py-3 font-mono text-lg text-rose-300">{fmt(row.projected_dfs, 1)}</td>
                      <td className="px-3 py-3 font-mono text-xs">
                        <div className="text-cyan-300">+{fmt(row.projected_breaks_for, 1)}</div>
                        <div className="text-amber-300">-{fmt(row.projected_broken, 1)}</div>
                        <div className="text-slate-500">tot {fmt(row.projected_total_breaks, 1)}</div>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs">
                        <TieBreakCell row={row} />
                      </td>
                      <td className="px-3 py-3"><MiniBadge label={row.ace_confidence || "LOW"} tone={confidenceTone(row.ace_confidence)} /></td>
                      <td className="px-3 py-3"><MiniBadge label={row.df_confidence || "LOW"} tone={confidenceTone(row.df_confidence)} /></td>
                      <td className="px-3 py-3"><MiniBadge label={row.break_confidence || "LOW"} tone={confidenceTone(row.break_confidence)} /></td>
                      <td className="px-3 py-3"><MiniBadge label={row.tiebreak_confidence || "LOW"} tone={confidenceTone(row.tiebreak_confidence)} /></td>
                      <td className="px-3 py-3 text-xs text-slate-400">
                        <div className="min-w-[180px] rounded-xl border border-slate-800/80 bg-slate-950/55 p-2">
                          <div className="mb-1 font-mono text-emerald-300">
                            match games {fmt(row.expected_match_games, 1)}
                          </div>
                          <div className="mb-2 text-[11px] uppercase tracking-[0.1em] text-slate-600">
                            {row.expected_match_games_source || "fallback"}
                            {row.expected_match_games_confidence ? ` / ${row.expected_match_games_confidence}` : ""}
                          </div>
                          <div className="font-mono text-slate-300">{row.player_surface_matches || "0"}m / {row.player_surface_svpt_sample || "0"} svpt</div>
                          <div className="mt-1 text-[11px] text-slate-600">player same-event {row.same_tournament_matches || "0"}m / {row.same_tournament_svpt || "0"} svpt</div>
                          <div className="mt-1 text-[11px] text-slate-600">brk log +{row.same_tournament_breaks_for || "0"} / -{row.same_tournament_broken || "0"}</div>
                          <div className="mt-1 text-[11px] text-slate-600">serve pts {fmt(row.service_point_win, 3)} / opp {fmt(row.opponent_service_point_win, 3)}</div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-xs">
                        <div className="min-w-[310px] rounded-xl border border-slate-800/80 bg-slate-950/55 p-2">
                          <div className="mb-2 flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">
                            <span>current {row.current_env_matches || "0"} matches</span>
                            <span>live weight {fmt(row.current_env_weight, 2)}</span>
                          </div>
                          <div className="space-y-1.5">
                            <div className="grid grid-cols-[44px_1fr] items-center gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-emerald-300">Aces</span>
                              <div className="flex flex-wrap gap-1.5">
                                <MiniBadge label={`venue ${factorMove(row.venue_ace_factor)}`} tone={factorTone(row.venue_ace_factor)} />
                                <MiniBadge label={`live ${factorMove(row.current_env_ace_factor)}`} tone={factorTone(row.current_env_ace_factor)} />
                                <MiniBadge label={`net ${factorProductMove(row.venue_ace_factor, row.current_env_ace_factor)}`} tone={factorProductTone(row.venue_ace_factor, row.current_env_ace_factor)} />
                              </div>
                            </div>
                            <div className="grid grid-cols-[44px_1fr] items-center gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-rose-300">DF</span>
                              <div className="flex flex-wrap gap-1.5">
                                <MiniBadge label={`venue ${factorMove(row.venue_df_factor)}`} tone={factorTone(row.venue_df_factor)} />
                                <MiniBadge label={`live ${factorMove(row.current_env_df_factor)}`} tone={factorTone(row.current_env_df_factor)} />
                                <MiniBadge label={`net ${factorProductMove(row.venue_df_factor, row.current_env_df_factor)}`} tone={factorProductTone(row.venue_df_factor, row.current_env_df_factor)} />
                              </div>
                            </div>
                            <div className="grid grid-cols-[44px_1fr] items-center gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-cyan-300">Brk</span>
                              <div className="flex flex-wrap gap-1.5">
                                <MiniBadge label={`live ${factorMove(row.current_env_break_factor)}`} tone={factorTone(row.current_env_break_factor)} />
                              </div>
                            </div>
                            <div className="grid grid-cols-[44px_1fr] items-center gap-2">
                              <span className="text-[10px] font-black uppercase tracking-[0.12em] text-violet-300">TB</span>
                              <div className="flex flex-wrap gap-1.5">
                            <MiniBadge label={`1st venue ${factorMove(row.venue_first_set_tiebreak_factor)}`} tone={factorTone(row.venue_first_set_tiebreak_factor)} />
                            <MiniBadge label={`1st live ${factorMove(row.current_env_first_set_tiebreak_factor)}`} tone={factorTone(row.current_env_first_set_tiebreak_factor)} />
                            <MiniBadge label={`match venue ${factorMove(row.venue_match_tiebreak_factor)}`} tone={factorTone(row.venue_match_tiebreak_factor)} />
                            <MiniBadge label={`match live ${factorMove(row.current_env_match_tiebreak_factor)}`} tone={factorTone(row.current_env_match_tiebreak_factor)} />
                            <MiniBadge label={`player ${factorMove(row.player_tiebreak_factor)}`} tone={factorTone(row.player_tiebreak_factor)} />
                          </div>
                          <div className="mt-1 text-[10px] text-slate-600">
                            hist match TB {pctText(row.player_match_tiebreak_actual_pct)} / opp {pctText(row.opponent_match_tiebreak_actual_pct)}
                            {row.player_tiebreak_sample ? ` · sample ${row.player_tiebreak_sample}` : ""}
                          </div>
                        </div>
                      </div>
                    </div>
                      </td>
                      <td className="px-3 py-3 text-xs text-slate-500">
                        <NoteBadges value={[row.notes, row.break_notes, row.tiebreak_notes].filter(Boolean).join("|")} />
                      </td>
                    </tr>
                  ))}
                </Fragment>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
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
  const groupedRows = groupRowsByDate(rows);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-3 py-3 font-semibold">Rec</th>
            <th className="px-3 py-3 font-semibold">Player</th>
            <th className="px-3 py-3 font-semibold">Market</th>
            <th className="px-3 py-3 font-semibold">Line</th>
            <th className="px-3 py-3 font-semibold">Projection</th>
            <th className="px-3 py-3 font-semibold">Over</th>
            <th className="px-3 py-3 font-semibold">Under</th>
            <th className="px-3 py-3 font-semibold">Fair O/U</th>
            <th className="px-3 py-3 font-semibold">Value O/U</th>
            <th className="px-3 py-3 font-semibold">Conf</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map((group) => (
            <Fragment key={group.date}>
              <tr className="border-y border-slate-800 bg-slate-950/80">
                <td colSpan={10} className="px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase tracking-[0.18em] text-cyan-300">{dateLabel(group.date)}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.rows.length} line rows</span>
                  </div>
                </td>
              </tr>
              {group.rows.map((row, index) => (
                <tr key={`${group.date}-${row.player}-${row.market}-${row.line}-${index}`} className="border-b border-slate-900/80 text-slate-300">
                  <td className="px-3 py-3"><MiniBadge label={row.recommended_side || "watch"} tone={recTone(row.recommended_side)} /></td>
                  <td className="px-3 py-3">
                    <div className="font-semibold text-slate-100">{row.player}</div>
                    <div className="text-xs text-slate-500">vs {row.opponent}</div>
                  </td>
                  <td className="px-3 py-3 text-slate-300">{row.market}</td>
                  <td className="px-3 py-3 font-mono text-slate-100">{fmt(row.line, 1)}</td>
                  <td className="px-3 py-3 font-mono text-slate-100">{fmt(row.projection_mean, 1)}</td>
                  <td className="px-3 py-3 font-mono text-slate-300">{fmt(row.over_odds, 2)}</td>
                  <td className="px-3 py-3 font-mono text-slate-300">{fmt(row.under_odds, 2)}</td>
                  <td className="px-3 py-3 font-mono text-xs text-slate-400">
                    <div>{fmt(row.fair_over_odds, 2)} / {fmt(row.fair_under_odds, 2)}</div>
                    {n(row.fair_p_push) > 0 ? <div className="text-[10px] text-amber-300/70">push {(n(row.fair_p_push) * 100).toFixed(1)}%</div> : null}
                  </td>
                  <td className="px-3 py-3 font-mono text-xs">
                    <span className={n(row.value_over_pct) > 0 ? "text-emerald-300" : "text-slate-500"}>{fmt(row.value_over_pct, 1)}%</span>
                    <span className="text-slate-600"> / </span>
                    <span className={n(row.value_under_pct) > 0 ? "text-emerald-300" : "text-slate-500"}>{fmt(row.value_under_pct, 1)}%</span>
                  </td>
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
  const actionableRows = sortedComparison.filter((row) => row.recommended_side);
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
          <StatCard label="Bet365 rows" value={String(comparisonRows.length)} detail={lineStamp} tone={comparisonRows.length ? "text-cyan-300" : "text-slate-400"} />
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
          <SectionCard
            title="Bet365 Comparison"
            subtitle="Appears when data/tennis-props/comparison-YYYY-MM-DD.csv exists. Recommended side is gated hard; most rows should stay watch-only."
          >
            <ComparisonTable rows={sortedComparison.slice(0, 80)} hasLinesFile={lineRows.length > 0} />
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
