"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { FeaturedSignalCard } from "@/components/fair-odds-lab/FeaturedSignalCard";
import { LogoBadge } from "@/components/fair-odds-lab/LogoBadge";
import { OddsComparisonBar } from "@/components/fair-odds-lab/OddsComparisonBar";
import {
  PenaltyBadge,
  TierIndicator,
} from "@/components/fair-odds-lab/primitives";
import type { LabArtifact, Signal } from "@/components/fair-odds-lab/types";

type SortMode = "edge" | "kickoff" | "confidence";

type LeagueOption = {
  key: string;
  label: string;
  count: number;
};

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function leagueKey(signal: Signal) {
  return signal.leagueSlug || slugify(signal.competition || "other");
}

function probabilityGap(signal: Signal) {
  return signal.modelProbability - signal.bookmakerProbability;
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function parseKickoff(signal: Signal) {
  const timestamp = signal.kickoffUtc ? Date.parse(signal.kickoffUtc) : Number.NaN;
  return Number.isFinite(timestamp) ? timestamp : Number.MAX_SAFE_INTEGER;
}

function confidenceRank(confidence: Signal["confidence"]) {
  if (confidence === "High") return 3;
  if (confidence === "Medium") return 2;
  return 1;
}

function compactLineupLabel(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("confirmed")) return "Confirmed";
  if (normalized.includes("projected")) return "Projected";
  if (normalized.includes("bench")) return "Bench risk";
  return "Unknown";
}

function sortSignals(signals: Signal[], sortMode: SortMode) {
  return [...signals].sort((a, b) => {
    if (sortMode === "kickoff") {
      return parseKickoff(a) - parseKickoff(b) || probabilityGap(b) - probabilityGap(a);
    }

    if (sortMode === "confidence") {
      return (
        confidenceRank(b.confidence) - confidenceRank(a.confidence) ||
        probabilityGap(b) - probabilityGap(a) ||
        parseKickoff(a) - parseKickoff(b)
      );
    }

    return probabilityGap(b) - probabilityGap(a) || parseKickoff(a) - parseKickoff(b);
  });
}

