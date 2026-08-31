"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import MarginBenchmarkStrip from "@/components/bookmakers/MarginBenchmarkStrip";
import MarginMatrix from "@/components/bookmakers/MarginMatrix";
import MarginRowList from "@/components/bookmakers/MarginRowList";
import MarginTable from "@/components/bookmakers/MarginTable";
import {
  deriveSegmentStats,
  sortMarginRows,
  type MarginSortKey,
  type SortDirection,
} from "@/components/bookmakers/segment-stats";
import {
  capturedLabel,
  confidenceLabel,
  type BookmakerMarginIndex,
  type MarginSegment,
  type NotMeasuredMarket,
} from "@/lib/bookmakers/margin-index";

type MarginExplorerProps = {
  generatedAt: string | null;
  segments: MarginSegment[];
  notMeasured: NotMeasuredMarket[];
  coverage?: BookmakerMarginIndex["coverage"];
  summary?: BookmakerMarginIndex["summary"];
};

const SPORT_ORDER = ["football", "tennis"] as const;
const SPORT_LABELS: Record<string, string> = {
  football: "Football",
  tennis: "Tennis",
};
const DEFAULT_VISIBLE_ROWS = 8;

function marketId(segment: MarginSegment) {
  return segment.market_family.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function SportGlyph({ sport }: { sport: string }) {
  if (sport === "tennis") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current">
        <circle cx="12" cy="12" r="8.25" strokeWidth="1.7" />
        <path d="M6.4 6.4c3.9 2.1 5.1 7.7 2.1 11.2M17.6 17.6c-3.9-2.1-5.1-7.7-2.1-11.2" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current">
      <circle cx="12" cy="12" r="8.25" strokeWidth="1.7" />
      <path d="m12 7.3 3 2.2-1.15 3.5h-3.7L9 9.5l3-2.2Zm-3 2.2-3.2.2m8.05 3.3 1.8 2.65m-5.5-2.65-1.8 2.65m7.3 0-.25 2.7m-7.05-2.7.25 2.7" strokeWidth="1.45" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MarginPanel({ segment }: { segment: MarginSegment }) {
  const stats = useMemo(() => deriveSegmentStats(segment), [segment]);
  const [sortKey, setSortKey] = useState<MarginSortKey>("margin");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [showAll, setShowAll] = useState(false);
  const [expandedName, setExpandedName] = useState<string | null>(null);

  const sortedRows = useMemo(
    () => stats ? sortMarginRows(stats.rows, sortKey, sortDirection) : [],
    [stats, sortKey, sortDirection],
  );
  const visibleRows = showAll ? sortedRows : sortedRows.slice(0, DEFAULT_VISIBLE_ROWS);
  const confidence = confidenceLabel(segment.events);

  if (!stats) return null;

  function handleSort(key: MarginSortKey) {
    if (key === sortKey) {
      setSortDirection((current) => current === "asc" ? "desc" : "asc");
      return;
    }
    setSortKey(key);
    setSortDirection("asc");
  }

  function toggleExpanded(name: string) {
    setExpandedName((current) => current === name ? null : name);
  }

  return (
    <section
      id={`margin-panel-${segment.sport_slug}-${marketId(segment)}`}
      role="tabpanel"
      aria-labelledby={`margin-market-${segment.sport_slug}-${marketId(segment)}`}
      tabIndex={0}
      className="rounded-3xl border border-white/[0.08] bg-[#080d12]/95 p-4 shadow-[0_28px_80px_rgba(0,0,0,0.34)] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 sm:p-5"
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300">{segment.sport} snapshot</p>
          <h3 className="mt-1.5 text-2xl font-semibold tracking-tight text-white">{segment.market_family}</h3>
          <p className="mt-1 text-sm text-slate-400">Complete fixed-odds prices only. Lower margin is better.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full border px-3 py-1.5 font-semibold ${confidence.className}`}>{confidence.label} sample</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono tabular-nums text-slate-400">
            {segment.events} events · {segment.operators.length} books
          </span>
        </div>
      </div>

      {segment.operators.length === 1 ? (
        <div className="rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] p-5">
          <p className="font-semibold text-amber-100">One book only, not a comparison</p>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
            Only one bookmaker supplied a complete price for this market. The reading is visible for transparency, but it cannot support a ranking.
          </p>
        </div>
      ) : (
        <>
          <MarginBenchmarkStrip stats={stats} />

          {segment.events < 4 && (
            <p className="mt-3 rounded-xl border border-white/[0.07] bg-white/[0.025] px-3 py-2.5 text-xs leading-5 text-slate-400">
              Snapshot depth: {segment.events} events and {segment.operators[0]?.samples ?? 0} complete price sets per book. Gaps under 0.50pp are de-emphasised at this depth.
            </p>
          )}
          {segment.operators.length <= 4 && (
            <p className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/[0.055] px-3 py-2.5 text-xs leading-5 text-amber-100">
              Limited field: only {segment.operators.length} books priced this market completely. This is not a full UK ranking.
            </p>
          )}
          {stats.spread === 0 && (
            <p className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] px-3 py-2.5 text-xs text-cyan-100">
              Every measured bookmaker returned the same margin in this capture.
            </p>
          )}

          <div className="mt-4">
            <MarginTable
              rows={visibleRows}
              stats={stats}
              expandedName={expandedName}
              onToggleExpanded={toggleExpanded}
              onSort={handleSort}
              sortKey={sortKey}
              sortDirection={sortDirection}
              marketLabel={`${segment.sport} ${segment.market_family}`}
            />
            <MarginRowList
              rows={visibleRows}
              stats={stats}
              expandedName={expandedName}
              onToggleExpanded={toggleExpanded}
              sortKey={sortKey}
              sortDirection={sortDirection}
              onSortChange={(key, direction) => {
                setSortKey(key);
                setSortDirection(direction);
              }}
            />
          </div>

          {sortedRows.length > DEFAULT_VISIBLE_ROWS && (
            <button
              type="button"
              onClick={() => setShowAll((current) => !current)}
              className="mt-3 flex min-h-11 w-full items-center justify-center rounded-xl border border-white/10 bg-white/[0.025] px-4 text-sm font-semibold text-slate-200 transition-colors hover:border-cyan-300/25 hover:bg-cyan-300/[0.05] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70"
            >
              {showAll ? "Show top 8" : `Show all ${sortedRows.length} bookmakers`}
            </button>
          )}
        </>
      )}
    </section>
  );
}

export default function MarginExplorer({ generatedAt, segments, notMeasured, coverage, summary }: MarginExplorerProps) {
  const measured = useMemo(() => segments.filter((segment) => segment.operators.length > 0), [segments]);
  const availableSports = SPORT_ORDER.filter((sport) => measured.some((segment) => segment.sport_slug === sport));
  const initialSport = availableSports[0] ?? "football";
  const initialMarket = measured.find((segment) => segment.sport_slug === initialSport);
  const [selectedSport, setSelectedSport] = useState<string>(initialSport);
  const [selectedMarket, setSelectedMarket] = useState<string>(initialMarket ? marketId(initialMarket) : "");

  useEffect(() => {
    const applyHash = () => {
      const hash = window.location.hash.replace(/^#margin-/, "");
      const match = measured.find((segment) => `${segment.sport_slug}-${marketId(segment)}` === hash);
      if (match) {
        setSelectedSport(match.sport_slug);
        setSelectedMarket(marketId(match));
      }
    };
    const initialHash = window.setTimeout(applyHash, 0);
    window.addEventListener("hashchange", applyHash);
    return () => {
      window.clearTimeout(initialHash);
      window.removeEventListener("hashchange", applyHash);
    };
  }, [measured]);

  const currentSegments = measured.filter((segment) => segment.sport_slug === selectedSport);
  const currentMissing = notMeasured.filter((market) => market.sport_slug === selectedSport);
  const activeSegment = measured.find(
    (segment) => segment.sport_slug === selectedSport && marketId(segment) === selectedMarket,
  );
  const coverageIncomplete = Boolean(coverage && coverage.payload_operators < Math.min(10, coverage.target_operators));

  function chooseMarket(segment: MarginSegment) {
    const id = marketId(segment);
    setSelectedSport(segment.sport_slug);
    setSelectedMarket(id);
    window.history.replaceState(null, "", `#margin-${segment.sport_slug}-${id}`);
  }

  function chooseSport(sport: string) {
    const first = measured.find((segment) => segment.sport_slug === sport);
    if (first) chooseMarket(first);
  }

  function moveTab(event: KeyboardEvent<HTMLButtonElement>, index: number, values: string[], choose: (value: string) => void, idPrefix: string) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? values.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + values.length) % values.length;
    const value = values[nextIndex];
    choose(value);
    document.getElementById(`${idPrefix}${value}`)?.focus();
  }

  if (measured.length === 0) {
    return (
      <section className="relative mb-12 overflow-hidden rounded-[2rem] border border-amber-300/20 bg-[#090d12] p-6 shadow-[0_30px_90px_rgba(0,0,0,0.35)] sm:p-8">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300">UK margin index</p>
        <h2 className="mt-2 text-2xl font-semibold text-white sm:text-3xl">Broad comparison pending</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
          Rankings remain hidden until at least 10 target UK bookmakers return complete, like-for-like fixed-odds prices.
        </p>
      </section>
    );
  }

  return (
    <section className="relative mb-12 overflow-hidden rounded-[2rem] border border-emerald-300/20 bg-[#070b0f] shadow-[0_34px_110px_rgba(0,0,0,0.48)]">
      <div
        className="pointer-events-none absolute inset-0 opacity-35"
        style={{
          backgroundImage: "linear-gradient(rgba(45,212,191,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,191,0.05) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "linear-gradient(to bottom, black, transparent 42%)",
        }}
        aria-hidden="true"
      />

      <div className="relative border-b border-white/[0.07] px-4 py-6 sm:px-7 sm:py-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.23em] text-emerald-300">Independent price intelligence</p>
            <h2 className="mt-2 max-w-3xl text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">What a bet costs, market by market</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">
              Compare the margin built into complete fixed-odds markets. Rankings belong to the selected market, never to a bookmaker overall.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-cyan-300/15 bg-cyan-300/10 lg:min-w-[260px]">
            <div className="bg-[#091016] px-4 py-3">
              <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Captured</p>
              <p className="mt-1 font-mono text-[11px] tabular-nums text-cyan-100">{capturedLabel(generatedAt)}</p>
            </div>
            <div className="bg-[#091016] px-4 py-3">
              <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Coverage</p>
              <p className="mt-1 font-mono text-lg font-semibold tabular-nums text-emerald-100">
                {coverage?.payload_operators ?? 0}/{coverage?.target_operators ?? 0}
              </p>
              <p className="text-[9px] text-slate-500">books returned prices</p>
            </div>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-400">
          <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1.5">{summary?.events ?? "-"} captured events</span>
          <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1.5">{availableSports.length} sports</span>
          <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1.5">{measured.length} measured markets</span>
          <span className="rounded-full border border-white/[0.08] bg-black/20 px-3 py-1.5">One-off snapshot</span>
        </div>
      </div>

      {coverageIncomplete && coverage && (
        <div className="relative border-b border-amber-300/15 bg-amber-300/[0.055] px-4 py-4 sm:px-7">
          <p className="text-sm font-semibold text-amber-100">Incomplete bookmaker coverage</p>
          <p className="mt-1 max-w-4xl text-xs leading-5 text-slate-300">
            Only {coverage.payload_operators} of {coverage.target_operators} target bookmakers returned complete prices. Rankings stay limited to the measured books.
          </p>
        </div>
      )}

      <div className="relative border-b border-white/[0.07] px-4 py-4 sm:px-7">
        <div className="flex flex-col gap-4">
          <div role="tablist" aria-label="Choose sport" className="grid grid-cols-2 gap-1.5 rounded-2xl border border-white/[0.07] bg-black/30 p-1.5 sm:w-fit sm:min-w-[300px]">
            {availableSports.map((sport, index) => {
              const active = selectedSport === sport;
              return (
                <button
                  key={sport}
                  id={`margin-sport-${sport}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls={`margin-markets-${sport}`}
                  tabIndex={active ? 0 : -1}
                  onClick={() => chooseSport(sport)}
                  onKeyDown={(event) => moveTab(event, index, [...availableSports], chooseSport, "margin-sport-")}
                  className={`flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/70 ${active ? "bg-emerald-300 text-[#04110c] shadow-[0_8px_28px_rgba(16,185,129,0.16)]" : "text-slate-400 hover:bg-white/[0.04] hover:text-white"}`}
                >
                  <SportGlyph sport={sport} />
                  {SPORT_LABELS[sport]}
                </button>
              );
            })}
          </div>

          <div id={`margin-markets-${selectedSport}`} className="min-w-0">
            <p className="mb-2 text-[9px] font-semibold uppercase tracking-[0.17em] text-slate-500">Choose market</p>
            <div className="overflow-x-auto pb-1">
              <div role="tablist" aria-label={`${SPORT_LABELS[selectedSport]} measured markets`} className="flex min-w-max gap-2">
                {currentSegments.map((segment, index) => {
                  const id = marketId(segment);
                  const active = selectedMarket === id;
                  const marketIds = currentSegments.map(marketId);
                  return (
                    <button
                      key={id}
                      id={`margin-market-${segment.sport_slug}-${id}`}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      aria-controls={`margin-panel-${segment.sport_slug}-${id}`}
                      tabIndex={active ? 0 : -1}
                      onClick={() => chooseMarket(segment)}
                      onKeyDown={(event) => moveTab(
                        event,
                        index,
                        marketIds,
                        (nextId) => {
                          const next = currentSegments.find((item) => marketId(item) === nextId);
                          if (next) chooseMarket(next);
                        },
                        `margin-market-${segment.sport_slug}-`,
                      )}
                      className={`min-h-11 snap-start rounded-xl border px-4 py-2.5 text-xs font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 ${active ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100" : "border-white/[0.08] bg-white/[0.025] text-slate-400 hover:border-white/15 hover:text-white"}`}
                    >
                      {segment.market_family}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="relative px-4 py-5 sm:px-7">
        {activeSegment && <MarginPanel key={`${activeSegment.sport_slug}-${activeSegment.market_family}`} segment={activeSegment} />}
        <MarginMatrix segments={currentSegments} sportLabel={SPORT_LABELS[selectedSport]} />

        <details className="mt-5 rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-4">
          <summary className="cursor-pointer text-xs font-semibold text-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70">
            Not measured in this snapshot ({currentMissing.length})
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {currentMissing.map((market) => (
              <div key={market.label} className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                <p className="text-xs font-semibold text-slate-300">{market.label}</p>
                <p className="mt-1 text-[11px] leading-5 text-slate-400">{market.reason}</p>
              </div>
            ))}
          </div>
        </details>
      </div>

      <div className="relative grid gap-4 border-t border-white/[0.07] bg-black/25 px-4 py-5 text-sm sm:grid-cols-3 sm:px-7">
        <div><p className="font-semibold text-slate-100">What margin means</p><p className="mt-1 leading-6 text-slate-400">The estimated slice of every £1 staked that the bookmaker keeps. Lower is better.</p></div>
        <div><p className="font-semibold text-slate-100">Why markets are missing</p><p className="mt-1 leading-6 text-slate-400">Every mutually exclusive outcome must exist at the identical line. Over-only prices are not enough.</p></div>
        <div><p className="font-semibold text-slate-100">How to read the scale</p><p className="mt-1 leading-6 text-slate-400">Bars show position inside this market only. The white tick marks its median bookmaker.</p></div>
      </div>
    </section>
  );
}
