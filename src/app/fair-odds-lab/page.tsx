import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import { AbstractJersey } from "@/components/fair-odds-lab/AbstractJersey";
import { FairOddsSignalBrowser } from "@/components/fair-odds-lab/FairOddsSignalBrowser";
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
import { sampleSignals } from "@/components/fair-odds-lab/__fixtures__/sample-signals";
import type { LabArtifact, Signal, SignalMetric } from "@/components/fair-odds-lab/types";

export const metadata: Metadata = {
  title: "Fair Odds Lab | Anytime Goalscorer Value Signals",
  description:
    "Research-only anytime goalscorer value signals comparing Il Margine fair odds with bookmaker market prices.",
  alternates: {
    canonical: "/fair-odds-lab",
  },
  robots: {
    index: process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1",
    follow: process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1",
  },
};

function asNumber(value: unknown): number | null {
  const numberValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function asText(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function normalizeConfidence(value: unknown): Signal["confidence"] {
  const text = asText(value).toLowerCase();
  if (text === "high") return "High";
  if (text === "low") return "Low";
  return "Medium";
}

function normalizeMetricTier(value: unknown, fallback = "Unknown") {
  if (typeof value === "string" && value.trim()) return value.trim();
  return fallback;
}

function mapArtifactSignal(rawValue: unknown): Signal | null {
  const raw = asRecord(rawValue);
  const model = asRecord(raw.model);
  const marketData = asRecord(raw.market_data);
  const edge = asRecord(raw.edge);
  const metrics = asRecord(raw.metrics);
  const recentChanceMetric = asRecord(metrics.recent_chance_quality);
  const teamOutlookMetric = asRecord(metrics.team_attacking_outlook);
  const opponentWeaknessMetric = asRecord(metrics.opponent_defensive_weakness);
  const player = asRecord(raw.player);
  const matchData = asRecord(raw.match);

  const modelProbability = asNumber(model.scoring_chance_pct);
  const fairOdds = asNumber(model.fair_odds);
  const bestBookOdds = asNumber(marketData.best_odds);
  const bookmakerProbability = asNumber(marketData.implied_chance_pct);
  const priceGap = asNumber(edge.price_gap_pp);

  if (
    modelProbability === null ||
    fairOdds === null ||
    bestBookOdds === null ||
    bookmakerProbability === null ||
    priceGap === null
  ) {
    return null;
  }

  const recentChanceQuality = normalizeMetricTier(recentChanceMetric.tier);
  const teamAttackingOutlook = normalizeMetricTier(teamOutlookMetric.tier);
  const opponentDefensiveWeakness = normalizeMetricTier(opponentWeaknessMetric.tier);
  const shareOfTeamChances = asNumber(metrics.share_of_team_chances_pct) ?? 0;
  const fixtureBoost = asNumber(metrics.fixture_boost_pct) ?? 0;
  const projectedMinutes = asNumber(metrics.projected_minutes) ?? undefined;
  const lineupStatus = asText(metrics.lineup_confidence, "Lineup unknown");
  const penaltyRole = asText(metrics.penalty_role, "Not on penalties");
  const playerName = asText(player.name, "Unknown player");
  const homeTeam = asText(matchData.home_team);
  const awayTeam = asText(matchData.away_team);
  const match = homeTeam && awayTeam ? `${homeTeam} vs ${awayTeam}` : asText(matchData.label, "Unknown match");

  return {
    id: asText(raw.id, `${playerName}-${match}`),
    match,
    competition: asText(matchData.league_display, "Football"),
    leagueSlug: asText(matchData.league),
    kickoff: asText(matchData.kickoff_display, "TBC"),
    kickoffUtc: asText(matchData.kickoff_utc),
    venue: asText(matchData.venue, "Venue TBC"),
    player: playerName,
    team: asText(player.team, "Unknown team"),
    position: asText(player.position, "FW"),
    playerNumber: asText(player.jersey_label, asText(player.position, "FW")).slice(0, 3).toUpperCase(),
    teamPrimaryColor: asText(player.team_primary_color, "#1d4ed8"),
    teamSecondaryColor: asText(player.team_secondary_color, "#0f172a"),
    market: asText(raw.market, "Anytime goalscorer"),
    fairOdds,
    bestBookOdds,
    bestBookmaker: asText(marketData.best_book, "Best market"),
    modelProbability,
    bookmakerProbability,
    projectedMinutes,
    attackingShare: shareOfTeamChances,
    fixtureSwing: fixtureBoost,
    penaltyRole,
    lineupStatus,
    confidence: normalizeConfidence(raw.confidence_tier),
    accent: "from-emerald-400 to-lime-300",
    recentChanceQuality,
    teamAttackingOutlook,
    opponentDefensiveWeakness,
    playerMetrics: [
      {
        label: "Recent chance quality",
        value: recentChanceQuality,
        percentile: asNumber(recentChanceMetric.percentile) ?? undefined,
        note: "Recent non-penalty chance volume",
      },
      {
        label: "Share of team chances",
        value: `${shareOfTeamChances}%`,
        percentile: asNumber(metrics.share_of_team_chances_percentile) ?? undefined,
        note: "How much of the team threat runs through him",
      },
      {
        label: "Lineup confidence",
        value: lineupStatus,
      },
      {
        label: "Penalty role",
        value: penaltyRole,
      },
    ],
    opponentMetrics: [
      {
        label: "Team attacking outlook",
        value: teamAttackingOutlook,
        percentile: asNumber(teamOutlookMetric.percentile) ?? undefined,
      },
      {
        label: "Opponent defensive weakness",
        value: opponentDefensiveWeakness,
        percentile: asNumber(opponentWeaknessMetric.percentile) ?? undefined,
      },
      {
        label: "Fixture boost",
        value: `${fixtureBoost >= 0 ? "+" : ""}${fixtureBoost}%`,
      },
      {
        label: "Projected minutes",
        value: projectedMinutes ? `${projectedMinutes} min` : lineupStatus,
      },
    ],
    edgeReasons: Array.isArray(raw.reasons) ? raw.reasons.map((reason: unknown) => asText(reason)).filter(Boolean) : [],
  };
}

function makeMockArtifact(): LabArtifact {
  return {
    generatedAt: null,
    edgeThresholdPp: 5,
    fixturesEvaluated: sampleSignals.length,
    signalsQualifying: sampleSignals.length,
    leaguesCovered: [...new Set(sampleSignals.map((signal) => signal.competition))],
    featuredSignalId: sampleSignals[0]?.id,
    signals: sampleSignals,
    isMock: true,
  };
}

function makeEmptyArtifact(): LabArtifact {
  return {
    generatedAt: null,
    edgeThresholdPp: 5,
    fixturesEvaluated: 0,
    signalsQualifying: 0,
    leaguesCovered: [],
    featuredSignalId: null,
    signals: [],
    isMock: false,
  };
}

function readLabArtifact(): LabArtifact {
  const artifactPath = path.join(process.cwd(), "public", "fair-odds-lab", "signals.json");

  if (!fs.existsSync(artifactPath)) {
    return process.env.NODE_ENV === "production" ? makeEmptyArtifact() : makeMockArtifact();
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
    const artifactSignals = Array.isArray(parsed?.signals)
      ? parsed.signals
          .map(mapArtifactSignal)
          .filter((signal: Signal | null): signal is Signal => signal !== null)
      : [];

    return {
      generatedAt: asText(parsed?.generated_at) || null,
      edgeThresholdPp: asNumber(parsed?.edge_threshold_pp) ?? 5,
      fixturesEvaluated: asNumber(parsed?.fixtures_evaluated) ?? 0,
      signalsQualifying: asNumber(parsed?.signals_qualifying) ?? artifactSignals.length,
      leaguesCovered: Array.isArray(parsed?.leagues_covered)
        ? parsed.leagues_covered.map((league: unknown) => asText(league)).filter(Boolean)
        : [],
      featuredSignalId: asText(parsed?.featured_signal_id) || artifactSignals[0]?.id,
      signals: artifactSignals,
      isMock: false,
    };
  } catch {
    return process.env.NODE_ENV === "production" ? makeEmptyArtifact() : makeMockArtifact();
  }
}

function formatOdds(value: number) {
  return value.toFixed(2);
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function probabilityGap(signal: Signal) {
  return signal.modelProbability - signal.bookmakerProbability;
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
      <div className="grid min-w-[150px] gap-1">
        <span className="text-right font-mono text-sm font-semibold text-slate-100">
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

  if (label.includes("opponent defensive weakness")) {
    return (
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-100">{metric.value}</span>
        <TierIndicator tier={metric.value} size="sm" variant="weakness" />
      </div>
    );
  }

  if (label.includes("fixture boost")) {
    return (
      <div className="grid min-w-[150px] gap-1">
        <span className="text-right font-mono text-sm font-semibold text-slate-100">
          {metric.value}
        </span>
        <SignedBoostMeter value={numberFromMetric(metric.value)} />
      </div>
    );
  }

  if (label.includes("projected minutes")) {
    return (
      <div className="grid min-w-[150px] gap-1">
        <span className="text-right font-mono text-sm font-semibold text-slate-100">
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
    <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-4">
      <div className="mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
          {kicker}
        </div>
        <h3 className="mt-1 text-base font-semibold text-slate-100">{title}</h3>
      </div>
      <div className="space-y-2">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3"
          >
            <div>
              <div className="text-xs font-medium text-slate-300">
                {metric.label}
              </div>
              {metric.note ? (
                <div className="mt-0.5 text-[11px] text-slate-500">
                  {metric.note}
                </div>
              ) : null}
            </div>
            <div className="flex min-w-[150px] justify-end">
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
      best: `+${gap.toFixed(1)}pp`,
    },
  ];

  return (
    <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-4">
      <div className="mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
          Price panel
        </div>
        <h3 className="mt-1 text-base font-semibold text-slate-100">
          Il Margine vs market
        </h3>
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-800/80">
        <div className="grid grid-cols-3 bg-slate-900/90 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          <div className="px-3 py-2">Metric</div>
          <div className="px-3 py-2 text-right">Model</div>
          <div className="px-3 py-2 text-right">
            Best
            <span className="hidden truncate normal-case tracking-normal text-slate-600 sm:block">
              {signal.bestBookmaker}
            </span>
          </div>
        </div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-3 border-t border-slate-800/75 text-sm"
          >
            <div className="px-3 py-3 text-slate-400">{row.label}</div>
            <div className="px-3 py-3 text-right font-mono text-emerald-200 tabular-nums">
              {row.model}
            </div>
            <div
              className={`px-3 py-3 text-right font-mono tabular-nums ${
                row.label === "Probability gap" ? "text-amber-300" : "text-slate-100"
              }`}
            >
              {row.best}
              {row.label === "Probability gap" ? <PriceGapMeter value={gap} /> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeatureStrip({ signal }: { signal: Signal }) {
  const cardClass =
    "flex min-h-[126px] flex-col justify-between rounded-xl border border-slate-700/45 border-t-slate-500/45 bg-slate-900/70 p-4";
  const labelClass = "text-[10px] uppercase tracking-[0.18em] text-slate-500";
  const valueClass = "font-mono text-2xl font-black text-slate-100";

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div className={cardClass}>
        <div className={labelClass}>Model scoring chance</div>
        <div className="flex items-center justify-between gap-3">
          <div className="font-mono text-2xl font-black text-emerald-200">
            {formatPercent(signal.modelProbability)}
          </div>
          <MiniDonut value={signal.modelProbability} />
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Recent chance quality</div>
        <div className="flex items-center justify-between gap-3">
          <div className={valueClass}>
            {signal.recentChanceQuality ?? "Unknown"}
          </div>
          <TierIndicator tier={signal.recentChanceQuality ?? "Average"} />
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Share of team chances</div>
        <div>
          <div className={valueClass}>{signal.attackingShare}%</div>
          <ProportionalBar value={signal.attackingShare} maxValue={50} />
        </div>
      </div>
      <div className={cardClass}>
        <div className={labelClass}>Fixture boost</div>
        <div>
          <div className={valueClass}>
            {signal.fixtureSwing >= 0 ? "+" : ""}
            {signal.fixtureSwing}%
          </div>
          <SignedBoostMeter value={signal.fixtureSwing} />
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

function FeaturedSignal({ signal }: { signal: Signal }) {
  const gap = probabilityGap(signal);

  return (
    <article className="overflow-hidden rounded-[2rem] border border-emerald-300/20 bg-[#0a0f12] shadow-[0_24px_90px_rgba(16,185,129,0.12)]">
      <div className="border-b border-slate-800/90 bg-slate-950/80 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
              Featured research signal
            </div>
            <div className="mt-2 text-sm font-semibold text-slate-200">
              {signal.match} <span className="text-slate-600">|</span> {signal.competition}
            </div>
            <div className="mt-1 text-xs text-slate-500">
              {signal.kickoff} <span className="text-slate-700">|</span> {signal.venue}
            </div>
          </div>
          <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-200">
            Research only
          </span>
        </div>
      </div>

      <div className="relative p-5 sm:p-6 lg:p-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(34,197,94,0.18),transparent_32%),radial-gradient(circle_at_82%_24%,rgba(14,165,233,0.12),transparent_28%)]" />
        <div className="relative rounded-[1.75rem] border border-slate-800/80 bg-slate-950/35 p-4 sm:p-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)_340px] lg:items-center">
            <div className="min-w-0 overflow-hidden rounded-[1.5rem] border border-slate-800/80 bg-slate-950/70 p-5 text-center">
              <div className="mx-auto max-w-[155px] sm:max-w-[165px]">
                <AbstractJersey
                  playerNumber={signal.playerNumber}
                  teamPrimaryColor={signal.teamPrimaryColor}
                  teamSecondaryColor={signal.teamSecondaryColor}
                />
              </div>
              <div className="mt-3 flex flex-wrap justify-center gap-2">
                <span className="rounded-md border border-slate-700/60 bg-slate-900/80 px-2.5 py-1 text-xs font-semibold text-slate-300">
                  {signal.position}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300/30 bg-emerald-400/18 px-2.5 py-1 text-xs font-semibold text-emerald-100 shadow-[0_0_18px_rgba(52,211,153,0.08)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.9)]" />
                  {signal.confidence} confidence
                </span>
              </div>
              <h2 className="mt-4 break-words text-3xl font-black leading-tight tracking-tight text-slate-50 sm:text-4xl">
                {signal.player}
              </h2>
              <p className="mt-2 text-sm font-medium text-slate-400">
                {signal.team} | {signal.market}
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

            <ProbabilityGauge
              modelProb={signal.modelProbability}
              marketProb={signal.bookmakerProbability}
              gapPp={gap}
            />
          </div>

          <div className="mt-5">
            <FeatureStrip signal={signal} />
          </div>
        </div>

        <div className="relative mt-8 grid gap-4 xl:grid-cols-3">
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

        <div className="relative mt-6">
          <div className="rounded-2xl border border-slate-700/45 bg-slate-950/55 p-5">
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

function EmptySignalsState({ artifact }: { artifact: LabArtifact }) {
  return (
    <section className="rounded-[2rem] border border-slate-700/45 bg-[#0c0f14] p-8 text-center shadow-[0_24px_80px_rgba(0,0,0,0.25)]">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300">
        <svg aria-hidden="true" className="h-7 w-7" fill="none" viewBox="0 0 24 24">
          <path
            d="M4 12h4l2-6 4 12 2-6h4"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="1.8"
          />
        </svg>
      </div>
      <h2 className="mt-5 text-2xl font-black tracking-tight text-slate-50">
        No qualifying value signals right now
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
        The model evaluated {artifact.fixturesEvaluated} fixture
        {artifact.fixturesEvaluated === 1 ? "" : "s"}.{" "}
        {artifact.edgeThresholdPp > 0
          ? `None currently meet the +${artifact.edgeThresholdPp.toFixed(1)}pp price-gap threshold.`
          : "None currently show a positive model-vs-market price gap."}{" "}
        That means the lab is deliberately quiet rather than showing stale or
        forced picks.
      </p>
    </section>
  );
}

export default function FairOddsLabPage() {
  const artifact = readLabArtifact();
  const featured =
    artifact.signals.find((signal) => signal.id === artifact.featuredSignalId) ??
    artifact.signals[0];
  const signals = featured
    ? [featured, ...artifact.signals.filter((signal) => signal.id !== featured.id)]
    : artifact.signals;
  const exampleSignal = featured ?? sampleSignals[0];
  const bestProbabilityGap = featured ? probabilityGap(featured) : 0;
  const exampleProbabilityGap = probabilityGap(exampleSignal);
  const averageProbabilityGap =
    signals.length > 0
      ? signals.reduce((total, signal) => total + probabilityGap(signal), 0) / signals.length
      : 0;
  const leagueCount =
    artifact.leaguesCovered.length || new Set(signals.map((signal) => signal.competition)).size;

  return (
    <main className="min-h-screen overflow-hidden bg-[#07090d] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_12%_5%,rgba(34,197,94,0.16),transparent_28%),radial-gradient(circle_at_88%_12%,rgba(14,165,233,0.12),transparent_30%),linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] bg-[size:auto,auto,40px_40px,40px_40px]" />

      <div className="relative mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <section className="relative overflow-hidden rounded-[2rem] border border-slate-700/45 bg-slate-950/55 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)] sm:p-8">
          <div className="pointer-events-none absolute -right-16 -top-20 h-80 w-80 rounded-full border-[34px] border-emerald-400/[0.055]" />
          <div className="pointer-events-none absolute right-10 top-10 h-40 w-40 rounded-full border-[18px] border-emerald-300/[0.045]" />
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-emerald-400/35 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Research preview
            </span>
            <span className="rounded-full border border-slate-700/55 bg-slate-900/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Not tracked picks
            </span>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-5xl font-black tracking-tight text-slate-50 sm:text-6xl lg:text-7xl">
                Fair Odds Lab
              </h1>
              <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300 sm:text-xl">
                Anytime goalscorer value signals where the model thinks the
                market price is too long.
              </p>
            </div>
          </div>

          <div className="relative mt-8 grid gap-0 overflow-hidden rounded-2xl border border-slate-700/55 bg-slate-950/70 sm:grid-cols-4">
            {[
              ["Sample signals", signals.length.toString()],
              ["Avg gap", `+${averageProbabilityGap.toFixed(1)}pp`],
              ["Biggest gap", `+${bestProbabilityGap.toFixed(1)}pp`],
              ["Leagues", leagueCount.toString()],
            ].map(([label, value], index) => (
              <div
                key={label}
                className={`px-4 py-4 ${index > 0 ? "border-t border-slate-800/80 sm:border-l sm:border-t-0" : ""}`}
              >
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {label}
                </div>
                <div
                  className={`mt-1 font-mono text-2xl font-black ${
                    label.includes("gap") || label.includes("Gap")
                      ? "text-amber-300"
                      : "text-slate-100"
                  }`}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-amber-400/25 bg-amber-400/[0.08] px-4 py-3 text-sm leading-6 text-amber-100 sm:px-5">
          Research signals only. These are not official Il Margine tracked bets
          and are not part of the paid record. They show where the model thinks
          the market price may be too big.
        </section>

        <section className="mt-5">
          <div className="rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
              How to read this
            </div>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              The model estimates a player&apos;s true chance of scoring. If our fair
              odds are {formatOdds(exampleSignal.fairOdds)} and the bookmaker offers{" "}
              {formatOdds(exampleSignal.bestBookOdds)}, the market is paying more
              than the implied risk. That is a value signal, not a promise the
              player will score. Worked example: model {formatOdds(exampleSignal.fairOdds)} vs market{" "}
              {formatOdds(exampleSignal.bestBookOdds)} = +{exampleProbabilityGap.toFixed(1)}pp gap.
            </p>
          </div>
        </section>

        {featured ? (
          <section className="mt-8">
            <FeaturedSignal signal={featured} />
          </section>
        ) : (
          <section className="mt-8">
            <EmptySignalsState artifact={artifact} />
          </section>
        )}

        {signals.length > 0 ? (
          <FairOddsSignalBrowser
            artifact={{ ...artifact, signals }}
            featuredSignalId={featured?.id ?? null}
          />
        ) : null}

        <footer className="mt-10 rounded-2xl border border-slate-700/45 bg-slate-950/55 p-5 text-sm leading-6 text-slate-400">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              Last refreshed: {artifact.generatedAt ? artifact.generatedAt : "static mock preview"}
            </span>
            <span>{signals.length} signals shown</span>
          </div>
          <p className="mt-3 border-t border-slate-800/80 pt-3">
            This lab separates model research from official picks. No ROI, win
            loss record, or staking claim should appear here until the
            goalscorer model earns tracked status.
          </p>
        </footer>
      </div>
    </main>
  );
}
