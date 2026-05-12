import type { ReactNode } from "react";
import Link from "next/link";

import { AbstractJersey } from "@/components/fair-odds-lab/AbstractJersey";
import { LogoBadge } from "@/components/fair-odds-lab/LogoBadge";
import { OddsComparisonBar } from "@/components/fair-odds-lab/OddsComparisonBar";
import { ProbabilityGauge } from "@/components/fair-odds-lab/ProbabilityGauge";
import {
  MiniDonut,
  MinutesMeter,
  PenaltyBadge,
  PriceGapMeter,
  ProportionalBar,
  SignedBoostMeter,
  StatusSteps,
  TierIndicator,
} from "@/components/fair-odds-lab/primitives";
import type { Signal, SignalMetric } from "@/components/fair-odds-lab/types";

function formatOdds(value: number) {
  return value.toFixed(2);
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function probabilityGap(signal: Signal) {
  return signal.modelProbability - signal.bookmakerProbability;
}

function splitMatchTeams(match: string) {
  const parts = match.split(/\s+(?:vs|v)\s+/i).map((part) => part.trim()).filter(Boolean);
  return {
    home: parts[0] ?? "",
    away: parts[1] ?? "",
  };
}

function opponentFromSignal(signal: Signal) {
  const { home, away } = splitMatchTeams(signal.match);
  const normalizedTeam = signal.team.toLowerCase();
  const homeKey = home.toLowerCase();
  const awayKey = away.toLowerCase();
  if (homeKey && (homeKey.includes(normalizedTeam) || normalizedTeam.includes(homeKey))) return away;
  if (awayKey && (awayKey.includes(normalizedTeam) || normalizedTeam.includes(awayKey))) return home;
  return away || home || "Opponent";
}

function numberFromMetric(value: string) {
  const parsed = Number.parseFloat(value.replace(/[^0-9.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function renderMetricVisual(metric: SignalMetric) {
  const label = metric.label.toLowerCase();

  if (label.includes("recent chance quality")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="quality" />
      </div>
    );
  }

  if (label.includes("share of team chances")) {
    return (
      <div className="grid w-full gap-1 sm:min-w-[138px]">
        <span className="font-mono text-sm font-semibold text-slate-100 sm:text-right">
          {metric.value}
        </span>
        <ProportionalBar value={numberFromMetric(metric.value)} maxValue={50} />
      </div>
    );
  }

  if (label.includes("lineup confidence")) {
    return <StatusSteps status={metric.value} />;
  }

  if (label.includes("penalty role")) {
    return <PenaltyBadge role={metric.value} />;
  }

  if (label.includes("team attacking outlook")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="outlook" />
      </div>
    );
  }

  if (label.includes("recent team form")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="outlook" />
      </div>
    );
  }

  if (label.includes("opponent defensive weakness")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="weakness" />
      </div>
    );
  }

  if (label.includes("opponent recent defence")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="weakness" />
      </div>
    );
  }

  if (label.includes("fixture boost")) {
    return (
      <div className="grid w-full gap-1 sm:min-w-[138px]">
        <span className="font-mono text-sm font-semibold text-slate-100 sm:text-right">
          {metric.value}
        </span>
        <SignedBoostMeter value={numberFromMetric(metric.value)} />
      </div>
    );
  }

  if (label.includes("projected minutes")) {
    return (
      <div className="grid w-full gap-1 sm:min-w-[138px]">
        <span className="font-mono text-sm font-semibold text-slate-100 sm:text-right">
          {metric.value}
        </span>
        <MinutesMeter minutes={numberFromMetric(metric.value)} />
      </div>
    );
  }

  return (
    <span className="rounded-lg border border-slate-700/55 bg-slate-900/80 px-3 py-2 font-mono text-sm font-semibold text-slate-100">
      {metric.value}
    </span>
  );
}

