import { promises as fs } from "fs";
import path from "path";
import { Fragment } from "react";
import { notFound } from "next/navigation";
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

const ROOT = process.cwd();
const PROPS_DIR = path.join(ROOT, "data", "tennis-props");
const BOARD_PATH = path.join(PROPS_DIR, "player-props-board.csv");
const BASELINE_PATH = path.join(PROPS_DIR, "player-props-baseline.csv");
const FACTORS_PATH = path.join(PROPS_DIR, "slam-venue-factors.csv");
const INBOX_DIR = path.join(PROPS_DIR, "inbox");

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

function MiniBadge({ label, tone }: { label: string; tone: string }) {
  return (
    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em]", tone)}>
      {label}
    </span>
  );
}

function ProjectionTable({ rows }: { rows: CsvRow[] }) {
  if (!rows.length) return <EmptyState message="No aces/DF projection board found. Run python scripts/run-tennis-props-daily.py after OnCourt extract." />;
  const groupedRows = groupRowsByDate(rows);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <th className="px-3 py-3 font-semibold">Tour</th>
            <th className="px-3 py-3 font-semibold">Player</th>
            <th className="px-3 py-3 font-semibold">Opponent</th>
            <th className="px-3 py-3 font-semibold">Aces</th>
            <th className="px-3 py-3 font-semibold">DFs</th>
            <th className="px-3 py-3 font-semibold">Aces conf</th>
            <th className="px-3 py-3 font-semibold">DF conf</th>
            <th className="px-3 py-3 font-semibold">Sample</th>
            <th className="px-3 py-3 font-semibold">Notes</th>
          </tr>
        </thead>
        <tbody>
          {groupedRows.map((group) => (
            <Fragment key={group.date}>
              <tr className="border-y border-slate-800 bg-slate-950/80">
                <td colSpan={9} className="px-3 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">{dateLabel(group.date)}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate-500">{group.rows.length} player rows</span>
                  </div>
                </td>
              </tr>
              {group.rows.map((row, index) => (
                <tr key={`${group.date}-${row.tour}-${row.player}-${row.opponent}-${index}`} className="border-b border-slate-900/80 text-slate-300">
                  <td className="px-3 py-3">
                    <MiniBadge label={row.tour || "-"} tone={row.tour === "WTA" ? "border-fuchsia-500/25 bg-fuchsia-500/10 text-fuchsia-200" : "border-cyan-500/25 bg-cyan-500/10 text-cyan-200"} />
                  </td>
                  <td className="px-3 py-3 font-semibold text-slate-100">{row.player}</td>
                  <td className="px-3 py-3 text-slate-400">{row.opponent}</td>
                  <td className="px-3 py-3 font-mono text-lg text-emerald-300">{fmt(row.projected_aces, 1)}</td>
                  <td className="px-3 py-3 font-mono text-lg text-rose-300">{fmt(row.projected_dfs, 1)}</td>
                  <td className="px-3 py-3"><MiniBadge label={row.ace_confidence || "LOW"} tone={confidenceTone(row.ace_confidence)} /></td>
                  <td className="px-3 py-3"><MiniBadge label={row.df_confidence || "LOW"} tone={confidenceTone(row.df_confidence)} /></td>
                  <td className="px-3 py-3 font-mono text-xs text-slate-400">
                    <div>{row.player_surface_matches || "0"}m / {row.player_surface_svpt_sample || "0"} svpt</div>
                    <div className="text-slate-600">event {row.same_tournament_matches || "0"}m / {row.same_tournament_svpt || "0"} svpt</div>
                  </td>
                  <td className="px-3 py-3 text-xs text-slate-500">{row.notes || "clear"}</td>
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
                  <td className="px-3 py-3 font-mono text-xs text-slate-400">{fmt(row.fair_over_odds, 2)} / {fmt(row.fair_under_odds, 2)}</td>
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

export default async function TennisPropsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [boardRows, boardStamp, boardAgeHours, baselineStamp, factorsStamp, latestComparisonPath, latestLinesPath] = await Promise.all([
    readCsv(BOARD_PATH),
    fileStamp(BOARD_PATH),
    fileAgeHours(BOARD_PATH),
    fileStamp(BASELINE_PATH),
    fileStamp(FACTORS_PATH),
    latestCsv("comparison"),
    latestCsv("bet365-lines"),
  ]);
  const comparisonRows = latestComparisonPath ? await readCsv(latestComparisonPath) : [];
  const lineRows = latestLinesPath ? await readCsv(latestLinesPath) : [];
  const lineStamp = latestLinesPath ? await fileStamp(latestLinesPath) : "missing";
  const comparisonStamp = latestComparisonPath ? await fileStamp(latestComparisonPath) : "missing";
  const sortedBoard = [...boardRows].sort(boardSort);
  const sortedComparison = [...comparisonRows].sort(comparisonSort);
  const actionableRows = sortedComparison.filter((row) => row.recommended_side);
  const boardStale = boardAgeHours == null || boardAgeHours > 24;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_24%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <MonitorNav current="tennis-props" />
        </div>

        <HeroCard title="Tennis Aces / Double-Faults Board" eyebrow="Slam player props research">
          <p className="text-slate-300">
            Local OnCourt schedule plus Sackmann service stats. This is a research board for Bet365 aces and double-fault lines, not a public record lane yet.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label="OnCourt schedule" tone="border-emerald-500/25 bg-emerald-500/10 text-emerald-300" />
            <StatusPill label="ATP + WTA" tone="border-cyan-500/25 bg-cyan-500/10 text-cyan-200" />
            <StatusPill label="Research only" tone="border-amber-500/25 bg-amber-500/10 text-amber-300" />
          </div>
        </HeroCard>

        <section className="my-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Projection rows" value={String(boardRows.length)} detail={`${countBy(boardRows, "tour", "ATP")} ATP / ${countBy(boardRows, "tour", "WTA")} WTA`} />
          <StatCard label="High ace conf" value={String(countBy(boardRows, "ace_confidence", "HIGH"))} detail="Sample + Slam history gate" tone="text-emerald-300" />
          <StatCard label="High DF conf" value={String(countBy(boardRows, "df_confidence", "HIGH"))} detail="Harder gate, noisier market" tone="text-rose-300" />
          <StatCard label="Bet365 rows" value={String(comparisonRows.length)} detail={lineStamp} tone={comparisonRows.length ? "text-cyan-300" : "text-slate-400"} />
          <StatCard label="Actionable" value={String(actionableRows.length)} detail="HIGH confidence + edge gate" tone={actionableRows.length ? "text-emerald-300" : "text-slate-400"} />
        </section>

        <section className="mb-6 grid gap-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-xs text-slate-400 md:grid-cols-4">
          <div><span className="text-slate-500">Board:</span> <span className="text-slate-200">{boardStamp}</span></div>
          <div><span className="text-slate-500">Baseline:</span> <span className="text-slate-200">{baselineStamp}</span></div>
          <div><span className="text-slate-500">Slam factors:</span> <span className="text-slate-200">{factorsStamp}</span></div>
          <div><span className="text-slate-500">Comparison:</span> <span className="text-slate-200">{comparisonStamp}</span></div>
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
            title={`Projection Board (${latestDate(boardRows)})`}
            subtitle="Expected aces and double faults for each scheduled player. This is the simulation layer you asked for."
          >
            <ProjectionTable rows={sortedBoard} />
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
