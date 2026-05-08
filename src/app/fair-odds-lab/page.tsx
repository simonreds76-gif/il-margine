import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import teamLogoManifest from "../../../data/goalscorer/team-logo-map.json";
import { FairOddsSignalBrowser } from "@/components/fair-odds-lab/FairOddsSignalBrowser";
import { sampleSignals } from "@/components/fair-odds-lab/__fixtures__/sample-signals";
import type { LabArtifact, Signal } from "@/components/fair-odds-lab/types";

export const metadata: Metadata = {
  title: "Goalscorer Fair Odds Lab | Anytime Goalscorer Value Spots",
  description:
    "Research-only anytime goalscorer value spots for likely and confirmed starters, comparing Il Margine fair odds with bookmaker market prices.",
  alternates: {
    canonical: "/fair-odds-lab",
  },
  robots: {
    index: process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1",
    follow: process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1",
  },
};

export const dynamic = "force-dynamic";

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

function roleLabel(minutes: number | undefined, lineupStatus: string) {
  if (lineupStatus.toLowerCase().includes("confirmed")) return "Confirmed starter";
  if (minutes === undefined) return lineupStatus;
  if (minutes >= 80) return "Likely full match";
  if (minutes >= 70) return "Expected 60+";
  return "Minutes watch";
}

type TeamLogoRow = {
  logo_path?: string;
  team_key?: string;
};

type LogoManifest = {
  leagues?: Record<
    string,
    {
      teams?: Record<string, TeamLogoRow>;
    }
  >;
};

const LOGO_MANIFEST = teamLogoManifest as LogoManifest;

const TEAM_NAME_ALIASES: Record<string, string> = {
  "rb leipzig": "rasenballsport leipzig",
  "fc cologne": "cologne",
  "1 fc koln": "cologne",
  "fc koln": "cologne",
  "1 fc cologne": "cologne",
  "tottenham hotspur": "tottenham",
  "west ham united": "west ham",
  wolves: "wolverhampton wanderers",
  wolverhampton: "wolverhampton wanderers",
  "brighton and hove albion": "brighton",
  "brighton hove albion": "brighton",
  "afc bournemouth": "bournemouth",
  "borussia monchengladbach": "borussia m gladbach",
  "as roma": "roma",
  "acf fiorentina": "fiorentina",
  "inter milan": "inter",
  "inter milano": "inter",
  internazionale: "inter",
  "athletic bilbao": "athletic club",
  "real sociedad": "sociedad",
  "real sociedad san sebastian": "sociedad",
  "as monaco": "monaco",
  "rc lens": "lens",
};

const TEAM_STYLE_OVERRIDES: Record<string, { primary: string; secondary: string; pattern: Signal["teamShirtPattern"] }> = {
  "arsenal": { primary: "#b91c1c", secondary: "#f8fafc", pattern: "sash" },
  "aston villa": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "bournemouth": { primary: "#dc2626", secondary: "#111827", pattern: "vertical-stripes" },
  "brentford": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "brighton": { primary: "#2563eb", secondary: "#f8fafc", pattern: "vertical-stripes" },
  "burnley": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "chelsea": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "crystal palace": { primary: "#1d4ed8", secondary: "#dc2626", pattern: "vertical-stripes" },
  "everton": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "liverpool": { primary: "#dc2626", secondary: "#f8fafc", pattern: "solid" },
  "manchester city": { primary: "#7dd3fc", secondary: "#f8fafc", pattern: "solid" },
  "manchester united": { primary: "#dc2626", secondary: "#111827", pattern: "solid" },
  "newcastle united": { primary: "#f8fafc", secondary: "#111827", pattern: "vertical-stripes" },
  "tottenham": { primary: "#f8fafc", secondary: "#1e3a8a", pattern: "solid" },
  "west ham": { primary: "#7f1d1d", secondary: "#38bdf8", pattern: "solid" },
  "wolverhampton wanderers": { primary: "#f59e0b", secondary: "#111827", pattern: "solid" },
  "bayer leverkusen": { primary: "#111827", secondary: "#dc2626", pattern: "vertical-stripes" },
  "rasenballsport leipzig": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "cologne": { primary: "#f8fafc", secondary: "#dc2626", pattern: "solid" },
  "borussia dortmund": { primary: "#facc15", secondary: "#111827", pattern: "solid" },
  "union berlin": { primary: "#b91c1c", secondary: "#facc15", pattern: "solid" },
  "bayern munich": { primary: "#dc2626", secondary: "#f8fafc", pattern: "solid" },
  "pisa": { primary: "#0f172a", secondary: "#1d4ed8", pattern: "halves" },
  "lecce": { primary: "#facc15", secondary: "#dc2626", pattern: "vertical-stripes" },
  "napoli": { primary: "#0ea5e9", secondary: "#f8fafc", pattern: "solid" },
  "como": { primary: "#1d4ed8", secondary: "#f8fafc", pattern: "solid" },
  "juventus": { primary: "#f8fafc", secondary: "#111827", pattern: "vertical-stripes" },
  "inter": { primary: "#1d4ed8", secondary: "#111827", pattern: "vertical-stripes" },
  "milan": { primary: "#dc2626", secondary: "#111827", pattern: "vertical-stripes" },
  "roma": { primary: "#7f1d1d", secondary: "#f59e0b", pattern: "solid" },
  "lazio": { primary: "#7dd3fc", secondary: "#f8fafc", pattern: "solid" },
  "fiorentina": { primary: "#7e22ce", secondary: "#f8fafc", pattern: "solid" },
  "atalanta": { primary: "#1d4ed8", secondary: "#111827", pattern: "vertical-stripes" },
  "barcelona": { primary: "#1e3a8a", secondary: "#b91c1c", pattern: "vertical-stripes" },
  "real madrid": { primary: "#f8fafc", secondary: "#facc15", pattern: "solid" },
  "atletico madrid": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "sociedad": { primary: "#f8fafc", secondary: "#2563eb", pattern: "vertical-stripes" },
  "athletic club": { primary: "#f8fafc", secondary: "#dc2626", pattern: "vertical-stripes" },
  "monaco": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "psg": { primary: "#1e3a8a", secondary: "#dc2626", pattern: "solid" },
  "marseille": { primary: "#f8fafc", secondary: "#0ea5e9", pattern: "solid" },
  "lyon": { primary: "#f8fafc", secondary: "#dc2626", pattern: "sash" },
  "lille": { primary: "#dc2626", secondary: "#1e3a8a", pattern: "solid" },
  "lens": { primary: "#dc2626", secondary: "#facc15", pattern: "vertical-stripes" },
};

