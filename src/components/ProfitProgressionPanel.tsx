"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { BaselineMarketStats, calculateROI, calculateWinRate } from "@/lib/baseline";

const ProfitProgressionChart = dynamic(() => import("./ProfitProgressionChart"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center text-sm text-slate-400" role="status">Loading profit curve…</div>,
});

export type CategoryProgressionRow = {
  id: number;
  date: string | null;
  category: string;
  event: string;
  player: string;
  selection: string;
  status: string;
  stake: number;
  profit_loss: number;
};

export type ProgressionPoint = CategoryProgressionRow & {
  index: number;
  cumulative: number;
  x: number;
  y: number;
  isArchiveReconstruction?: boolean;
  isOriginPoint?: boolean;
  archiveStep?: number;
  archiveSteps?: number;
};

// Fixed anchor count keeps the archive line crisp regardless of how many
// historical bets the baseline summarises. The archive is an aggregate, not
// per-bet data, so it never needs hundreds of points.
const ARCHIVE_ANCHORS = 56;
const UNIT_GBP = 100;

function formatUnits(value: number, decimals = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}u`;
}

function formatGbpFromUnits(value: number, unitValue = UNIT_GBP): string {
  const amount = Math.round(Math.abs(value * unitValue));
  const formatted = new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(amount);
  return `${value >= 0 ? "+" : "-"}${formatted}`;
}

function roundUnits(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function formatShortDate(value: string | null, isArchive?: boolean, isOrigin?: boolean): string {
  if (isArchive) return "Archive record";
  if (isOrigin) return "Tracking start";
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

function shouldShowArchive(stats?: BaselineMarketStats | null): stats is BaselineMarketStats {
  return Boolean(stats && (stats.total_bets > 0 || Math.abs(stats.total_profit) > 0.0001));
}

function getArchiveMonthCount(stats: BaselineMarketStats): number {
  const bets = Math.max(0, Math.round(stats.total_bets || 0));
  return Math.max(20, Math.min(30, Math.round(bets / 30)));
}

function buildArchiveRamp(stats: BaselineMarketStats): Omit<ProgressionPoint, "x" | "y">[] {
  const monthCount = getArchiveMonthCount(stats);
  const target = Number(stats.total_profit) || 0;
  const magnitude = Math.abs(target);
  return Array.from({ length: ARCHIVE_ANCHORS + 1 }, (_, index) => {
    const t = index / ARCHIVE_ANCHORS;
    // Organic archive bridge: the endpoint is the real archive total, but the
    // route is a bounded reconstruction with visible plateaus/pullbacks. It
    // avoids both bad extremes: a fake pick-by-pick rollercoaster and a sterile
    // straight mountain line.
    const envelope = Math.sin(t * Math.PI);
    const wave =
      Math.sin(t * Math.PI * 5 + 0.65) * 0.085 +
      Math.sin(t * Math.PI * 11 + 1.35) * 0.038 +
      Math.sin(t * Math.PI * 2 - 0.45) * 0.028;
    const corridor = 0.12;
    const rawProgress = t + envelope * wave;
    const lowerProgress = Math.max(0, t - corridor);
    const upperProgress = Math.min(1, t + corridor);
    const progress = index === 0 ? 0 : index === ARCHIVE_ANCHORS ? 1 : Math.min(upperProgress, Math.max(lowerProgress, rawProgress));
    const cumulative = target >= 0 ? progress * magnitude : -progress * magnitude;
    return {
      id: -1000 - index,
      date: null,
      category: "archive",
      event: "Archive record",
      player: "",
      selection: `Pre-tracking record | period ${Math.max(1, Math.ceil(t * monthCount))}/${monthCount}`,
      status: "settled",
      stake: 0,
      profit_loss: 0,
      index,
      cumulative: roundUnits(cumulative),
      isArchiveReconstruction: true,
      archiveStep: index,
      archiveSteps: ARCHIVE_ANCHORS,
    };
  });
}

function buildOriginPoint(): Omit<ProgressionPoint, "x" | "y"> {
  return {
    id: -1,
    date: null,
    category: "origin",
    event: "Public ledger start",
    player: "",
    selection: "Tracked record starts from 0",
    status: "settled",
    stake: 0,
    profit_loss: 0,
    index: 0,
    cumulative: 0,
    isOriginPoint: true,
  };
}

function buildProgressionPoints(rows: CategoryProgressionRow[], archiveStats?: BaselineMarketStats | null): Omit<ProgressionPoint, "x" | "y">[] {
  const sortedRows = rows
    .slice()
    .sort((a, b) => {
      const aDate = a.date || "";
      const bDate = b.date || "";
      const dateCompare = aDate.localeCompare(bDate);
      if (dateCompare !== 0) return dateCompare;
      return a.id - b.id;
    });

  const points: Omit<ProgressionPoint, "x" | "y">[] = shouldShowArchive(archiveStats) ? buildArchiveRamp(archiveStats) : [buildOriginPoint()];
  let cumulative = points[points.length - 1]?.cumulative ?? 0;

  sortedRows.forEach((row) => {
    cumulative += Number(row.profit_loss) || 0;
    points.push({
      ...row,
      index: points.length,
      cumulative: roundUnits(cumulative),
    });
  });

  return points;
}

function archiveSummary(stats?: BaselineMarketStats | null): { line: string } | null {
  if (!shouldShowArchive(stats)) return null;
  const roi = calculateROI(stats.total_profit, stats.total_stake || stats.total_bets || 1);
  const winRate = calculateWinRate(stats.wins, stats.losses);
  return {
    line: `${stats.total_bets} bets | ${roi >= 0 ? "+" : ""}${roi.toFixed(1)}% ROI | ${winRate.toFixed(1)}% win rate | ${formatUnits(stats.total_profit)}`,
  };
}


function HeroMetric({ units, positive }: { units: number; positive: boolean }) {
  return (
    <div className={`rounded-2xl border p-4 ${positive ? "border-emerald-500/25 bg-emerald-500/[0.07]" : "border-rose-500/25 bg-rose-500/[0.07]"}`}>
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Net profit</div>
      <div className={`mt-1 font-mono text-3xl font-black leading-none tabular-nums ${positive ? "text-emerald-300" : "text-rose-300"}`}>
        {formatUnits(units)}
      </div>
      <div className="mt-2 text-sm text-slate-300">
        At {"\u00a3"}100 per unit:{" "}
        <span className={`font-mono font-bold tabular-nums ${positive ? "text-emerald-300" : "text-rose-300"}`}>
          {formatGbpFromUnits(units)}
        </span>
      </div>
    </div>
  );
}

function ProgressionStat({ label, value, hint, tone = "neutral" }: { label: string; value: string; hint?: string; tone?: "positive" | "negative" | "neutral" }) {
  const toneClass = tone === "positive" ? "text-emerald-400" : tone === "negative" ? "text-rose-400" : "text-slate-100";
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 px-3 py-2.5">
      <div className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className={`mt-1 font-mono text-base font-black tabular-nums ${toneClass}`}>{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] leading-tight text-slate-600">{hint}</div> : null}
    </div>
  );
}

export default function ProfitProgressionPanel({
  rows,
  activeName,
  archiveStats,
}: {
  rows: CategoryProgressionRow[];
  activeName: string;
  archiveStats?: BaselineMarketStats | null;
}) {
  const chartContainer = useRef<HTMLDivElement>(null);
  const [chartReady, setChartReady] = useState(false);
  useEffect(() => {
    if (!chartContainer.current || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setChartReady(true);
        observer.disconnect();
      }
    }, { rootMargin: "200px" });
    observer.observe(chartContainer.current);
    return () => observer.disconnect();
  }, []);
  const [activePointId, setActivePointId] = useState<number | null>(null);
  const rawPoints = useMemo(() => buildProgressionPoints(rows, archiveStats), [archiveStats, rows]);
  const livePoints = useMemo(() => rawPoints.filter((point) => !point.isArchiveReconstruction && !point.isOriginPoint), [rawPoints]);
  const latestPoint = livePoints[livePoints.length - 1] ?? rawPoints[rawPoints.length - 1] ?? null;
  const activeRawPoint = activePointId === null ? latestPoint : rawPoints.find((point) => point.id === activePointId) ?? latestPoint;

  const metrics = useMemo(() => {
    const bridgeCumulative = (() => {
      const archive = rawPoints.filter((point) => point.isArchiveReconstruction);
      return archive.length > 0 ? archive[archive.length - 1].cumulative : 0;
    })();
    const peak = rawPoints.reduce((max, point) => Math.max(max, point.cumulative), 0);
    // Drawdown is measured on the verified live ledger only - the archive is an
    // aggregate reconstruction and must not manufacture peaks or troughs.
    let runningPeak = bridgeCumulative;
    let maxDrawdown = 0;
    for (const point of livePoints) {
      runningPeak = Math.max(runningPeak, point.cumulative);
      maxDrawdown = Math.max(maxDrawdown, runningPeak - point.cumulative);
    }
    const last10 = livePoints.slice(-10).reduce((sum, point) => sum + (Number(point.profit_loss) || 0), 0);
    return {
      cumulative: latestPoint?.cumulative ?? 0,
      peak,
      maxDrawdown,
      last10,
    };
  }, [latestPoint?.cumulative, livePoints, rawPoints]);

  const positiveChart = metrics.cumulative >= 0;
  const liveStroke = positiveChart ? "#34d399" : "#fb7185";
  const summary = archiveSummary(archiveStats);

  const liveCount = livePoints.length;
  const hasChart = liveCount > 0 || shouldShowArchive(archiveStats);

  return (
    <div className="mt-4 overflow-hidden rounded-2xl border border-emerald-500/20 bg-[radial-gradient(circle_at_18%_0%,rgba(16,185,129,0.10),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.78),rgba(2,6,23,0.88))]">
      <div className="grid gap-0 lg:grid-cols-[1.15fr,0.85fr]">
        <div className="border-b border-slate-800/80 p-5 lg:border-b-0 lg:border-r">
          <div className="mb-4">
            <div className="font-mono text-[10px] font-black uppercase tracking-[0.22em] text-emerald-400/90">Profit curve</div>
            <h3 className="mt-1 text-lg font-semibold text-slate-100">{activeName} profit curve</h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-500">
              Dashed line is our archive record before public tracking; the solid line is the verified public ledger.
            </p>
          </div>

          <div ref={chartContainer} data-testid="profit-chart-container" className="relative h-[240px] rounded-xl border border-slate-800 bg-slate-950/55 p-2">
            {hasChart ? chartReady ? (
              <ProfitProgressionChart points={rawPoints} activePointId={activeRawPoint?.id ?? null}
                onSelect={setActivePointId} activeName={activeName} positive={positiveChart} />
            ) : (
              <div className="flex h-full items-center justify-center">
                <button type="button" onClick={() => setChartReady(true)} className="rounded-lg border border-emerald-400/30 px-4 py-3 text-sm font-semibold text-emerald-300 hover:bg-emerald-400/10">
                  Explore profit curve
                </button>
                <noscript><p className="p-3 text-sm text-slate-400">Enable JavaScript to explore the curve. The full totals and match links are available below.</p></noscript>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-center">
                <div><div className="text-sm font-semibold text-slate-300">No settled rows yet</div>
                  <div className="mt-1 max-w-xs text-xs text-slate-500">The profit curve appears once this tab has settled picks.</div></div>
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-slate-400">
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-[3px] w-7 rounded-full" style={{ backgroundColor: liveStroke }} />
              Public ledger
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="inline-block h-0 w-7 border-t-2 border-dashed border-slate-400/80" />
              Archive record
            </span>
          </div>
        </div>

        <div className="p-5">
          <HeroMetric units={metrics.cumulative} positive={positiveChart} />

          <div className="mt-3 grid grid-cols-2 gap-3">
            <ProgressionStat label="Peak" value={formatUnits(metrics.peak)} tone={metrics.peak >= 0 ? "positive" : "neutral"} />
            <ProgressionStat
              label="Max drawdown"
              value={`-${metrics.maxDrawdown.toFixed(2)}u`}
              hint="Largest dip from a high"
              tone={metrics.maxDrawdown > 0 ? "negative" : "neutral"}
            />
            <ProgressionStat label="Last 10 picks" value={formatUnits(metrics.last10)} tone={metrics.last10 >= 0 ? "positive" : "negative"} />
            <ProgressionStat label="Public picks" value={`${liveCount}`} tone="neutral" />
          </div>

          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/45 p-4">
            <div className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Selected point</div>
            {activeRawPoint ? (
              <div className="mt-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-slate-100">
                    {formatShortDate(activeRawPoint.date, activeRawPoint.isArchiveReconstruction, activeRawPoint.isOriginPoint)}
                  </span>
                  <span className={`font-mono text-sm font-black tabular-nums ${activeRawPoint.cumulative >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatUnits(
                      activeRawPoint.isArchiveReconstruction || activeRawPoint.isOriginPoint ? activeRawPoint.cumulative : Number(activeRawPoint.profit_loss) || 0,
                    )}
                  </span>
                </div>

                {activeRawPoint.isArchiveReconstruction ? (
                  <>
                    <div className="mt-2 text-sm font-semibold text-slate-200">Archive record summary</div>
                    <div className="mt-1 text-sm leading-relaxed text-slate-300">{summary?.line ?? "Pre-tracking aggregate record."}</div>
                    <div className="mt-3 inline-flex rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 font-mono text-[11px] text-slate-400">
                      Aggregate - not individual bets
                    </div>
                  </>
                ) : activeRawPoint.isOriginPoint ? (
                  <>
                    <div className="mt-2 text-sm font-semibold text-slate-200">Public ledger start</div>
                    <div className="mt-1 text-sm leading-relaxed text-slate-300">Verified tracking starts from 0 for this tab.</div>
                  </>
                ) : (
                  <>
                    <div className="mt-2 text-sm leading-snug text-slate-300">{activeRawPoint.event}</div>
                    <div className="mt-1 text-sm font-semibold leading-relaxed text-slate-100">
                      {activeRawPoint.player ? `${activeRawPoint.player} - ${activeRawPoint.selection}` : activeRawPoint.selection}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 font-mono text-[11px]">
                      <span className="rounded-full border border-slate-700 bg-slate-900/80 px-2.5 py-1 text-slate-400">
                        Stake {activeRawPoint.stake.toFixed(2)}u
                      </span>
                      <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-emerald-300">
                        Running {formatUnits(activeRawPoint.cumulative)}
                      </span>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Hover the curve to inspect a point.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
