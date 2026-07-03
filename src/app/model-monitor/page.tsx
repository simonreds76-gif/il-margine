import Link from "next/link";
import { promises as fs } from "fs";
import { notFound } from "next/navigation";
import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";
import { MODEL_MONITOR_ENABLED, MonitorNav, cn } from "./shared";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;

type MonitorTile = {
  title: string;
  href: string;
  eyebrow: string;
  state: "live" | "shadow" | "paused" | "content";
  summary: string;
  bullets: string[];
};

const monitorTiles: MonitorTile[] = [
  {
    title: "Tennis ML Live Control",
    href: "/model-monitor/tennis/live",
    eyebrow: "official betting lane",
    state: "live",
    summary: "Strict hard-court control board with Volume 200, Spread v1, CLV coverage, settlement queues and historical profile detail.",
    bullets: ["Strict Hard Masters is the clean production lane", "Volume 200 is bundled shadow expansion", "Spread v1 is handicap research only"],
  },
  {
    title: "Tennis Research Lanes",
    href: "/model-monitor/tennis",
    eyebrow: "surface + CPI lab",
    state: "shadow",
    summary: "Single home for Grass bo3, Clay bo3, CPI speed shadow, Challenger tracker and parked future lanes.",
    bullets: ["Shows live rows, settled rows, ROI and near-miss reasons", "CPI speed cells are visible here", "No research lane is silently treated as a live pick"],
  },
  {
    title: "Tennis Props",
    href: "/model-monitor/tennis-props",
    eyebrow: "aces / dfs / tie-breaks",
    state: "shadow",
    summary: "Projection board for aces, double faults, breaks and tie-break probabilities with venue factors and same-tournament context.",
    bullets: ["Useful for research and manual price checks", "Not a paid/tipping lane until odds capture and settlement prove it", "Wimbledon and Slam props live here"],
  },
  {
    title: "Player Props Public Record",
    href: "/player-props",
    eyebrow: "commercial record",
    state: "live",
    summary: "The clean public product page: grouped World Cup picks, settled record, category cards and progression charts.",
    bullets: ["This is what users should understand", "Monitor is internal; player-props is public", "Telegram posts link into this record"],
  },
  {
    title: "Team Shots",
    href: "/model-monitor/team-shots",
    eyebrow: "football research",
    state: "paused",
    summary: "Canonical football team-shots tracker. Club-season lane is paused until the new domestic season.",
    bullets: ["Do not mix old comparison reports into the headline", "Needs one CLV-positive tracker before selling", "World Cup is not currently routed through this lane"],
  },
  {
    title: "Corners",
    href: "/model-monitor/corners",
    eyebrow: "real-odds rebuild",
    state: "shadow",
    summary: "Corners v2 should be judged against real Pinnacle prices only. Synthetic ROI is not a sellable edge.",
    bullets: ["NB/real-odds path only", "Sell gate: n>=200, CLV>=+1%, >=55% positive", "Current output is research, not a product"],
  },
  {
    title: "Goalscorer",
    href: "/model-monitor/goalscorer",
    eyebrow: "content + model audit",
    state: "content",
    summary: "Club goalscorer model and World Cup content pipeline. Penalty-taker content is useful; club ATGS still needs recalibration.",
    bullets: ["Keep WC and club records separate", "Penalty pages are acquisition/content", "Club EV needs recalibration before paid use"],
  },
  {
    title: "Assist Value",
    href: "/model-monitor/assist-value",
    eyebrow: "disabled research",
    state: "paused",
    summary: "Assist model remains research-only and should not be treated as a live product while club football is off-season.",
    bullets: ["Triple-gated and not public", "Needs set-piece source repair and calibration", "Keep it visible but clearly quarantined"],
  },
];

const statusStyles = {
  live: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
  shadow: "border-cyan-500/30 bg-cyan-500/10 text-cyan-200",
  paused: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  content: "border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-200",
};

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur);
  return out;
}

function parseCsv(text: string | null): CsvRow[] {
  if (!text) return [];
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) return [];
  const headers = parseCsvLine(lines[0]).map((header) => header.trim());
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

async function readKnownFile(relativePath: string): Promise<string | null> {
  const fullPath = tryGetKnownProjectFilePath(relativePath);
  if (!fullPath) return null;
  try {
    return await fs.readFile(fullPath, "utf8");
  } catch {
    return null;
  }
}

async function readKnownMtime(relativePath: string): Promise<string | null> {
  const fullPath = tryGetKnownProjectFilePath(relativePath);
  if (!fullPath) return null;
  try {
    return (await fs.stat(fullPath)).mtime.toISOString();
  } catch {
    return null;
  }
}

