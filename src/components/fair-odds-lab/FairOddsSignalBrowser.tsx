"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { AbstractJersey } from "@/components/fair-odds-lab/AbstractJersey";
import { FeaturedSignalCard } from "@/components/fair-odds-lab/FeaturedSignalCard";
import { LogoBadge } from "@/components/fair-odds-lab/LogoBadge";
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

function formatOdds(value: number) {
  return value.toFixed(2);
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
  const lineupLabel = compactLineupLabel(signal.lineupStatus);

  return (
    <article
      className={`group relative min-w-0 overflow-hidden rounded-2xl border bg-[#0b1018] p-3 transition duration-300 hover:-translate-y-0.5 hover:border-emerald-300/40 hover:shadow-[0_18px_54px_rgba(16,185,129,0.14)] sm:p-4 ${
        selected ? "border-emerald-300/70 shadow-[0_0_0_1px_rgba(52,211,153,0.18),0_24px_80px_rgba(16,185,129,0.14)]" : "border-slate-700/45"
      }`}
    >
      <div className={`absolute inset-y-0 left-0 w-1 bg-gradient-to-b ${signal.accent}`} />
      <div className="pointer-events-none absolute -right-16 top-1/2 h-28 w-28 -translate-y-1/2 rounded-full bg-emerald-300/[0.07] blur-2xl transition group-hover:bg-emerald-300/[0.12]" />

      <div className="relative grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)_auto] lg:items-center">
        <button
          type="button"
          onClick={onOpen}
          className="flex min-w-0 items-center gap-3 text-left"
        >
          <span className="w-12 shrink-0">
            <AbstractJersey
              playerNumber={signal.playerNumber}
              teamLogoPath={signal.teamLogoPath}
              teamPrimaryColor={signal.teamPrimaryColor}
              teamSecondaryColor={signal.teamSecondaryColor}
              shirtPattern={signal.teamShirtPattern}
              accentEmerald={false}
            />
          </span>
          <div className="min-w-0">
            <div className="break-words text-xl font-black leading-tight tracking-tight text-slate-50 sm:text-2xl">
              {signal.player}
            </div>
            <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
              <span className="min-w-0 truncate">{signal.match}</span>
              <span className="text-slate-700">|</span>
              <LogoBadge
                src={signal.leagueLogoPath}
                alt={`${signal.competition} logo`}
                fallback={signal.competition}
                size={18}
                shape="rounded"
                className="bg-white/95 p-0.5"
              />
              <span>{signal.kickoff}</span>
            </div>
          </div>
        </button>

        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-emerald-300/18 bg-emerald-300/[0.055] px-3 py-2">
            <div className="text-[9px] font-black uppercase tracking-[0.16em] text-emerald-200/80">
              Il Margine
            </div>
            <div className="mt-1 font-mono text-xl font-black text-emerald-100">
              {formatOdds(signal.fairOdds)}
            </div>
          </div>
          <div className="rounded-xl border border-slate-700/65 bg-slate-950/55 px-3 py-2">
            <div className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-500">
              Market
            </div>
            <div className="mt-1 font-mono text-xl font-black text-slate-100">
              {formatOdds(signal.bestBookOdds)}
            </div>
          </div>
          <div className="rounded-xl border border-amber-300/22 bg-amber-300/[0.075] px-3 py-2">
            <div className="text-[9px] font-black uppercase tracking-[0.16em] text-amber-100/80">
              Gap
            </div>
            <div className="mt-1 font-mono text-xl font-black text-amber-100">
              +{gap.toFixed(1)} pp
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          {featured ? (
            <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-emerald-200">
              Top gap
            </span>
          ) : null}
          <span className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.07] px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-cyan-100">
            {lineupLabel}
          </span>
          <span className="rounded-full border border-slate-700/70 bg-slate-950/70 px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.12em] text-slate-300">
            {signal.penaltyRole}
          </span>
          <button
            type="button"
            onClick={onOpen}
            className="rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-1.5 text-xs font-black text-emerald-100 transition hover:border-emerald-300/45 hover:bg-emerald-300/[0.1]"
          >
            {selected ? "Showing" : "Details"}
          </button>
        </div>
      </div>

      <div className="relative mt-3 text-xs leading-5 text-slate-500 lg:hidden">
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
    </article>
  );
}

export function FairOddsSignalBrowser({
  artifact,
  featuredSignalId,
  embed = false,
}: {
  artifact: LabArtifact;
  featuredSignalId?: string | null;
  embed?: boolean;
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
    <section className={`${embed ? "mt-0" : "mt-6"} rounded-[2.25rem] border border-slate-700/45 bg-[#080d14]/75 p-4 shadow-[0_28px_110px_rgba(0,0,0,0.35)] sm:p-5`}>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.22em] text-emerald-300">
            Current value spots
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-50 sm:text-4xl">
            Model price vs market price.
          </h2>
        </div>
        <div className="rounded-full border border-cyan-300/20 bg-cyan-300/[0.07] px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-100">
          {artifact.isMock
            ? "Static design data"
            : "Latest model artifact"}
        </div>
      </div>

      <div className="mb-5 rounded-2xl border border-slate-700/45 bg-[linear-gradient(135deg,rgba(15,23,42,0.9),rgba(6,18,26,0.9))] p-4">
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
                  visibleSignals.length > 1 ? (
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
                  ) : null
                }
              />
            </div>
          ) : null}

          {visibleSignals.length > 1 ? (
            <div className="grid gap-3">
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
          ) : null}
        </div>
      )}

      {embed ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/70 pt-4 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
          <span>Fair odds research module</span>
          <span className="text-emerald-200">Powered by Il Margine &middot; ilmargine.bet</span>
        </div>
      ) : null}
    </section>
  );
}