function normalizeTeamKey(value: unknown): string {
  const normalized = asText(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  const aliased = TEAM_NAME_ALIASES[normalized] ?? normalized;
  const simplified = aliased
    .replace(/\b(?:ac|afc|as|bc|ca|cf|cfc|fc|rc|rcd|sc|ssc|us)\b/g, " ")
    .replace(/\bcalcio\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return TEAM_NAME_ALIASES[simplified] ?? simplified;
}

function resolveTeamLogoPath(leagueSlug: string, team: string): string {
  const teams = LOGO_MANIFEST.leagues?.[leagueSlug]?.teams ?? {};
  if (teams[team]?.logo_path) return asText(teams[team].logo_path);
  const target = normalizeTeamKey(team);
  const matched = Object.entries(teams).find(([name, row]) => {
    return normalizeTeamKey(name) === target || normalizeTeamKey(row.team_key) === target;
  });
  return matched?.[1].logo_path ? asText(matched[1].logo_path) : "";
}

function resolveTeamStyle(team: string) {
  return TEAM_STYLE_OVERRIDES[normalizeTeamKey(team)] ?? null;
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
  const teamName = asText(player.team, "Unknown team");
  const teamStyle = resolveTeamStyle(teamName);
  const rawPattern = asText(player.team_shirt_pattern);
  const artifactPattern = ["solid", "vertical-stripes", "halves", "sash"].includes(rawPattern)
    ? (rawPattern as Signal["teamShirtPattern"])
    : undefined;

  return {
    id: asText(raw.id, `${playerName}-${match}`),
    match,
    competition: asText(matchData.league_display, "Football"),
    leagueSlug,
    kickoff: asText(matchData.kickoff_display, "TBC"),
    kickoffUtc: asText(matchData.kickoff_utc),
    venue: asText(matchData.venue, "Venue TBC"),
    player: playerName,
    team: teamName,
    position: asText(player.position, "FW"),
    playerNumber,
    teamLogoPath: asText(player.team_logo_path) || resolveTeamLogoPath(leagueSlug, teamName),
    leagueLogoPath: asText(matchData.league_logo_path, leagueSlug ? `/league-logos/${leagueSlug}.png` : ""),
    teamPrimaryColor: teamStyle?.primary ?? asText(player.team_primary_color, "#1d4ed8"),
    teamSecondaryColor: teamStyle?.secondary ?? asText(player.team_secondary_color, "#0f172a"),
    teamShirtPattern: teamStyle?.pattern ?? artifactPattern,
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
        label: "Expected role",
        value: roleLabel(projectedMinutes, lineupStatus),
      },
    ],
    edgeReasons: Array.isArray(raw.reasons) ? raw.reasons.map((reason: unknown) => asText(reason)).filter(Boolean) : [],
  };
}