function SignalCard({
  signal,
  featured,
  selected,
  onOpen,
}: {
  signal: Signal;
  featured: boolean;
  selected: boolean;
  onOpen: () => void;
}) {
  const gap = probabilityGap(signal);

  return (
    <article
      className={`group relative min-w-0 overflow-hidden rounded-2xl border bg-[#0c0f14] p-5 transition hover:-translate-y-0.5 hover:border-emerald-300/35 hover:shadow-[0_16px_50px_rgba(16,185,129,0.1)] ${
        selected ? "border-emerald-300/60 shadow-[0_0_0_1px_rgba(52,211,153,0.12)]" : "border-slate-700/45"
      }`}
    >
      <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${signal.accent}`} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            <LogoBadge
              src={signal.leagueLogoPath}
              alt={`${signal.competition} logo`}
              fallback={signal.competition}
              size={22}
              shape="rounded"
              className="bg-white/95 p-1"
            />
            <span className="truncate">{signal.competition}</span>
          </div>
          <div className="mt-2 text-sm leading-snug text-slate-400">{signal.match}</div>
          <div className="mt-1 text-xs text-slate-600">{signal.kickoff}</div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {featured ? (
            <span className="rounded-md border border-emerald-400/25 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-200">
              Top gap
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-5">
        <OddsComparisonBar
          modelOdds={signal.fairOdds}
          bookOdds={signal.bestBookOdds}
          bookName={signal.bestBookmaker}
          gapPp={gap}
          modelProb={signal.modelProbability}
          marketProb={signal.bookmakerProbability}
          size="compact"
        />
      </div>

      <div className="mt-5 min-w-0">
        <div className="flex items-start gap-3">
          <LogoBadge
            src={signal.teamLogoPath}
            alt={`${signal.team} logo`}
            fallback={signal.team}
            size={40}
          />
          <div className="min-w-0">
            <div className="break-words text-2xl font-bold leading-tight tracking-tight text-slate-50">
              {signal.player}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {signal.team} | {signal.position} | {signal.market}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2">
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Chance
          </div>
          <div className="mt-2">
            <TierIndicator tier={signal.recentChanceQuality ?? "Average"} size="sm" />
          </div>
          <div className="mt-2 text-[10px] font-semibold text-slate-300">
            {signal.recentChanceQuality ?? "Unknown"}
          </div>
        </div>
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Lineup
          </div>
          <div className="mt-3 inline-flex rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold text-emerald-100">
            {compactLineupLabel(signal.lineupStatus)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-3">
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            Penalties
          </div>
          <div className="mt-2">
            <PenaltyBadge role={signal.penaltyRole} size="mini" />
          </div>
        </div>
      </div>

      <div className="mt-5 border-t border-slate-800/80 pt-4 text-sm text-slate-400">
        Model chance{" "}
        <span className="font-mono font-semibold text-emerald-200">
          {formatPercent(signal.modelProbability)}
        </span>{" "}
        vs market{" "}
        <span className="font-mono font-semibold text-slate-200">
          {formatPercent(signal.bookmakerProbability)}
        </span>
        .
      </div>

      <button
        type="button"
        onClick={onOpen}
        className="mt-4 inline-flex w-full items-center justify-center rounded-xl border border-slate-700/70 bg-slate-900/80 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-emerald-400/40 hover:text-emerald-200"
      >
        {selected ? "Selected" : "View details"}
      </button>
    </article>
  );
}

export function FairOddsSignalBrowser({
  artifact,
  featuredSignalId,
}: {
  artifact: LabArtifact;
  featuredSignalId?: string | null;
}) {
  const [activeLeague, setActiveLeague] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("edge");
  const [selectedId, setSelectedId] = useState<string | null>(featuredSignalId ?? null);
  const featuredRef = useRef<HTMLDivElement | null>(null);
  const liveSignals = artifact.signals;

  const leagueOptions = useMemo<LeagueOption[]>(() => {
    const counts = new Map<string, LeagueOption>();
    for (const signal of liveSignals) {
      const key = leagueKey(signal);
      const current = counts.get(key);
      if (current) {
        current.count += 1;
      } else {
        counts.set(key, { key, label: signal.competition || key, count: 1 });
      }
    }
    return [...counts.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [liveSignals]);

  const visibleSignalsFor = useCallback((league: string, sort: SortMode) => {
    const filtered =
      league === "all"
        ? liveSignals
        : liveSignals.filter((signal) => leagueKey(signal) === league);
    return sortSignals(filtered, sort);
  }, [liveSignals]);

  const visibleSignals = useMemo(
    () => visibleSignalsFor(activeLeague, sortMode),
    [activeLeague, sortMode, visibleSignalsFor],
  );
  const confidenceSortDisabled =
    new Set(visibleSignals.map((signal) => signal.confidence)).size < 2;

  const selectedSignal =
    (selectedId ? visibleSignals.find((signal) => signal.id === selectedId) : null) ??
    visibleSignals[0] ??
    null;
  const selectedIndex = selectedSignal
    ? visibleSignals.findIndex((signal) => signal.id === selectedSignal.id)
    : -1;

  function applyLeague(nextLeague: string) {
    setActiveLeague(nextLeague);
    const nextSignals = visibleSignalsFor(nextLeague, sortMode);
    setSelectedId(nextSignals[0]?.id ?? null);
  }

  function applySort(nextSort: SortMode) {
    setSortMode(nextSort);
    const nextSignals = visibleSignalsFor(activeLeague, nextSort);
    setSelectedId(nextSignals[0]?.id ?? null);
  }

  function openSignal(signal: Signal) {
    setSelectedId(signal.id);
    window.requestAnimationFrame(() => {
      featuredRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function cycleSignal(direction: 1 | -1) {
    if (!visibleSignals.length || selectedIndex < 0) return;
    const nextIndex = (selectedIndex + direction + visibleSignals.length) % visibleSignals.length;
    setSelectedId(visibleSignals[nextIndex].id);
  }

  if (liveSignals.length === 0) return null;

  return (
    <section className="mt-10">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Signal browser
          </div>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-50">
            Browse live value spots
          </h2>
        </div>
        <div className="text-sm text-slate-500">
          {artifact.isMock
            ? "Static concept data for page design."
            : "Refreshed from the latest model artifact. No live database calls."}
        </div>
      </div>

      <div className="mb-5 rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => applyLeague("all")}
              className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                activeLeague === "all"
                  ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
                  : "border-slate-700/80 bg-slate-900/70 text-slate-400 hover:text-slate-200"
              }`}
            >
              All | {liveSignals.length}
            </button>
            {leagueOptions.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => applyLeague(option.key)}
                className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                  activeLeague === option.key
                    ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
                    : "border-slate-700/80 bg-slate-900/70 text-slate-400 hover:text-slate-200"
                }`}
              >
                {option.label} | {option.count}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Sort
            </span>
            {[
              ["edge", "Edge"],
              ["kickoff", "Kickoff"],
              ["confidence", "Confidence"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => applySort(value as SortMode)}
                disabled={value === "confidence" && confidenceSortDisabled}
                title={
                  value === "confidence" && confidenceSortDisabled
                    ? "All visible signals have the same confidence tier."
                    : undefined
                }
                className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                  sortMode === value
                    ? "border-amber-400/35 bg-amber-400/10 text-amber-200"
                    : value === "confidence" && confidenceSortDisabled
                      ? "cursor-not-allowed border-slate-800/80 bg-slate-950/70 text-slate-600"
                      : "border-slate-700/80 bg-slate-900/70 text-slate-400 hover:text-slate-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {visibleSignals.length === 0 ? (
        <div className="rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-8 text-center text-sm text-slate-400">
          No signals match this league filter. Switch back to All to see the current artifact.
        </div>
      ) : (
        <div className="grid gap-6">
          {selectedSignal ? (
            <div ref={featuredRef} className="scroll-mt-24">
              <FeaturedSignalCard
                signal={selectedSignal}
                eyebrow={selectedSignal.id === featuredSignalId ? "Top value spot" : "Selected value spot"}
                controls={
                  <div className="hidden items-center gap-2 sm:flex">
                    <button
                      type="button"
                      onClick={() => cycleSignal(-1)}
                      className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1 text-xs font-semibold text-slate-400 transition hover:text-slate-100"
                    >
                      Previous
                    </button>
                    <span className="text-xs text-slate-500">
                      {selectedIndex + 1} of {visibleSignals.length}
                    </span>
                    <button
                      type="button"
                      onClick={() => cycleSignal(1)}
                      className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1 text-xs font-semibold text-slate-400 transition hover:text-slate-100"
                    >
                      Next
                    </button>
                  </div>
                }
              />
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {visibleSignals.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                featured={signal.id === featuredSignalId}
                selected={signal.id === selectedSignal?.id}
                onOpen={() => openSignal(signal)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

