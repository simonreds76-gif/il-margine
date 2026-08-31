"use client";

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import BookmakerLogo from "@/components/BookmakerLogo";
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
};

const SPORT_ORDER = ["football", "tennis"] as const;
const SPORT_LABELS: Record<string, string> = {
  football: "Football",
  tennis: "Tennis",
};

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

function formatMargin(value: number) {
  return `${value.toFixed(2)}%`;
}

function MarginPanel({ segment, active }: { segment: MarginSegment; active: boolean }) {
  const best = segment.operators[0]?.normalized_hold_pct ?? null;
  const confidence = confidenceLabel(segment.events);
  const thin = segment.operators.length < 2 || segment.status === "THIN_SAMPLE";

  return (
    <section
      id={`margin-panel-${segment.sport_slug}-${marketId(segment)}`}
      role="tabpanel"
      aria-labelledby={`margin-market-${segment.sport_slug}-${marketId(segment)}`}
      hidden={!active}
      className="overflow-hidden rounded-3xl border border-white/[0.08] bg-[#080d12]/90 shadow-[0_28px_80px_rgba(0,0,0,0.34)]"
    >
      <div className="flex flex-col gap-4 border-b border-white/[0.07] px-5 py-5 sm:flex-row sm:items-end sm:justify-between sm:px-7">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-300">
            {segment.sport}
          </p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
            {segment.market_family}
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Complete prices only. Cheapest bookmaker first.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full border px-3 py-1.5 font-semibold ${confidence.className}`}>
            {confidence.label} sample
          </span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono tabular-nums text-slate-400">
            {segment.events} events · {segment.observations} observations
          </span>
        </div>
      </div>

      {thin ? (
        <div className="px-5 py-8 sm:px-7">
          <div className="rounded-2xl border border-amber-300/20 bg-amber-300/[0.06] p-5">
            <p className="font-semibold text-amber-100">One book only, not a comparison</p>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Only one bookmaker supplied a complete price for this market. We show the reading for transparency, but it cannot tell you which bookmaker is cheaper.
            </p>
          </div>
          {segment.operators.map((operator) => (
            <div key={operator.name} className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4">
              <div className="flex min-w-0 items-center gap-3">
                <BookmakerLogo bookmaker={{ id: 0, name: operator.name, short_name: operator.name, affiliate_link: null, active: true }} size="sm" noLink />
                <span className="truncate font-semibold text-slate-100">{operator.name}</span>
              </div>
              <span className="font-mono text-xl font-semibold tabular-nums text-cyan-200">{formatMargin(operator.normalized_hold_pct)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="px-5 py-6 sm:px-7">
          <div className="space-y-4">
            {segment.operators.map((operator, index) => {
              const gap = best === null ? 0 : operator.normalized_hold_pct - best;
              const railWidth = Math.min(100, Math.max(4, (operator.normalized_hold_pct / 15) * 100));
              return (
                <div
                  key={operator.name}
                  className={`relative overflow-hidden rounded-2xl border p-4 sm:p-5 ${
                    index === 0
                      ? "border-emerald-300/30 bg-emerald-300/[0.055]"
                      : "border-white/[0.07] bg-white/[0.025]"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border font-mono text-xs ${
                      index === 0
                        ? "border-emerald-300/35 bg-emerald-300/10 text-emerald-200"
                        : "border-white/10 text-slate-500"
                    }`}>
                      {operator.rank}
                    </span>
                    <BookmakerLogo bookmaker={{ id: 0, name: operator.name, short_name: operator.name, affiliate_link: null, active: true }} size="sm" noLink />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <p className="truncate font-semibold text-slate-100">{operator.name}</p>
                        {index === 0 ? (
                          <span className="rounded-full bg-emerald-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-200">
                            Cheapest here
                          </span>
                        ) : (
                          <span className="text-xs font-medium text-amber-200">+{gap.toFixed(2)}pp</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">{operator.samples} complete market samples</p>
                    </div>
                    <div className="text-right">
                      <p className="font-mono text-2xl font-semibold tabular-nums text-cyan-200">
                        {formatMargin(operator.normalized_hold_pct)}
                      </p>
                      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-600">margin</p>
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="h-2 overflow-hidden rounded-full bg-slate-900 ring-1 ring-inset ring-white/[0.05]">
                      <div
                        className={`h-full rounded-full ${
                          index === 0
                            ? "bg-[linear-gradient(90deg,#10b981,#5eead4)] shadow-[0_0_18px_rgba(16,185,129,0.35)]"
                            : "bg-[linear-gradient(90deg,#164e63,#22d3ee)]"
                        }`}
                        style={{ width: `${railWidth}%` }}
                        aria-hidden="true"
                      />
                    </div>
                    <div className="mt-2 flex justify-between font-mono text-[9px] tabular-nums text-slate-700" aria-hidden="true">
                      <span>0%</span><span>5%</span><span>10%</span><span>15%</span>
                    </div>
                  </div>
                  <span className="sr-only">
                    {operator.name}, ranked {operator.rank} of {segment.operators.length}, margin {formatMargin(operator.normalized_hold_pct)}, based on {operator.samples} samples.
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

export default function MarginExplorer({ generatedAt, segments, notMeasured, coverage }: MarginExplorerProps) {
  const measured = useMemo(
    () => segments.filter((segment) => segment.operators.length > 0),
    [segments],
  );
  const availableSports = SPORT_ORDER.filter((sport) =>
    measured.some((segment) => segment.sport_slug === sport),
  );
  const initialSport = availableSports[0] ?? "football";
  const initialMarket = measured.find((segment) => segment.sport_slug === initialSport);
  const [selectedSport, setSelectedSport] = useState<string>(initialSport);
  const [selectedMarket, setSelectedMarket] = useState<string>(
    initialMarket ? marketId(initialMarket) : "",
  );

  useEffect(() => {
    const applyHash = () => {
      const hash = window.location.hash.replace(/^#margin-/, "");
      const match = measured.find(
        (segment) => `${segment.sport_slug}-${marketId(segment)}` === hash,
      );
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

  function chooseSport(sport: string) {
    const first = measured.find((segment) => segment.sport_slug === sport);
    setSelectedSport(sport);
    if (first) {
      chooseMarket(first);
    }
  }

  function chooseMarket(segment: MarginSegment) {
    const id = marketId(segment);
    setSelectedSport(segment.sport_slug);
    setSelectedMarket(id);
    window.history.replaceState(null, "", `#margin-${segment.sport_slug}-${id}`);
  }

  function handleSportKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? availableSports.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + availableSports.length) % availableSports.length;
    const nextSport = availableSports[nextIndex];
    chooseSport(nextSport);
    document.getElementById(`margin-sport-${nextSport}`)?.focus();
  }

  const currentSegments = measured.filter((segment) => segment.sport_slug === selectedSport);
  const currentMissing = notMeasured.filter((market) => market.sport_slug === selectedSport);
  const coverageIncomplete = Boolean(
    coverage && coverage.payload_operators < Math.min(10, coverage.target_operators),
  );

  if (measured.length === 0) {
    return (
      <section className="mb-12 rounded-[2rem] border border-amber-300/20 bg-amber-300/[0.045] p-6 sm:p-8">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300">Margin index</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">Awaiting a complete comparison sample</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">No market is shown until the snapshot contains at least one complete outcome set. Incomplete or over-only prices remain unpublished.</p>
      </section>
    );
  }

  return (
    <section className="relative mb-12 overflow-hidden rounded-[2rem] border border-emerald-300/20 bg-[#070b0f] shadow-[0_34px_110px_rgba(0,0,0,0.48)]">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "linear-gradient(rgba(45,212,191,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(45,212,191,0.055) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "linear-gradient(to bottom, black, transparent 68%)",
        }}
        aria-hidden="true"
      />

      <div className="relative border-b border-white/[0.07] px-5 py-6 sm:px-8 sm:py-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-300">Independent price intelligence</p>
            <h2 className="mt-3 max-w-3xl text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">
              Explore bookmaker margin by market
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">
              Lower is better for you. Every reading uses a complete set of prices from the same bookmaker, at the same line, in one dated snapshot.
            </p>
          </div>
          <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.045] px-4 py-3">
            <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-slate-500">Captured</p>
            <p className="mt-1 font-mono text-xs tabular-nums text-cyan-100">{capturedLabel(generatedAt)}</p>
            {coverage && (
              <p className="mt-1 font-mono text-[10px] tabular-nums text-slate-500">
                {coverage.payload_operators}/{coverage.target_operators} books returned prices
              </p>
            )}
          </div>
        </div>
      </div>

      {coverageIncomplete && coverage && (
        <div className="relative border-b border-amber-300/15 bg-amber-300/[0.055] px-5 py-4 sm:px-8">
          <p className="text-sm font-semibold text-amber-100">Incomplete bookmaker coverage</p>
          <p className="mt-1 max-w-4xl text-xs leading-5 text-slate-300">
            Only {coverage.payload_operators} of {coverage.target_operators} target sportsbooks returned prices in this capture. Rankings below are limited to those books and must not be read as a complete UK league table.
          </p>
        </div>
      )}

      <div className="relative px-5 py-5 sm:px-8">
        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="space-y-5">
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Sport</p>
              <div role="tablist" aria-label="Choose sport" className="grid grid-cols-2 gap-2 rounded-2xl border border-white/[0.07] bg-black/30 p-1.5 xl:grid-cols-1">
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
                      onKeyDown={(event) => handleSportKey(event, index)}
                      className={`flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/70 xl:justify-start ${
                        active
                          ? "bg-emerald-300 text-[#04110c] shadow-[0_8px_28px_rgba(16,185,129,0.18)]"
                          : "text-slate-400 hover:bg-white/[0.04] hover:text-white"
                      }`}
                    >
                      <SportGlyph sport={sport} />
                      {SPORT_LABELS[sport]}
                    </button>
                  );
                })}
              </div>
            </div>

            <div id={`margin-markets-${selectedSport}`}>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Measured markets</p>
              <div role="tablist" aria-label={`${SPORT_LABELS[selectedSport]} measured markets`} className="flex flex-wrap gap-2 xl:flex-col">
                {currentSegments.map((segment) => {
                  const id = marketId(segment);
                  const active = selectedMarket === id;
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
                      className={`min-h-11 rounded-xl border px-3 py-2 text-left text-xs font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70 ${
                        active
                          ? "border-cyan-300/35 bg-cyan-300/10 text-cyan-100"
                          : "border-white/[0.07] bg-white/[0.025] text-slate-400 hover:border-white/15 hover:text-white"
                      }`}
                    >
                      {segment.market_family}
                    </button>
                  );
                })}
              </div>
            </div>

            <details className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-4">
              <summary className="cursor-pointer text-xs font-semibold text-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70">
                Not measured yet ({currentMissing.length})
              </summary>
              <div className="mt-3 space-y-3">
                {currentMissing.map((market) => (
                  <div key={market.label}>
                    <p className="text-xs font-semibold text-slate-500">{market.label}</p>
                    <p className="mt-0.5 text-[11px] leading-5 text-slate-600">{market.reason}</p>
                  </div>
                ))}
              </div>
            </details>
          </aside>

          <div className="min-w-0">
            {measured.map((segment) => (
              <MarginPanel
                key={`${segment.sport_slug}-${segment.market_family}`}
                segment={segment}
                active={segment.sport_slug === selectedSport && marketId(segment) === selectedMarket}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="relative grid gap-4 border-t border-white/[0.07] bg-black/25 px-5 py-5 text-sm sm:grid-cols-3 sm:px-8">
        <div>
          <p className="font-semibold text-slate-100">What “margin” means</p>
          <p className="mt-1 leading-6 text-slate-500">The estimated slice of every £1 staked that the bookmaker keeps. Lower is better.</p>
        </div>
        <div>
          <p className="font-semibold text-slate-100">Why some markets are missing</p>
          <p className="mt-1 leading-6 text-slate-500">An over-only price is not enough. We need every mutually exclusive outcome at the identical line.</p>
        </div>
        <div>
          <p className="font-semibold text-slate-100">Commercially independent</p>
          <p className="mt-1 leading-6 text-slate-500">Neither Bet365 nor BetMGM is an affiliate partner. The measured ranking ignores commercial relationships.</p>
        </div>
      </div>
    </section>
  );
}

