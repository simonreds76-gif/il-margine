import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import { FairOddsSignalBrowser } from "@/components/fair-odds-lab/FairOddsSignalBrowser";
import { sampleSignals } from "@/components/fair-odds-lab/__fixtures__/sample-signals";
import type { LabArtifact, Signal } from "@/components/fair-odds-lab/types";

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
  const leagueSlug = asText(matchData.league);
  const match = homeTeam && awayTeam ? `${homeTeam} vs ${awayTeam}` : asText(matchData.label, "Unknown match");
  const rawPlayerNumber = asText(player.jersey_number, asText(player.shirt_number, asText(player.jersey_label)));
  const playerNumber = /^\d{1,2}$/.test(rawPlayerNumber) ? rawPlayerNumber : undefined;

  return {
    id: asText(raw.id, `${playerName}-${match}`),
    match,
    competition: asText(matchData.league_display, "Football"),
    leagueSlug,
    kickoff: asText(matchData.kickoff_display, "TBC"),
    kickoffUtc: asText(matchData.kickoff_utc),
    venue: asText(matchData.venue, "Venue TBC"),
    player: playerName,
    team: asText(player.team, "Unknown team"),
    position: asText(player.position, "FW"),
    playerNumber,
    teamLogoPath: asText(player.team_logo_path),
    leagueLogoPath: asText(matchData.league_logo_path, leagueSlug ? `/league-logos/${leagueSlug}.png` : ""),
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

function probabilityGap(signal: Signal) {
  return signal.modelProbability - signal.bookmakerProbability;
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

        {!featured ? (
          <section className="mt-8">
            <EmptySignalsState artifact={artifact} />
          </section>
        ) : null}

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