function isPreKickoffSignal(signal: Signal, nowMs = Date.now()): boolean {
  if (!signal.kickoffUtc) return false;
  const kickoffMs = Date.parse(signal.kickoffUtc);
  return Number.isFinite(kickoffMs) && kickoffMs > nowMs;
}

function makeMockArtifact(): LabArtifact {
  return {
    generatedAt: null,
    edgeThresholdPp: 6,
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
    edgeThresholdPp: 6,
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
          .filter((signal: Signal) => isPreKickoffSignal(signal))
      : [];

    return {
      generatedAt: asText(parsed?.generated_at) || null,
      edgeThresholdPp: asNumber(parsed?.edge_threshold_pp) ?? 6,
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

function formatRefreshed(value: string | null) {
  if (!value) return "Waiting";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "Latest artifact";
  const label = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  }).format(timestamp);
  return `${label} UK`;
}

function EmptySignalsState() {
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
        No live value spots right now
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
        The latest board does not have a goalscorer price strong enough to
        show. That is intentional: if the edge is not clear, the lab stays
        quiet instead of filling the page with weak picks. Check again closer
        to kickoff, when teams and prices are sharper.
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
  const exampleProbabilityGap = probabilityGap(exampleSignal);
  const leagueCount =
    artifact.leaguesCovered.length || new Set(signals.map((signal) => signal.competition)).size;
  const boardStatus = featured ? featured.player : "Quiet board";
  const coverageLabel = leagueCount > 0 ? leagueCount.toString() : "Waiting";
  const refreshedLabel = formatRefreshed(artifact.generatedAt);

  return (
    <main className="min-h-screen overflow-hidden bg-[#07090d] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_12%_5%,rgba(34,197,94,0.16),transparent_28%),radial-gradient(circle_at_88%_12%,rgba(14,165,233,0.12),transparent_30%),linear-gradient(rgba(148,163,184,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.025)_1px,transparent_1px)] bg-[size:auto,auto,40px_40px,40px_40px]" />

      <div className="relative mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
        <section className="relative overflow-hidden rounded-[2rem] border border-slate-700/45 bg-slate-950/55 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)] sm:p-8">
          <div className="pointer-events-none absolute -right-16 -top-20 h-80 w-80 rounded-full border-[34px] border-emerald-400/[0.055]" />
          <div className="pointer-events-none absolute right-10 top-10 h-40 w-40 rounded-full border-[18px] border-emerald-300/[0.045]" />
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-emerald-400/35 bg-emerald-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">
              Il Margine Intelligence
            </span>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-end">
            <div>
              <h1 className="max-w-4xl text-5xl font-black tracking-tight text-slate-50 sm:text-6xl lg:text-7xl">
                Goalscorer Fair Odds Lab
              </h1>
              <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300 sm:text-xl">
                Where our model&apos;s price is shorter than the bookies&apos;.
                We surface likely-starter anytime-goalscorer value spots, then
                upgrade the status to confirmed once official teams are out.
              </p>
            </div>
          </div>

          <div className="relative mt-8 grid gap-0 overflow-hidden rounded-2xl border border-slate-700/55 bg-slate-950/70 sm:grid-cols-4">
            {[
              ["Board status", boardStatus],
              ["Live value spots", signals.length.toString()],
              ["Leagues active", coverageLabel],
              ["Updated", refreshedLabel],
            ].map(([label, value], index) => (
              <div
                key={label}
                className={`px-4 py-4 ${index > 0 ? "border-t border-slate-800/80 sm:border-l sm:border-t-0" : ""}`}
              >
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {label}
                </div>
                <div
                  className="mt-1 break-words font-mono text-2xl font-black text-slate-100"
                >
                  {value}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-amber-400/25 bg-amber-400/[0.08] px-4 py-3 text-sm leading-6 text-amber-100 sm:px-5">
          Research board only. These are model-led value spots, not official
          tracked picks. Projected starters can appear before team news; once
          official lineups land, the status updates to confirmed or drops out.
        </section>

        <section className="mt-5">
          <div className="rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
              How to read this
            </div>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              The model estimates a player&apos;s true chance of scoring. If our fair
              odds are {formatOdds(exampleSignal.fairOdds)} and the bookmaker offers{" "}
              {formatOdds(exampleSignal.bestBookOdds)}, the bookmaker is paying
              more than our price says it should. That is a value signal, not a
              promise the player will score. In plain words, a {`+${exampleProbabilityGap.toFixed(1)}pp`} gap means our model sees a
              bigger scoring chance than the market price implies.
            </p>
          </div>
        </section>

        {!featured ? (
          <section className="mt-8">
            <EmptySignalsState />
          </section>
        ) : null}

        {signals.length > 0 ? (
          <FairOddsSignalBrowser
            artifact={{ ...artifact, signals }}
            featuredSignalId={featured?.id ?? null}
          />
        ) : null}

      </div>
    </main>
  );
}