function toNumber(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPct(value: number | null, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatUnits(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function pickPerfRow(rows: CsvRow[]): CsvRow | null {
  const preferred = [...rows].reverse().find((row) => {
    return row.scope === "all_time" && row.eval_period === "clean" && row.league_scope === "combined" && (row.bet_type || "") === "";
  });
  if (preferred) return preferred;
  return [...rows].reverse().find((row) => row.scope === "all_time" && (row.bet_type || "") === "") ?? rows.at(-1) ?? null;
}

async function metricFromPerf(path: string) {
  const rows = parseCsv(await readKnownFile(path));
  const row = pickPerfRow(rows);
  return {
    signals: toNumber(row?.signals),
    settled: toNumber(row?.settled),
    open: toNumber(row?.unsettled),
    pnl: toNumber(row?.pnl_units),
    roi: toNumber(row?.roi_pct),
    updated: await readKnownMtime(path),
  };
}

async function liveRows(path: string) {
  return parseCsv(await readKnownFile(path)).length;
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{value}</div>
      <div className="mt-1 text-xs leading-5 text-slate-500">{hint}</div>
    </div>
  );
}

function Tile({ tile }: { tile: MonitorTile }) {
  return (
    <Link
      href={tile.href}
      className="group rounded-3xl border border-slate-800/80 bg-[linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.94))] p-5 transition hover:border-emerald-500/35 hover:bg-slate-900/80"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">{tile.eyebrow}</div>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-white">{tile.title}</h2>
        </div>
        <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]", statusStyles[tile.state])}>
          {tile.state}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{tile.summary}</p>
      <ul className="mt-4 space-y-2 text-sm text-slate-300">
        {tile.bullets.map((bullet) => (
          <li key={bullet} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400/80" />
            <span>{bullet}</span>
          </li>
        ))}
      </ul>
      <div className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 opacity-80 transition group-hover:opacity-100">
        Open board -&gt;
      </div>
    </Link>
  );
}

export default async function ModelMonitorIndexPage() {
  if (!MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [strict, volume, cpi, strictLive, volumeLive, grassLive] = await Promise.all([
    metricFromPerf("data/backtest/strict-policy-performance-weekly.csv"),
    metricFromPerf("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    metricFromPerf("data/backtest/strict-policy-performance-cpi_speed-weekly.csv"),
    liveRows("data/backtest/strict-signals-live.csv"),
    liveRows("data/backtest/strict-signals-volume200-live.csv"),
    liveRows("data/backtest/strict-signals-grass_bo3-live.csv"),
  ]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-6">
          <MonitorNav current="overview" />
        </div>

        <section className="overflow-hidden rounded-[2rem] border border-emerald-500/20 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.18),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.12),transparent_35%),linear-gradient(135deg,rgba(15,23,42,0.98),rgba(2,6,23,0.98))] p-6 shadow-[0_24px_80px_rgba(2,6,23,0.45)] md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">Model control room</p>
              <h1 className="mt-3 max-w-4xl text-3xl font-semibold tracking-tight text-white md:text-5xl">
                One clean map of every model, lane and research board.
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
                Production lanes, shadow experiments and paused football models are separated here. The goal is simple:
                you should know what can be used, what is only research, and where to check P/L, ROI and CLV without
                hunting through random generated files.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-700/70 bg-slate-950/50 p-4 text-sm text-slate-300 lg:max-w-sm">
              <div className="font-semibold text-slate-100">Rule of the page</div>
              <p className="mt-2 leading-6">Green can be operational. Cyan is shadow. Amber is paused or not sellable. No hidden lane should look like a paid pick.</p>
            </div>
          </div>
        </section>

        <section className="mt-6 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard label="Strict ROI" value={formatPct(strict.roi)} hint={`${strict.settled ?? 0} settled, ${strictLive} live rows`} />
          <MetricCard label="Strict P/L" value={formatUnits(strict.pnl)} hint="official hard/Masters control" />
          <MetricCard label="Vol200 ROI" value={formatPct(volume.roi)} hint={`${volume.settled ?? 0} settled, ${volumeLive} live rows`} />
          <MetricCard label="CPI speed ROI" value={formatPct(cpi.roi)} hint="shadow-only court-speed lane" />
          <MetricCard label="CPI P/L" value={formatUnits(cpi.pnl)} hint="research, not public routing" />
          <MetricCard label="Grass rows" value={`${grassLive}`} hint="grass_bo3 live CSV rows" />
        </section>

        <section className="mt-8 grid gap-4 lg:grid-cols-2">
          {monitorTiles.map((tile) => <Tile key={tile.href} tile={tile} />)}
        </section>

        <section className="mt-8 rounded-3xl border border-slate-800 bg-slate-950/45 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Operational interpretation</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                This is the current hierarchy. If a lane is not in the live column, it should not be sold or shown as a proven edge.
              </p>
            </div>
            <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-300">
              noindex internal page
            </span>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <h3 className="font-semibold text-emerald-100">Usable / operational</h3>
              <p className="mt-2 text-sm leading-6 text-emerald-50/80">Tennis strict hard/Masters and the public player-props record. These are the boards you can actually explain to someone.</p>
            </div>
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4">
              <h3 className="font-semibold text-cyan-100">Shadow / being tested</h3>
              <p className="mt-2 text-sm leading-6 text-cyan-50/80">Volume 200, Spread v1, Clay bo3, Grass bo3, CPI speed, tennis props, corners v2. They need ROI/CLV proof before promotion.</p>
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
              <h3 className="font-semibold text-amber-100">Paused / quarantined</h3>
              <p className="mt-2 text-sm leading-6 text-amber-50/80">Assist value and most club-football automation during off-season. Visible for audit, not for daily betting decisions.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
