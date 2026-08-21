import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";

import teamKitColors from "../../../data/goalscorer/team-kit-colors.json";
import teamLogoManifest from "../../../data/goalscorer/team-logo-map.json";
import { AbstractJersey } from "@/components/fair-odds-lab/AbstractJersey";
import { BookmakerLogo } from "@/components/fair-odds-lab/BookmakerLogo";
import { FairOddsSignalBrowser } from "@/components/fair-odds-lab/FairOddsSignalBrowser";
import { LogoBadge } from "@/components/fair-odds-lab/LogoBadge";
import { sampleSignals } from "@/components/fair-odds-lab/__fixtures__/sample-signals";
import type { LabArtifact, LabHighlight, Signal, SignalMetric } from "@/components/fair-odds-lab/types";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Anytime Goalscorer Value Spots | Goalscorer Fair Odds Lab",
  description:
    "Live anytime goalscorer value spots from Il Margine, comparing our model's fair odds with bookmaker prices for likely and confirmed starters, including bookmaker-dependent Super Sub upside.",
  keywords: [
    "anytime goalscorer tips",
    "goalscorer value bets",
    "Super Sub goalscorer",
    "Sub On Play On",
    "bet365 goalscorer",
    "football goalscorer odds",
    "fair odds",
    "football betting model",
    "Bet365 goalscorer odds",
    "Il Margine",
  ],
  alternates: {
    canonical: "/fair-odds-lab",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: "website",
    url: `${BASE_URL}/fair-odds-lab`,
    title: "Goalscorer Fair Odds Lab | Il Margine",
    description:
      "Anytime goalscorer value spots where Il Margine's model price is shorter than the bookmaker market price. Some bookmaker markets can add Sub On Play On upside.",
    images: [
      {
        url: `${BASE_URL}/og.png`,
        width: 1200,
        height: 630,
        alt: "Il Margine Goalscorer Fair Odds Lab",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Goalscorer Fair Odds Lab | Il Margine",
    description:
      "Anytime goalscorer value spots where Il Margine's model price is shorter than the bookmaker market price, with Super Sub upside explained where relevant.",
    images: [`${BASE_URL}/og.png`],
  },
};

export const revalidate = 300;
const REMOTE_ARTIFACT_REVALIDATE_SECONDS = 300;
const MATCH_VISIBILITY_AFTER_KICKOFF_MS = 150 * 60 * 1000;

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

function isKnownTier(value: string) {
  return value.trim().toLowerCase() !== "unknown";
}

function roleLabel(minutes: number | undefined, lineupStatus: string) {
  if (lineupStatus.toLowerCase().includes("confirmed")) return "Confirmed starter";
  if (minutes === undefined) return lineupStatus;
  if (minutes >= 80) return "Likely full match";
  if (minutes >= 70) return "Expected 60+";
  return "Minutes watch";
}

function formatSignedValue(value: number | null, digits = 2) {
  if (value === null) return null;
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function formatOneDecimal(value: number | null) {
  if (value === null) return null;
  return value.toFixed(1);
}

function teamFormNote(metric: Record<string, unknown>) {
  const window = asNumber(metric.window) ?? 5;
  const xgd = formatSignedValue(asNumber(metric.xgd_per90));
  const xgFor = formatOneDecimal(asNumber(metric.xg_for_avg));
  const xgAgainst = formatOneDecimal(asNumber(metric.xg_against_avg));
  if (!xgd) return "Recent team attacking form";
  const xgDetail = xgFor && xgAgainst ? ` (${xgFor} xG for, ${xgAgainst} against)` : "";
  return `Last ${window}: ${xgd} xGD/90${xgDetail}`;
}

function opponentFormNote(metric: Record<string, unknown>) {
  const window = asNumber(metric.window) ?? 5;
  const xgAgainst = formatOneDecimal(asNumber(metric.xg_against_avg));
  const shotsAgainst = formatOneDecimal(asNumber(metric.shots_against_avg));
  if (!xgAgainst) return "Recent opponent chance concession";
  const shotDetail = shotsAgainst ? `, ${shotsAgainst} shots conceded/game` : "";
  return `Last ${window}: ${xgAgainst} xGA/game${shotDetail}`;
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
type TeamStyle = {
  primary: string;
  secondary: string;
  pattern: NonNullable<Signal["teamShirtPattern"]>;
};
const TEAM_KIT_COLORS = teamKitColors as Record<string, TeamStyle>;

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
  "ogc nice": "nice",
  "olympique gymnaste club nice": "nice",
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
  const key = normalizeTeamKey(team);
  return TEAM_KIT_COLORS[key] ?? TEAM_STYLE_OVERRIDES[key] ?? null;
}

function mapArtifactSignal(rawValue: unknown): Signal | null {
  const raw = asRecord(rawValue);
  const model = asRecord(raw.model);
  const marketData = asRecord(raw.market_data);
  const edge = asRecord(raw.edge);
  const metrics = asRecord(raw.metrics);
  const recentChanceMetric = asRecord(metrics.recent_chance_quality);
  const teamOutlookMetric = asRecord(metrics.team_attacking_outlook);
  const recentTeamFormMetric = asRecord(metrics.recent_team_form);
  const opponentWeaknessMetric = asRecord(metrics.opponent_defensive_weakness);
  const opponentRecentDefenceMetric = asRecord(metrics.opponent_recent_defence);
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
  const recentTeamForm = normalizeMetricTier(recentTeamFormMetric.tier);
  const opponentDefensiveWeakness = normalizeMetricTier(opponentWeaknessMetric.tier);
  const opponentRecentDefence = normalizeMetricTier(opponentRecentDefenceMetric.tier);
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
  const opponentMetrics: SignalMetric[] = [
    {
      label: "Team attacking outlook",
      value: teamAttackingOutlook,
      percentile: asNumber(teamOutlookMetric.percentile) ?? undefined,
    },
  ];
  if (isKnownTier(recentTeamForm)) {
    opponentMetrics.push({
      label: "Recent team form",
      value: recentTeamForm,
      note: teamFormNote(recentTeamFormMetric),
    });
  }
  opponentMetrics.push({
    label: "Opponent defensive weakness",
    value: opponentDefensiveWeakness,
    percentile: asNumber(opponentWeaknessMetric.percentile) ?? undefined,
  });
  if (isKnownTier(opponentRecentDefence)) {
    opponentMetrics.push({
      label: "Opponent recent defence",
      value: opponentRecentDefence,
      note: opponentFormNote(opponentRecentDefenceMetric),
    });
  }
  opponentMetrics.push({
    label: "Expected role",
    value: roleLabel(projectedMinutes, lineupStatus),
  });

  return {
    id: asText(raw.id, `${playerName}-${match}`),
    match,
    homeTeam,
    awayTeam,
    homeTeamLogoPath: homeTeam ? resolveTeamLogoPath(leagueSlug, homeTeam) : "",
    awayTeamLogoPath: awayTeam ? resolveTeamLogoPath(leagueSlug, awayTeam) : "",
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
    bestBookmaker: asText(marketData.best_book, "Bet365 reference"),
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
    opponentMetrics,
    edgeReasons: Array.isArray(raw.reasons) ? raw.reasons.map((reason: unknown) => asText(reason)).filter(Boolean) : [],
  };
}

function getSignalDisplayStatus(
  signal: Signal,
  nowMs = Date.now(),
): Signal["displayStatus"] | null {
  if (signal.kickoffUtc) {
    const kickoffMs = Date.parse(signal.kickoffUtc);
    if (!Number.isFinite(kickoffMs)) return null;
    if (kickoffMs > nowMs) return "pre_match";
    return nowMs - kickoffMs <= MATCH_VISIBILITY_AFTER_KICKOFF_MS ? "in_play" : null;
  }

  const dateOnly = signal.kickoff.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!dateOnly) return null;

  const [, year, month, day] = dateOnly;
  const fallbackDateMs = Date.UTC(Number(year), Number(month) - 1, Number(day));
  const now = new Date(nowMs);
  const todayStartMs = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());

  // Date-only rows are safe to show only for future dates; same-day rows need an exact kickoff.
  return Number.isFinite(fallbackDateMs) && fallbackDateMs > todayStartMs ? "pre_match" : null;
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

function parseLabArtifact(parsed: unknown, isMock = false): LabArtifact | null {
  const raw = asRecord(parsed);
  if (!Array.isArray(raw.signals)) return null;

  const nowMs = Date.now();
  const artifactSignals = raw.signals
    .map(mapArtifactSignal)
    .filter((signal: Signal | null): signal is Signal => signal !== null)
    .map((signal: Signal): Signal | null => {
      const displayStatus = getSignalDisplayStatus(signal, nowMs);
      return displayStatus ? { ...signal, displayStatus } : null;
    })
    .filter((signal: Signal | null): signal is Signal => signal !== null);
  const requestedFeaturedId = asText(raw.featured_signal_id);
  const featuredSignal =
    artifactSignals.find((signal) => signal.id === requestedFeaturedId && signal.displayStatus === "pre_match") ??
    artifactSignals.find((signal) => signal.displayStatus === "pre_match") ??
    artifactSignals.find((signal) => signal.id === requestedFeaturedId) ??
    artifactSignals[0];

  return {
    generatedAt: asText(raw.generated_at) || null,
    edgeThresholdPp: asNumber(raw.edge_threshold_pp) ?? 6,
    fixturesEvaluated: asNumber(raw.fixtures_evaluated) ?? 0,
    signalsQualifying: artifactSignals.length,
    leaguesCovered: Array.isArray(raw.leagues_covered)
      ? raw.leagues_covered.map((league: unknown) => asText(league)).filter(Boolean)
      : [],
    featuredSignalId: featuredSignal?.id ?? null,
    signals: artifactSignals,
    isMock,
  };
}

async function fetchRemoteJson(url: string | undefined, label: string): Promise<unknown | null> {
  const artifactUrl = url?.trim();
  if (!artifactUrl) return null;

  try {
    const response = await fetch(artifactUrl, {
      headers: { accept: "application/json" },
      next: { revalidate: REMOTE_ARTIFACT_REVALIDATE_SECONDS },
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`[fair-odds-lab] ${label} remote fetch failed; falling back to bundled artifact.`, error);
    return null;
  }
}

function readLocalJson(fileName: string): unknown | null {
  const artifactPath = path.join(process.cwd(), "public", "fair-odds-lab", fileName);
  if (!fs.existsSync(artifactPath)) return null;

  try {
    return JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  } catch (error) {
    console.warn(`[fair-odds-lab] bundled ${fileName} failed to parse.`, error);
    return null;
  }
}

async function readLabArtifact(): Promise<LabArtifact> {
  const remoteArtifact = parseLabArtifact(
    await fetchRemoteJson(process.env.FAIR_ODDS_LAB_ARTIFACT_URL, "signals"),
  );
  if (remoteArtifact) return remoteArtifact;

  const localArtifact = parseLabArtifact(readLocalJson("signals.json"));
  if (localArtifact) return localArtifact;

  return process.env.NODE_ENV === "production" ? makeEmptyArtifact() : makeMockArtifact();
}

function mapHighlight(rawValue: unknown): LabHighlight | null {
  const raw = asRecord(rawValue);
  const bestOdds = asNumber(raw.best_odds);
  const fairOdds = asNumber(raw.fair_odds);
  const modelChancePct = asNumber(raw.model_chance_pct);
  const marketChancePct = asNumber(raw.market_chance_pct);
  const priceGapPp = asNumber(raw.price_gap_pp);
  const goalsScored = asNumber(raw.goals_scored) ?? 1;
  const superSubReplacementGoals = asNumber(raw.super_sub_replacement_goals);
  const player = asText(raw.player);
  const match = asText(raw.match);

  if (
    !player ||
    !match ||
    bestOdds === null ||
    fairOdds === null ||
    modelChancePct === null ||
    marketChancePct === null ||
    priceGapPp === null
  ) {
    return null;
  }

  return {
    id: asText(raw.id, `${asText(raw.date)}-${player}-${match}`),
    date: asText(raw.date),
    kickoff: asText(raw.kickoff) || undefined,
    competition: asText(raw.competition, "Football"),
    league: asText(raw.league) || undefined,
    match,
    player,
    team: asText(raw.team) || undefined,
    bestBookmaker: asText(raw.best_bookmaker, "Bet365 reference"),
    bestOdds,
    fairOdds,
    modelChancePct,
    marketChancePct,
    priceGapPp,
    goalsScored,
    superSubWin: Boolean(raw.super_sub_win),
    superSubReplacement: asText(raw.super_sub_replacement) || undefined,
    superSubReplacementGoals: superSubReplacementGoals ?? undefined,
    settledAt: asText(raw.settled_at) || undefined,
  };
}

function parseLabHighlights(parsed: unknown): LabHighlight[] | null {
  const raw = asRecord(parsed);
  if (!Array.isArray(raw.highlights)) return null;

  return raw.highlights
    .map(mapHighlight)
    .filter((highlight: LabHighlight | null): highlight is LabHighlight => highlight !== null);
}

async function readLabHighlights(): Promise<LabHighlight[]> {
  const remoteHighlights = parseLabHighlights(
    await fetchRemoteJson(process.env.FAIR_ODDS_LAB_HIGHLIGHTS_URL, "highlights"),
  );
  if (remoteHighlights) return remoteHighlights;

  return parseLabHighlights(readLocalJson("highlights.json")) ?? [];
}

function formatOdds(value: number) {
  return value.toFixed(2);
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

function formatHighlightDate(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value || "Recent";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(timestamp);
}

function formatTicketDate(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value || "Recent";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(timestamp);
}

function splitMatchTeams(match: string) {
  const parts = match.split(/\s+(?:vs|v)\s+/i).map((part) => part.trim()).filter(Boolean);
  return {
    home: parts[0] ?? "",
    away: parts[1] ?? "",
  };
}

function teamsMatch(a: string | undefined, b: string | undefined) {
  const left = normalizeTeamKey(a);
  const right = normalizeTeamKey(b);
  return Boolean(left && right && (left === right || left.includes(right) || right.includes(left)));
}

function resolveHighlightTeams(highlight: LabHighlight) {
  const { home, away } = splitMatchTeams(highlight.match);
  const team = highlight.team || home;
  const opponent = teamsMatch(team, home) ? away : teamsMatch(team, away) ? home : away || home;
  return {
    team,
    opponent,
    home,
    away,
  };
}

function HitTicket({ highlight }: { highlight: LabHighlight }) {
  const teams = resolveHighlightTeams(highlight);
  const style = resolveTeamStyle(teams.team);
  const teamLogoPath = resolveTeamLogoPath(highlight.league ?? "", teams.team);
  const opponentLogoPath = resolveTeamLogoPath(highlight.league ?? "", teams.opponent);
  const leagueLogoPath = highlight.league ? `/league-logos/${highlight.league}.png` : "";
  const stateLabel = highlight.superSubWin ? "Super Sub hit" : highlight.goalsScored > 1 ? `Scored x${highlight.goalsScored}` : "Scored";
  const stateClass = highlight.superSubWin
    ? "border-cyan-300/30 bg-cyan-300/10 text-cyan-100"
    : "border-emerald-300/30 bg-emerald-300/10 text-emerald-100";

  return (
    <article className="group relative overflow-hidden rounded-[1.5rem] border border-slate-800/80 bg-[#090e15] p-4 transition duration-300 hover:-translate-y-1 hover:border-emerald-400/35 hover:shadow-[0_24px_60px_rgba(16,185,129,0.12)]">
      <div className="pointer-events-none absolute -right-14 -top-14 h-32 w-32 rounded-full bg-emerald-300/[0.08] blur-2xl transition group-hover:bg-emerald-300/[0.14]" />
      <div className="relative flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
          <LogoBadge
            src={leagueLogoPath}
            alt={`${highlight.competition} logo`}
            fallback={highlight.competition}
            size={24}
            shape="rounded"
            className="bg-white/95 p-1"
          />
          <span className="truncate">{highlight.competition}</span>
        </div>
        <span className="shrink-0 font-mono text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
          {formatTicketDate(highlight.date)}
        </span>
      </div>

      <div className="relative mt-4 border-t border-dashed border-slate-700/50 pt-4">
        <div className="flex gap-4">
          <div className="w-[72px] shrink-0">
            <AbstractJersey
              teamLogoPath={teamLogoPath}
              teamPrimaryColor={style?.primary ?? "#10b981"}
              teamSecondaryColor={style?.secondary ?? "#0f172a"}
              shirtPattern={style?.pattern ?? "solid"}
              accentEmerald={false}
            />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="break-words text-2xl font-black leading-tight tracking-tight text-slate-50">
              {highlight.player}
            </h3>
            <div className="mt-1 text-sm font-semibold text-slate-500">
              {teams.team}
            </div>
            <div className="mt-3 flex min-w-0 items-center gap-2 rounded-xl border border-slate-800/80 bg-slate-950/55 px-3 py-2">
              <LogoBadge
                src={teamLogoPath}
                alt={`${teams.team} logo`}
                fallback={teams.team}
                size={24}
              />
              <span className="min-w-0 truncate text-xs font-semibold text-slate-300">
                {teams.team}
              </span>
              <span className="shrink-0 text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
                vs
              </span>
              <LogoBadge
                src={opponentLogoPath}
                alt={`${teams.opponent} logo`}
                fallback={teams.opponent}
                size={24}
              />
              <span className="min-w-0 truncate text-xs font-semibold text-slate-300">
                {teams.opponent}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-950/70">
          <div className="p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-emerald-200/80">
              Fair
            </div>
            <div className="mt-1 font-mono text-2xl font-black text-emerald-100">
              {formatOdds(highlight.fairOdds)}
            </div>
          </div>
          <div className="border-l border-slate-800/80 p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-slate-500">
              Reference
            </div>
            <div className="mt-1 flex min-w-0 flex-col items-start gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
              <span className="font-mono text-2xl font-black text-slate-100">
                {formatOdds(highlight.bestOdds)}
              </span>
              <BookmakerLogo name={highlight.bestBookmaker} size="xs" className="sm:h-6 sm:min-w-12 sm:max-w-none sm:px-2.5" />
            </div>
          </div>
          <div className="border-l border-amber-300/20 bg-amber-300/[0.065] p-3">
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-amber-100/80">
              Gap
            </div>
            <div className="mt-1 font-mono text-2xl font-black text-amber-100">
              +{highlight.priceGapPp.toFixed(1)}
            </div>
            <div className="text-[9px] font-black uppercase tracking-[0.14em] text-amber-100/60">
              pp
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 border-t border-dashed border-slate-700/45 pt-4">
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-black uppercase tracking-[0.14em] ${stateClass}`}>
            <span className="inline-flex h-4 w-4 animate-pulse items-center justify-center rounded-full bg-white/10">
              &#10003;
            </span>
            {stateLabel}
          </span>
          <span className="font-mono text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">
            Lab pick · {formatHighlightDate(highlight.date)}
          </span>
        </div>

        <div className="mt-3 text-xs leading-5 text-slate-500">
          Reference: {highlight.bestBookmaker} · Lab vs market gap.
        </div>
      </div>
    </article>
  );
}

function LabHitsSection({ highlights }: { highlights: LabHighlight[] }) {
  if (!highlights.length) return null;
  const visibleHighlights = highlights.slice(0, 6);

  return (
    <section id="lab-hits" className="mt-16">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.22em] text-emerald-300">
            Lab hits
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-50">
            The model said value. The player scored.
          </h2>
        </div>
        <Link
          href="/fair-odds-lab#lab-hits"
          className="text-xs font-black uppercase tracking-[0.16em] text-emerald-200 transition hover:text-emerald-100"
        >
          Recent flagged hits &rarr;
        </Link>
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
        Recent value spots the Lab flagged where the named player went on to
        score. This is not an official goalscorer track record; official settled
        picks live on the Track Record page.
      </p>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleHighlights.map((highlight) => (
          <HitTicket key={highlight.id} highlight={highlight} />
        ))}
      </div>
    </section>
  );
}

function SuperSubExplainer() {
  return (
    <details className="group mt-16 overflow-hidden rounded-2xl border border-slate-700/55 bg-[#080d14]/85 shadow-[0_22px_90px_rgba(0,0,0,0.28)]">
      <summary className="flex cursor-pointer list-none flex-col gap-3 px-5 py-5 transition hover:bg-emerald-300/[0.035] sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Bookmaker edge layer
          </div>
          <h2 className="mt-2 text-xl font-black tracking-tight text-slate-50 sm:text-2xl">
            Why Bet365 Super Sub can add protection
          </h2>
        </div>
        <span className="inline-flex items-center justify-center rounded-full border border-emerald-300/25 bg-emerald-300/[0.08] px-3 py-1.5 text-xs font-black uppercase tracking-[0.14em] text-emerald-100">
          Read explainer
          <span className="ml-2 transition group-open:rotate-180">v</span>
        </span>
      </summary>

      <div className="grid gap-0 border-t border-slate-800/80 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="p-5 sm:p-6">
          <p className="text-sm leading-7 text-slate-300">
            The model prices the named player only. It does not add extra value
            for bookmaker promotions such as bet365&apos;s Sub On Play On, where
            eligible player-market bets can roll to the direct replacement if
            your player is substituted. When that icon is available, the real
            bet can have more protection than the fair odds shown here.
          </p>
          <p className="mt-3 text-xs leading-6 text-slate-500">
            This page uses Bet365 as the reference price where available because
            its anytime-goalscorer markets commonly carry Sub On Play On terms.
            It is not a claim that Bet365 is the top price everywhere. Compare
            your own available bookies before betting; if we publish an
            official goalscorer tip, we will specify the bookie and odds used.
          </p>
          <p className="mt-2 text-xs leading-6 text-slate-500">
            Availability depends on the bookmaker, match, market, jurisdiction
            and account eligibility. Always check the betslip icon and the
            bookmaker rules before placing a bet.
          </p>
        </div>
        <div className="border-t border-slate-800/80 bg-slate-950/50 p-5 lg:border-l lg:border-t-0">
          <div className="grid gap-3">
            {[
              ["Model price", "Named player only"],
              ["Reference book", "Bet365 for simple comparison"],
              ["Why it matters", "Replacement can keep the bet alive"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3">
                <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  {label}
                </div>
                <div className="mt-1 font-mono text-sm font-black text-slate-100">
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </details>
  );
}

function buildFairOddsLabStructuredData({
  signals,
  highlights,
  generatedAt,
}: {
  signals: Signal[];
  highlights: LabHighlight[];
  generatedAt: string | null;
}) {
  const pageUrl = `${BASE_URL}/fair-odds-lab`;
  const topSignals = signals.slice(0, 8);

  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: "Goalscorer Fair Odds Lab",
        description:
          "Anytime goalscorer value spots where Il Margine compares model fair odds with bookmaker market prices and explains bookmaker-dependent Super Sub upside.",
        isPartOf: {
          "@type": "WebSite",
          "@id": `${BASE_URL}/#website`,
          name: "Il Margine",
          url: BASE_URL,
        },
        about: [
          "anytime goalscorer odds",
          "football betting model",
          "fair odds",
          "goalscorer value spots",
          "Super Sub goalscorer betting",
          "Sub On Play On",
        ],
        dateModified: generatedAt ?? new Date().toISOString(),
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${pageUrl}#breadcrumb`,
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: "Home",
            item: BASE_URL,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: "Goalscorer Fair Odds Lab",
            item: pageUrl,
          },
        ],
      },
      {
        "@type": "FAQPage",
        "@id": `${pageUrl}#super-sub-faq`,
        mainEntity: [
          {
            "@type": "Question",
            name: "Does the Fair Odds Lab include Super Sub in the model price?",
            acceptedAnswer: {
              "@type": "Answer",
              text:
                "No. The model prices the named player only. If a bookmaker offers a Sub On Play On or Super Sub feature on the same market, that is treated as extra bookmaker-dependent protection on top of the displayed fair odds.",
            },
          },
          {
            "@type": "Question",
            name: "Can a replacement player make a goalscorer bet win?",
            acceptedAnswer: {
              "@type": "Answer",
              text:
                "On selected player markets where the bookmaker displays the relevant Sub On Play On or Super Sub icon, the bet may roll to the direct replacement if the named player is substituted. Availability and settlement depend on bookmaker rules.",
            },
          },
          {
            "@type": "Question",
            name: "Why does the page use Bet365 as the reference price?",
            acceptedAnswer: {
              "@type": "Answer",
              text:
                "Bet365 is used as a simple reference because its anytime-goalscorer markets are widely available and commonly carry Sub On Play On terms. It is not a claim that Bet365 is the top price everywhere. Compare your own available bookies, and if Il Margine publishes an official goalscorer tip we will specify the bookie and odds used.",
            },
          },
        ],
      },
      ...(topSignals.length
        ? [
            {
              "@type": "ItemList",
              "@id": `${pageUrl}#current-signals`,
              name: "Current goalscorer value spots",
              itemListElement: topSignals.map((signal, index) => ({
                "@type": "ListItem",
                position: index + 1,
                item: {
                  "@type": "Thing",
                  name: `${signal.player} anytime goalscorer value spot`,
                  description: `${signal.player} in ${signal.match}: Il Margine fair odds ${formatOdds(
                    signal.fairOdds,
                  )}, Bet365 reference price ${formatOdds(signal.bestBookOdds)}.`,
                  url: pageUrl,
                },
              })),
            },
          ]
        : []),
      ...(highlights.length
        ? [
            {
              "@type": "ItemList",
              "@id": `${pageUrl}#recently-flagged`,
              name: "Recently flagged goalscorer hits",
              itemListElement: highlights.slice(0, 6).map((highlight, index) => ({
                "@type": "ListItem",
                position: index + 1,
                item: {
                  "@type": "Thing",
                  name: `${highlight.player} scored after being flagged by the Fair Odds Lab`,
                  description: `${highlight.player} was flagged in ${highlight.match} at market odds ${formatOdds(
                    highlight.bestOdds,
                  )}.`,
                  url: pageUrl,
                },
              })),
            },
          ]
        : []),
    ],
  };
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
        No flagged value spots right now
      </h2>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
        The latest board does not have a goalscorer price strong enough to
        show. That is intentional: if the edge is not clear, the lab stays
        quiet. Pre-match signals stay visible as locked watch cards after
        kickoff, then clear once the match window closes.
      </p>
    </section>
  );
}

type FairOddsLabPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function FairOddsLabPage({ searchParams }: FairOddsLabPageProps) {
  const artifact = await readLabArtifact();
  const highlights = await readLabHighlights();
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const embedParam = resolvedSearchParams.embed;
  const isEmbed = Array.isArray(embedParam) ? embedParam.includes("1") : embedParam === "1";
  const featured =
    artifact.signals.find((signal) => signal.id === artifact.featuredSignalId) ??
    artifact.signals[0];
  const signals = featured
    ? [featured, ...artifact.signals.filter((signal) => signal.id !== featured.id)]
    : artifact.signals;
  const leagueCount = new Set(signals.map((signal) => signal.competition)).size;
  const inPlayCount = signals.filter((signal) => signal.displayStatus === "in_play").length;
  const boardStatus = featured ? featured.player : "Quiet board";
  const coverageLabel = leagueCount.toString();
  const refreshedLabel = formatRefreshed(artifact.generatedAt);
  const structuredData = buildFairOddsLabStructuredData({
    signals,
    highlights,
    generatedAt: artifact.generatedAt,
  });

  return (
    <main className="min-h-screen overflow-hidden bg-[#05070b] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
      {!isEmbed ? (
        <>
          <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_10%_8%,rgba(16,185,129,0.2),transparent_28%),radial-gradient(circle_at_84%_10%,rgba(14,165,233,0.18),transparent_30%),radial-gradient(circle_at_50%_88%,rgba(245,158,11,0.1),transparent_30%),linear-gradient(rgba(148,163,184,0.028)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.028)_1px,transparent_1px)] bg-[size:auto,auto,auto,42px_42px,42px_42px]" />
          <div className="pointer-events-none fixed inset-x-0 top-0 h-40 bg-gradient-to-b from-emerald-300/[0.08] to-transparent" />
        </>
      ) : null}

      <div className={`relative mx-auto ${isEmbed ? "max-w-6xl px-3 py-3 sm:px-4 sm:py-4" : "max-w-7xl px-3 py-4 sm:px-6 sm:py-8 lg:px-8 lg:py-10"}`}>
        {!isEmbed ? (
          <section className="relative overflow-hidden rounded-[1.5rem] border border-emerald-300/20 bg-slate-950/70 p-4 shadow-[0_28px_120px_rgba(0,0,0,0.5)] sm:rounded-[1.75rem] sm:p-6">
            <div className="pointer-events-none absolute -left-24 top-0 h-64 w-64 rounded-full bg-emerald-400/[0.08] blur-3xl" />
            <div className="pointer-events-none absolute -right-20 -top-28 h-80 w-80 rounded-full border-[30px] border-cyan-300/[0.06]" />
            <div className="relative grid gap-4 sm:gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(520px,0.95fr)] lg:items-end">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-emerald-400/35 bg-emerald-400/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-emerald-200">
                    Il Margine Intelligence
                  </span>
                  <span className="rounded-full border border-slate-700/70 bg-slate-900/70 px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-slate-300">
                    Goalscorer value spots
                  </span>
                </div>
                <h1 className="mt-4 max-w-3xl text-4xl font-black leading-[0.95] tracking-tight text-slate-50 sm:text-5xl">
                  Goalscorer Fair Odds Lab
                </h1>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base sm:leading-7">
                  Where our model price is shorter than the bookies&apos;.
                </p>
                <Link
                  href="/resources/fair-odds-lab-explained"
                  className="mt-4 inline-flex text-xs font-bold uppercase tracking-[0.14em] text-emerald-300 transition hover:text-emerald-200"
                >
                  How to read fair odds and value gaps -&gt;
                </Link>
              </div>

              <div className="grid grid-cols-2 gap-0 overflow-hidden rounded-2xl border border-slate-700/55 bg-slate-950/75 sm:grid-cols-4">
                {[
                  ["Top value spot", boardStatus],
                  ["Flagged spots", signals.length.toString()],
                  ["Competitions", coverageLabel],
                  ["Updated", refreshedLabel],
                ].map(([label, value], index) => (
                  <div
                    key={label}
                    className={`px-3 py-3 sm:px-4 sm:py-4 ${
                      index >= 2 ? "border-t border-slate-800/80 sm:border-t-0" : ""
                    } ${index > 0 ? "sm:border-l sm:border-slate-800/80" : ""} ${
                      index === 1 || index === 3 ? "border-l border-slate-800/80" : ""
                    }`}
                  >
                    <div className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-500 sm:text-[10px] sm:tracking-[0.2em]">
                      {label}
                    </div>
                    <div className="mt-1 break-words font-mono text-lg font-black text-slate-100 sm:text-xl">
                      {value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : null}

        {!featured ? (
          <section className={isEmbed ? "mt-0" : "mt-8"}>
            <EmptySignalsState />
          </section>
        ) : null}

        {signals.length > 0 ? (
          <>
            <FairOddsSignalBrowser
              artifact={{ ...artifact, signals }}
              featuredSignalId={featured?.id ?? null}
              embed={isEmbed}
            />
            {!isEmbed ? (
              <p className="mt-3 px-2 text-xs leading-5 text-slate-500">
                Reference prices are taken from Bet365 to keep value spots
                comparable. This does not claim Bet365 beats every book.
                Prices and team news can move; likely starters update to
                Confirmed XI when official teams land. After kickoff, flagged
                spots stay visible as locked watch cards until the match window
                closes{inPlayCount > 0 ? ` (${inPlayCount} live now)` : ""}.
              </p>
            ) : null}
          </>
        ) : null}

        {!isEmbed ? (
          <>
            <LabHitsSection highlights={highlights} />
            <SuperSubExplainer />
            <div className="mt-12 flex flex-col gap-3 border-t border-slate-800/60 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-xs leading-5 text-slate-500">
                Goalscorer Fair Odds Lab · Model research, not official picks
              </span>
              <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300/80">
                Powered by Il Margine
              </span>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}


