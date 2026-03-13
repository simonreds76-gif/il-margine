import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";

type CsvRow = Record<string, string>;

type PerfSnapshot = {
  combinedAll?: CsvRow;
  combinedWindow?: CsvRow;
  mlAll?: CsvRow;
  handicapAll?: CsvRow;
  mlWindow?: CsvRow;
  handicapWindow?: CsvRow;
};

type ClvSummary = {
  rawRows?: number;
  settledMlAudited?: number;
  matchedMl?: number;
  matchedMlTotal?: number;
  historyRows?: number;
  signalDateRange?: string;
  matchDateRange?: string;
  closingDateRange?: string;
  warning?: string;
};

type ProfileSummary = {
  name: string;
  bets?: number;
  avgPerYear?: number;
  winRatePct?: number;
  avgValuePct?: number;
  flatRoiPct?: number;
  tierRoiPct?: number;
  tierPnL?: number;
  tierStaked?: number;
  years: Array<{ year: string; bets?: number; tierRoiPct?: number }>;
};

export const dynamic = "force-dynamic";

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

function parseCsv(text: string): CsvRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (!lines.length) return [];
  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row: CsvRow = {};
    headers.forEach((header, idx) => {
      row[header] = values[idx] ?? "";
    });
    return row;
  });
}

async function readLocalFile(relPath: string): Promise<string | null> {
  try {
    return await fs.readFile(path.join(process.cwd(), relPath), "utf8");
  } catch {
    return null;
  }
}

async function readLocalMtime(relPath: string): Promise<string | null> {
  try {
    const stat = await fs.stat(path.join(process.cwd(), relPath));
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

function lastMatching(rows: CsvRow[], predicate: (row: CsvRow) => boolean): CsvRow | undefined {
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (predicate(rows[i])) return rows[i];
  }
  return undefined;
}

function parsePerf(rows: CsvRow[], policyMode: string): PerfSnapshot {
  return {
    combinedAll: lastMatching(rows, (row) => row.scope === "all_time" && row.policy_mode === policyMode && !row.bet_type),
    combinedWindow: lastMatching(rows, (row) => row.scope === "window" && row.policy_mode === policyMode && !row.bet_type),
    mlAll: lastMatching(rows, (row) => row.scope === "all_time" && row.policy_mode === policyMode && row.bet_type === "ml"),
    handicapAll: lastMatching(rows, (row) => row.scope === "all_time" && row.policy_mode === policyMode && row.bet_type === "handicap"),
    mlWindow: lastMatching(rows, (row) => row.scope === "window" && row.policy_mode === policyMode && row.bet_type === "ml"),
    handicapWindow: lastMatching(rows, (row) => row.scope === "window" && row.policy_mode === policyMode && row.bet_type === "handicap"),
  };
}

function parseFloatMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseIntMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : undefined;
}