function MetricTable({
  title,
  kicker,
  metrics,
}: {
  title: string;
  kicker: string;
  metrics: SignalMetric[];
}) {
  return (
    <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-3 sm:p-4">
      <div className="mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
          {kicker}
        </div>
        <h3 className="mt-1 text-base font-semibold text-slate-100">{title}</h3>
      </div>
      <div className="space-y-3">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-3"
          >
            <div className="min-w-0">
              <div className="text-xs font-medium text-slate-300">{metric.label}</div>
              {metric.note ? (
                <div className="mt-0.5 text-[11px] text-slate-500">{metric.note}</div>
              ) : null}
            </div>
            <div className="flex min-w-0 justify-start sm:min-w-[138px] sm:justify-end">
              {renderMetricVisual(metric)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MarketTable({ signal }: { signal: Signal }) {
  const gap = probabilityGap(signal);
  const rows = [
    {
      label: "Fair odds",
      model: formatOdds(signal.fairOdds),
      best: formatOdds(signal.bestBookOdds),
    },
    {
      label: "Implied %",
      model: formatPercent(signal.modelProbability),
      best: formatPercent(signal.bookmakerProbability),
    },
    {
      label: "Probability gap",
      model: "-",
      best: `${gap >= 0 ? "+" : ""}${gap.toFixed(1)} pp`,
    },
  ];

  return (
    <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-3 sm:p-4">
      <div className="mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
          Price panel
        </div>
        <h3 className="mt-1 text-base font-semibold text-slate-100">
          Il Margine vs Bet365 reference
        </h3>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-800/80">
        <div className="grid grid-cols-[minmax(72px,1fr)_minmax(58px,0.7fr)_minmax(86px,0.95fr)] bg-slate-900/90 text-[8px] font-semibold uppercase tracking-[0.08em] text-slate-500 sm:grid-cols-[minmax(92px,1fr)_minmax(64px,0.6fr)_minmax(118px,0.85fr)] sm:text-[10px] sm:tracking-[0.1em]">
          <div className="px-2 py-2 sm:px-3">Metric</div>
          <div className="px-2 py-2 text-right sm:px-3">Model</div>
          <div className="min-w-0 px-2 py-2 text-right sm:px-3">
            <span className="block truncate">Reference</span>
            <span className="block truncate normal-case tracking-normal text-slate-600">
              {signal.bestBookmaker}
            </span>
          </div>
        </div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-[minmax(72px,1fr)_minmax(58px,0.7fr)_minmax(86px,0.95fr)] border-t border-slate-800/75 text-xs sm:grid-cols-[minmax(92px,1fr)_minmax(64px,0.6fr)_minmax(118px,0.85fr)] sm:text-sm"
          >
            <div className="px-2 py-3 text-slate-400 sm:px-3">{row.label}</div>
            <div className="px-2 py-3 text-right font-mono text-emerald-200 tabular-nums sm:px-3">
              {row.model}
            </div>
            <div
              className={`px-2 py-3 text-right font-mono tabular-nums sm:px-3 ${
                row.label === "Probability gap" ? "text-amber-300" : "text-slate-100"
              }`}
            >
              {row.label === "Probability gap" ? (
                <div className="flex flex-col items-end gap-1">
                  <span>{row.best}</span>
                  <span className="hidden whitespace-nowrap text-[9px] font-medium normal-case tracking-normal text-slate-500 sm:inline">
                    percentage points vs market
                  </span>
                  <div className="hidden sm:block">
                    <PriceGapMeter value={gap} />
                  </div>
                </div>
              ) : (
                row.best
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeatureStrip({ signal }: { signal: Signal }) {
  const cardClass =
    "flex min-h-[96px] flex-col justify-between rounded-xl border border-slate-700/45 border-t-slate-500/45 bg-slate-900/70 p-3 sm:min-h-[126px] sm:p-4";
  const labelClass = "text-[9px] uppercase tracking-[0.16em] text-slate-500 sm:text-[10px] sm:tracking-[0.18em]";
  const valueClass = "font-mono text-lg font-black text-slate-100 sm:text-2xl";

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div className={cardClass}>
        <div className={labelClass}>Model scoring chance</div>
        <div className="flex items-center justify-between gap-3">
          <div className="font-mono text-lg font-black text-emerald-200 sm:text-2xl">
            {formatPercent(signal.modelProbability)}
          </div>
          <MiniDonut value={signal.modelProbability} />
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Recent chance quality</div>
        <div className="flex items-center justify-between gap-3">
          <div className={valueClass}>{signal.recentChanceQuality ?? "Unknown"}</div>
          <TierIndicator tier={signal.recentChanceQuality ?? "Average"} />
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Lineup status</div>
        <div>
          <div className={valueClass}>{signal.lineupStatus}</div>
          <div className="mt-3">
            <StatusSteps status={signal.lineupStatus} />
          </div>
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Penalty role</div>
        <div className="flex items-center justify-between gap-3">
          <div className={valueClass}>{signal.penaltyRole}</div>
          <PenaltyBadge role={signal.penaltyRole} />
        </div>
      </div>
    </div>
  );
}

type EdgeIconName = "boot" | "ball" | "penalty" | "defender";

const edgeIcons: EdgeIconName[] = ["boot", "ball", "penalty", "defender"];

function EdgeIcon({ name }: { name: EdgeIconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.7,
  };

  return (
    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-emerald-400/20 bg-slate-800/80 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.08)]">
      <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24">
        {name === "boot" ? (
          <path {...common} d="M4 15.5c3.5.9 6.6.6 9.4-.8l1.2-.6 2.2 2.4c.8.9 1.9 1.4 3.2 1.4H21v2H7.4c-1.8 0-3.1-.8-3.9-2.3L3 16.7l1-.9ZM6.5 5.5l4.8 8.7M10 4.5l4.5 8" />
        ) : null}
        {name === "ball" ? (
          <>
            <circle {...common} cx="12" cy="12" r="8" />
            <path {...common} d="m12 7 3.7 2.7-1.4 4.4H9.7L8.3 9.7 12 7ZM9.7 14.1 7 17.2M14.3 14.1l2.7 3.1M8.3 9.7 5 9M15.7 9.7 19 9" />
          </>
        ) : null}
        {name === "penalty" ? (
          <>
            <path {...common} d="M4 20V5h16v15" />
            <path {...common} d="M8 20v-5h8v5M12 11h.01M7 8h10" />
          </>
        ) : null}
        {name === "defender" ? (
          <>
            <path {...common} d="M12 3 5.5 5.8v5.6c0 4.2 2.6 7.5 6.5 9.6 3.9-2.1 6.5-5.4 6.5-9.6V5.8L12 3Z" />
            <path {...common} d="M9 12.2 11.2 14 15 9.8" />
          </>
        ) : null}
      </svg>
    </span>
  );
}

export function FeaturedSignalCard({
  signal,
  eyebrow = "Featured research signal",
  controls,
}: {
  signal: Signal;
  eyebrow?: string;
  controls?: ReactNode;
}) {
  const gap = probabilityGap(signal);
  const inPlayWatch = signal.displayStatus === "in_play";
  const venueLabel = signal.venue && signal.venue !== "Venue TBC" ? ` | ${signal.venue}` : "";
  const opponent = opponentFromSignal(signal);

  return (
    <article className="overflow-hidden rounded-[1.5rem] border border-emerald-300/20 bg-[#0a0f12] shadow-[0_24px_90px_rgba(16,185,129,0.12)] sm:rounded-[2rem]">
      <div className="border-b border-slate-800/90 bg-slate-950/80 px-4 py-3 sm:px-5 sm:py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
              {eyebrow}
            </div>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2 text-sm font-semibold text-slate-200">
              <LogoBadge
                src={signal.leagueLogoPath}
                alt={`${signal.competition} logo`}
                fallback={signal.competition}
                size={24}
                shape="rounded"
                className="bg-white/95 p-1"
              />
              <span className="min-w-0 break-words">
                {signal.match} <span className="text-slate-600">|</span> {signal.competition}
              </span>
            </div>
            <div className="mt-3 inline-flex max-w-full items-center gap-2 rounded-full border border-slate-800/80 bg-slate-950/60 px-3 py-1.5">
              <LogoBadge
                src={signal.teamLogoPath}
                alt={`${signal.team} logo`}
                fallback={signal.team}
                size={24}
              />
              <span className="truncate text-xs font-semibold text-slate-300">
                {signal.team}
              </span>
              <span className="shrink-0 text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                vs
              </span>
              <LogoBadge
                alt={`${opponent} logo`}
                fallback={opponent}
                size={24}
              />
              <span className="truncate text-xs font-semibold text-slate-300">
                {opponent}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {signal.kickoff}
              {venueLabel ? (
                <>
                  <span className="text-slate-700"> | </span>
                  {signal.venue}
                </>
              ) : null}
              {inPlayWatch ? (
                <>
                  <span className="text-slate-700"> | </span>
                  <span className="font-semibold text-amber-200">
                    Flagged pre-match - market closed
                  </span>
                </>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {controls}
            {inPlayWatch ? (
              <span className="rounded-full border border-amber-300/25 bg-amber-300/[0.08] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-100">
                In play watch
              </span>
            ) : null}
            <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-200">
              Model signal
            </span>
          </div>
        </div>
      </div>

      <div className="relative p-3 sm:p-6 lg:p-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(34,197,94,0.18),transparent_32%),radial-gradient(circle_at_82%_24%,rgba(14,165,233,0.12),transparent_28%)]" />
        <div className="relative rounded-[1.25rem] border border-slate-800/80 bg-slate-950/35 p-3 sm:rounded-[1.75rem] sm:p-5">
          <div className="grid gap-3 sm:gap-5 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)_340px] lg:items-center">
            <div className="min-w-0 overflow-hidden rounded-[1.15rem] border border-slate-800/80 bg-slate-950/70 p-3 text-center sm:rounded-[1.5rem] sm:p-5">
              <div className="mx-auto max-w-[108px] sm:max-w-[165px]">
                <AbstractJersey
                  playerNumber={signal.playerNumber}
                  teamLogoPath={signal.teamLogoPath}
                  teamPrimaryColor={signal.teamPrimaryColor}
                  teamSecondaryColor={signal.teamSecondaryColor}
                  shirtPattern={signal.teamShirtPattern}
                />
              </div>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                <span className="rounded-md border border-slate-700/60 bg-slate-900/80 px-2.5 py-1 text-xs font-semibold text-slate-300">
                  {signal.position}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300/30 bg-emerald-400/18 px-2.5 py-1 text-xs font-semibold text-emerald-100 shadow-[0_0_18px_rgba(52,211,153,0.08)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.9)]" />
                  Value signal
                </span>
              </div>
              <h2 className="mt-3 break-words text-2xl font-black leading-tight tracking-tight text-slate-50 sm:mt-4 sm:text-4xl">
                {signal.player}
              </h2>
              <p className="mt-2 flex min-w-0 items-center justify-center gap-2 text-sm font-medium text-slate-400">
                <LogoBadge
                  src={signal.teamLogoPath}
                  alt={`${signal.team} logo`}
                  fallback={signal.team}
                  size={24}
                />
                <span className="min-w-0 truncate">
                  {signal.team} | {signal.market}
                </span>
              </p>
            </div>

            <OddsComparisonBar
              modelOdds={signal.fairOdds}
              bookOdds={signal.bestBookOdds}
              bookName={signal.bestBookmaker}
              gapPp={gap}
              modelProb={signal.modelProbability}
              marketProb={signal.bookmakerProbability}
              size="large"
            />

            <div className="hidden lg:block">
              <ProbabilityGauge
                modelProb={signal.modelProbability}
                marketProb={signal.bookmakerProbability}
                gapPp={gap}
              />
            </div>
          </div>

          <div className="mt-4 sm:mt-5">
            <FeatureStrip signal={signal} />
          </div>

          <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/55 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs leading-5 text-slate-500">
              Reference price:{" "}
              <span className="font-semibold text-slate-300">{signal.bestBookmaker}</span>.
              This is the single market reference for the Lab, not a claim that
              it beats every book.{" "}
              Compare your own available bookies before betting.
            </div>
            <Link
              href="/bookmakers"
              className="inline-flex items-center justify-center rounded-xl border border-emerald-300/25 bg-emerald-300/[0.09] px-4 py-2 text-sm font-black text-emerald-100 transition hover:border-emerald-300/45 hover:bg-emerald-300/[0.13]"
            >
              Compare bookmakers &rarr;
            </Link>
          </div>
        </div>

        <div className="relative mt-5 grid gap-3 sm:mt-8 sm:gap-4 xl:grid-cols-3">
          <MetricTable
            kicker="Player case"
            title="Why the model likes it"
            metrics={signal.playerMetrics}
          />
          <MetricTable
            kicker="Opponent profile"
            title="Where the matchup bends"
            metrics={signal.opponentMetrics}
          />
          <MarketTable signal={signal} />
        </div>

        <div className="relative mt-5 sm:mt-6">
          <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-3 sm:p-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
              Matchup edge
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {signal.edgeReasons.map((reason, index) => (
                <div
                  key={reason}
                  className="flex gap-3 rounded-xl border border-slate-800/80 bg-slate-900/70 p-3 text-sm leading-relaxed text-slate-300"
                >
                  <EdgeIcon name={edgeIcons[index % edgeIcons.length]} />
                  <span>{reason}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