function formatPct(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatUnits(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}u`;
}

function metricTone(value?: number): string {
  if (value == null || Number.isNaN(value)) return "text-slate-300";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-300";
}

function parseClvAudit(text: string | null): ClvSummary {
  if (!text) return {};
  const warningBlock = text.match(/Coverage warning\s+([\s\S]+?)(?:\n\n|$)/);
  return {
    rawRows: parseIntMaybe(text.match(/Raw strict rows:\s+(\d+)/)?.[1]),
    settledMlAudited: parseIntMaybe(text.match(/Settled ML rows audited:\s+(\d+)/)?.[1]),
    matchedMl: parseIntMaybe(text.match(/Matched ML rows:\s+(\d+)\s+\/\s+\d+/)?.[1]),
    matchedMlTotal: parseIntMaybe(text.match(/Matched ML rows:\s+\d+\s+\/\s+(\d+)/)?.[1]),
    historyRows: parseIntMaybe(text.match(/History rows loaded:\s+(\d+)/)?.[1]),
    signalDateRange: text.match(/Signal date range:\s+(.+)/)?.[1]?.trim(),
    matchDateRange: text.match(/Settled match-date range:\s+(.+)/)?.[1]?.trim(),
    closingDateRange: text.match(/Closing date range:\s+(.+)/)?.[1]?.trim(),
    warning: warningBlock?.[1]?.trim().replace(/\s+/g, " "),
  };
}

function parsePolicyProfiles(text: string | null): ProfileSummary[] {
  if (!text) return [];
  const blocks = [...text.matchAll(/\[([^\]]+)\]\n([\s\S]*?)(?=\n\[[^\]]+\]|\s*$)/g)];
  return blocks.map((match) => {
    const name = match[1];
    const body = match[2];
    const headline = body.match(/Bets=(\d+)\s+Avg\/Year=([\d.]+)\s+W-L=\d+-\d+\s+WR=([\d.]+)%\s+AvgValue=([\d.]+)%/);
    const flat = body.match(/Flat stake:\s+P\/L=[+-]?[\d.]+u\s+ROI=([+-]?[\d.]+)%/);
    const tier = body.match(/Value-tiered:\s+Staked=([\d.]+)u\s+P\/L=([+-]?[\d.]+)u\s+ROI=([+-]?[\d.]+)%/);
    const yearMatches = [...body.matchAll(/^\s+(\d{4}): bets=(\d+).*?tierROI=([+-]?[\d.]+)%/gm)];
    return {
      name,
      bets: parseIntMaybe(headline?.[1]),
      avgPerYear: parseFloatMaybe(headline?.[2]),
      winRatePct: parseFloatMaybe(headline?.[3]),
      avgValuePct: parseFloatMaybe(headline?.[4]),
      flatRoiPct: parseFloatMaybe(flat?.[1]),
      tierStaked: parseFloatMaybe(tier?.[1]),
      tierPnL: parseFloatMaybe(tier?.[2]),
      tierRoiPct: parseFloatMaybe(tier?.[3]),
      years: yearMatches.map((yearMatch) => ({
        year: yearMatch[1],
        bets: parseIntMaybe(yearMatch[2]),
        tierRoiPct: parseFloatMaybe(yearMatch[3]),
      })),
    };
  });
}

function perfValue(row: CsvRow | undefined, key: string, parser: (value?: string) => number | undefined) {
  return parser(row?.[key]);
}

function MonitorCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function Stat({
  label,
  value,
  tone = "text-slate-100",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function FileStamp({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
      <span className="text-slate-500">{label}</span> {value ?? "missing"}
    </div>
  );
}

export default async function ModelMonitorPage() {
  const [
    strictPerfCsv,
    volumePerfCsv,
    clvAuditTxt,
    profileTxt,
    shadowComparisonTxt,
    strictPerfMtime,
    volumePerfMtime,
    clvAuditMtime,
    profileMtime,
  ] = await Promise.all([
    readLocalFile("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalFile("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalFile("data/backtest/strict-clv-audit-2026.txt"),
    readLocalFile("data/backtest/policy-profile-backtest-2022-2025.txt"),
    readLocalFile("data/backtest/shadow-profile-comparison.txt"),
    readLocalMtime("data/backtest/strict-policy-performance-weekly.csv"),
    readLocalMtime("data/backtest/strict-policy-performance-volume200-weekly.csv"),
    readLocalMtime("data/backtest/strict-clv-audit-2026.txt"),
    readLocalMtime("data/backtest/policy-profile-backtest-2022-2025.txt"),
  ]);

  const strictRows = strictPerfCsv ? parseCsv(strictPerfCsv) : [];
  const volumeRows = volumePerfCsv ? parseCsv(volumePerfCsv) : [];
  const strictBase = parsePerf(strictRows, "base");
  const strictOverlay = parsePerf(strictRows, "overlay");
  const volumeBase = parsePerf(volumeRows, "base");
  const clv = parseClvAudit(clvAuditTxt);
  const profiles = parsePolicyProfiles(profileTxt);
  const profileMap = new Map(profiles.map((profile) => [profile.name, profile]));

  const strictAllRoi = perfValue(strictBase.combinedAll, "roi_pct", parseFloatMaybe);
  const volumeAllRoi = perfValue(volumeBase.combinedAll, "roi_pct", parseFloatMaybe);
  const strictWindowRoi = perfValue(strictBase.combinedWindow, "roi_pct", parseFloatMaybe);
  const overlayAllRoi = perfValue(strictOverlay.combinedAll, "roi_pct", parseFloatMaybe);
  const matchedMl = clv.matchedMl ?? 0;
  const auditedMl = clv.matchedMlTotal ?? clv.settledMlAudited ?? 0;
  const strictAsOf = strictBase.combinedAll?.as_of_date;
  const volumeAsOf = volumeBase.combinedAll?.as_of_date;
  const shadowProfile = profileMap.get("volume_200");
  const legacyShadowProfile = profileMap.get("volume_275");
  const missingReports = [
    !strictPerfCsv ? "strict weekly performance" : null,
    !volumePerfCsv ? "volume_200 weekly performance" : null,
    !clvAuditTxt ? "CLV audit" : null,
    !profileTxt ? "policy profile backtest" : null,
  ].filter(Boolean) as string[];
  const strictDiagnosis =
    strictAllRoi == null
      ? "Strict live has no settled ROI yet."
      : strictAllRoi < 0
        ? `Strict live control is negative at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`
        : `Strict live control is positive at ${formatPct(strictAllRoi)} as of ${strictAsOf ?? "n/a"}.`;
  const shadowDiagnosis =
    perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) === 0
      ? "Volume 200 shadow has no settled sample yet."
      : `Volume 200 shadow has settled enough to start comparing against strict on live results.`;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.10),_transparent_22%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href="/fair-odds" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Fair Odds
          </Link>
          <Link href="/" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Home
          </Link>
        </div>

        <section className="mb-8 overflow-hidden rounded-3xl border border-slate-800 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(15,23,42,0.92)_40%,rgba(244,63,94,0.08))] p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                Model Monitor
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Live control, shadow policy, CLV coverage, and historical edge in one place.</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                This page reads the generated report files directly. On localhost it reflects your latest local pipeline runs. On Vercel it only updates when those files are deployed.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <FileStamp label="Strict perf" value={strictPerfMtime} />
              <FileStamp label="Shadow perf" value={volumePerfMtime} />
              <FileStamp label="CLV audit" value={clvAuditMtime} />
              <FileStamp label="Profile backtest" value={profileMtime} />
            </div>
          </div>
        </section>

        {missingReports.length > 0 ? (
          <section className="mb-8 rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            Reports not found for: <span className="font-semibold">{missingReports.join(", ")}</span>. Run the daily/weekly pipeline locally or deploy fresh report files.
          </section>
        ) : null}

        <div className="mb-3 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Quick View</h2>
            <p className="mt-1 text-sm text-slate-400">At-a-glance metrics. Detailed live breakdown sits below.</p>
          </div>
        </div>

        <div className="mb-8 grid gap-4 lg:grid-cols-4">
          <MonitorCard title="Strict Live Control" subtitle={`Hard | Masters 1000 | high | public >=10%${strictAsOf ? ` | as of ${strictAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="All-time ROI" value={formatPct(strictAllRoi)} tone={metricTone(strictAllRoi)} />
              <Stat label="7d ROI" value={formatPct(strictWindowRoi)} tone={metricTone(strictWindowRoi)} />
              <Stat label="Settled" value={`${perfValue(strictBase.combinedAll, "settled", parseIntMaybe) ?? 0}`} />
              <Stat label="W-L" value={`${perfValue(strictBase.combinedAll, "wins", parseIntMaybe) ?? 0}-${perfValue(strictBase.combinedAll, "losses", parseIntMaybe) ?? 0}`} />
            </div>
          </MonitorCard>

          <MonitorCard title="Volume 200 Shadow" subtitle={`Active shadow profile, ML + spread tracked together${volumeAsOf ? ` | as of ${volumeAsOf}` : ""}`}>
            <div className="grid gap-3">
              <Stat label="All-time ROI" value={formatPct(volumeAllRoi)} tone={metricTone(volumeAllRoi)} />
              <Stat label="Signals" value={`${perfValue(volumeBase.combinedAll, "signals", parseIntMaybe) ?? 0}`} />
              <Stat label="Unsettled" value={`${perfValue(volumeBase.combinedAll, "unsettled", parseIntMaybe) ?? 0}`} />
              <Stat label="Avg Value" value={formatPct(perfValue(volumeBase.combinedAll, "avg_value_pct", parseFloatMaybe))} tone="text-amber-300" />
            </div>
          </MonitorCard>

          <MonitorCard title="CLV Audit" subtitle="Strict ML rows only. History first, Tennis-Data fallback second.">
            <div className="grid gap-3">
              <Stat label="Matched ML" value={`${matchedMl}/${auditedMl || 0}`} tone={matchedMl > 0 ? "text-emerald-300" : "text-amber-300"} />
              <Stat label="History Rows" value={`${clv.historyRows ?? 0}`} />
              <Stat label="Signal Range" value={clv.signalDateRange ?? "n/a"} tone="text-slate-300" />
              <Stat label="Close Range" value={clv.closingDateRange ?? "n/a"} tone="text-slate-300" />
            </div>
          </MonitorCard>

          <MonitorCard title="Historical Summary" subtitle="Exact policy-profile backtest from current CSV outputs">
            <div className="grid gap-3">
              <Stat label="Strict Tier ROI" value={formatPct(profileMap.get("strict")?.tierRoiPct)} tone={metricTone(profileMap.get("strict")?.tierRoiPct)} />
              <Stat label="Vol200 Tier ROI" value={formatPct(profileMap.get("volume_200")?.tierRoiPct)} tone={metricTone(profileMap.get("volume_200")?.tierRoiPct)} />
              <Stat label="Vol200 Bets/Yr" value={`${profileMap.get("volume_200")?.avgPerYear?.toFixed(1) ?? "n/a"}`} />
              <Stat label="Vol275 Bets/Yr" value={`${profileMap.get("volume_275")?.avgPerYear?.toFixed(1) ?? "n/a"}`} />
            </div>
          </MonitorCard>
        </div>

        <div className="mb-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <MonitorCard title="Live Performance Detail" subtitle="Current weekly settlement reports with ML vs spread split">
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Strict Base</h3>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${strictAllRoi != null && strictAllRoi < 0 ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/15 text-emerald-300"}`}>
                    control
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="All-time ROI" value={formatPct(strictAllRoi)} tone={metricTone(strictAllRoi)} />
                  <Stat label="7d ROI" value={formatPct(strictWindowRoi)} tone={metricTone(strictWindowRoi)} />
                  <Stat label="All-time P/L" value={formatUnits(perfValue(strictBase.combinedAll, "pnl_units", parseFloatMaybe))} tone={metricTone(perfValue(strictBase.combinedAll, "pnl_units", parseFloatMaybe))} />
                  <Stat label="Win Rate" value={formatPct(perfValue(strictBase.combinedAll, "win_rate_pct", parseFloatMaybe))} tone="text-slate-100" />
                  <Stat label="ML ROI" value={formatPct(perfValue(strictBase.mlAll, "roi_pct", parseFloatMaybe))} tone={metricTone(perfValue(strictBase.mlAll, "roi_pct", parseFloatMaybe))} />
                  <Stat label="Spread ROI" value={formatPct(perfValue(strictBase.handicapAll, "roi_pct", parseFloatMaybe))} tone={metricTone(perfValue(strictBase.handicapAll, "roi_pct", parseFloatMaybe))} />
                </div>
              </div>

              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">Volume 200 Shadow</h3>
                  <span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs font-semibold text-amber-300">shadow</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="All-time ROI" value={formatPct(volumeAllRoi)} tone={metricTone(volumeAllRoi)} />
                  <Stat label="Signals" value={`${perfValue(volumeBase.combinedAll, "signals", parseIntMaybe) ?? 0}`} />
                  <Stat label="Settled" value={`${perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) ?? 0}`} />
                  <Stat label="Unsettled" value={`${perfValue(volumeBase.combinedAll, "unsettled", parseIntMaybe) ?? 0}`} />
                  <Stat label="ML Signals" value={`${perfValue(volumeBase.mlAll, "signals", parseIntMaybe) ?? 0}`} />
                  <Stat label="Spread Signals" value={`${perfValue(volumeBase.handicapAll, "signals", parseIntMaybe) ?? 0}`} />
                </div>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Overlay reference</div>
                <div className={`text-2xl font-semibold ${metricTone(overlayAllRoi)}`}>{formatPct(overlayAllRoi)}</div>
                <p className="mt-2 text-sm text-slate-400">
                  {overlayAllRoi == null
                    ? "Overlay comparison has no settled ROI yet."
                    : `Overlay all-time ROI is ${formatPct(overlayAllRoi)} as of ${strictOverlay.combinedAll?.as_of_date ?? "n/a"}. Keep it as context, not as production proof.`}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Current diagnosis</div>
                <ul className="space-y-2 text-sm leading-6 text-slate-300">
                  <li>{strictDiagnosis}</li>
                  <li>{shadowDiagnosis}</li>
                  <li>
                    Historical exact profiles still favor <span className="font-semibold text-amber-300">volume_200</span>, but live promotion is not justified until shadow settles and CLV coverage overlaps the sample.
                  </li>
                </ul>
              </div>
            </div>
          </MonitorCard>

          <MonitorCard title="CLV Coverage" subtitle="This decides whether live-vs-backtest drift can be diagnosed cleanly">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Stat label="Strict Rows" value={`${clv.rawRows ?? 0}`} />
                <Stat label="Settled ML Audited" value={`${clv.settledMlAudited ?? 0}`} />
                <Stat label="Matched ML" value={`${matchedMl}/${auditedMl || 0}`} tone={matchedMl > 0 ? "text-emerald-300" : "text-amber-300"} />
                <Stat label="History Captures" value={`${clv.historyRows ?? 0}`} />
              </div>
              <div className="mt-4 space-y-2 text-sm text-slate-300">
                <p><span className="text-slate-500">Signals:</span> {clv.signalDateRange ?? "n/a"}</p>
                <p><span className="text-slate-500">Settled matches:</span> {clv.matchDateRange ?? "n/a"}</p>
                <p><span className="text-slate-500">Tennis-Data close range:</span> {clv.closingDateRange ?? "n/a"}</p>
              </div>
              <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4 text-sm leading-6 text-amber-100">
                {clv.warning ?? "No CLV coverage warning present."}
              </div>
            </div>
          </MonitorCard>
        </div>

        <MonitorCard title="Historical Policy Profiles Detail" subtitle="Exact 2022-2025 ATP ML-only backtest from generated backtest CSVs">
          <div className="grid gap-4 lg:grid-cols-3">
            {profiles.map((profile) => (
              <div key={profile.name} className="rounded-2xl border border-slate-800 bg-slate-950/35 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white">{profile.name}</h3>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${profile.name === "volume_200" ? "bg-amber-500/15 text-amber-300" : "bg-slate-800 text-slate-300"}`}>
                    {profile.name === "volume_200" ? "active shadow" : "reference"}
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stat label="Tier ROI" value={formatPct(profile.tierRoiPct)} tone={metricTone(profile.tierRoiPct)} />
                  <Stat label="Flat ROI" value={formatPct(profile.flatRoiPct)} tone={metricTone(profile.flatRoiPct)} />
                  <Stat label="Bets" value={`${profile.bets ?? 0}`} />
                  <Stat label="Avg / Year" value={profile.avgPerYear?.toFixed(1) ?? "n/a"} />
                  <Stat label="Tier P/L" value={formatUnits(profile.tierPnL)} tone={metricTone(profile.tierPnL)} />
                  <Stat label="Tier Staked" value={profile.tierStaked != null ? `${profile.tierStaked.toFixed(2)}u` : "n/a"} />
                </div>
                <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
                  <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">By year</div>
                  <div className="space-y-2 text-sm">
                    {profile.years.map((year) => (
                      <div key={year.year} className="flex items-center justify-between gap-4">
                        <span className="text-slate-300">{year.year}</span>
                        <span className="text-slate-500">{year.bets ?? 0} bets</span>
                        <span className={metricTone(year.tierRoiPct)}>{formatPct(year.tierRoiPct)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </MonitorCard>

        <div className="mt-8 grid gap-6 xl:grid-cols-2">
          <MonitorCard title="Shadow Decision Summary" subtitle="Compact read, with raw comparison available on demand">
            <div className="space-y-4 text-sm leading-6 text-slate-300">
              <ul className="space-y-2">
                <li>
                  Active shadow candidate: <span className="font-semibold text-amber-300">volume_200</span>
                  {shadowProfile?.tierRoiPct != null && shadowProfile?.avgPerYear != null
                    ? ` (${formatPct(shadowProfile.tierRoiPct)} tier ROI, ${shadowProfile.avgPerYear.toFixed(1)} bets/year historical).`
                    : "."}
                </li>
                <li>
                  Legacy comparison: <span className="font-semibold text-slate-100">volume_275</span>
                  {legacyShadowProfile?.tierRoiPct != null && legacyShadowProfile?.avgPerYear != null
                    ? ` (${formatPct(legacyShadowProfile.tierRoiPct)} tier ROI, ${legacyShadowProfile.avgPerYear.toFixed(1)} bets/year historical).`
                    : "."}
                </li>
                <li>
                  Live volume_200 tracking: {perfValue(volumeBase.combinedAll, "signals", parseIntMaybe) ?? 0} signals, {perfValue(volumeBase.combinedAll, "settled", parseIntMaybe) ?? 0} settled, {formatPct(volumeAllRoi)} ROI.
                </li>
              </ul>
              <details className="rounded-xl border border-slate-800 bg-slate-950/35 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-200">Show raw comparison report</summary>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-slate-400">{shadowComparisonTxt ?? "Missing shadow comparison report."}</pre>
              </details>
            </div>
          </MonitorCard>
          <MonitorCard title="Practical Use" subtitle="What this page means operationally">
            <div className="space-y-4 text-sm leading-6 text-slate-300">
              <p>
                <span className="font-semibold text-slate-100">Localhost:</span> this page reflects the report files produced by your daily and weekly jobs.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Vercel:</span> this page only updates when the report files in the repo are deployed. It is not yet a true live monitor in production.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Next clean upgrade:</span> move the monitor metrics into Supabase so this page can be real-time without redeploys.
              </p>
              <p>
                <span className="font-semibold text-slate-100">Current interpretation:</span> strict live control is negative, shadow is too young, and CLV diagnosis is blocked by missing overlap from historical close data. Your own Pinnacle history capture is now the right path to fix that.
              </p>
            </div>
          </MonitorCard>
        </div>
      </div>
    </div>
  );
}
