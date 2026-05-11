import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import teamLogoManifest from "../../../data/goalscorer/team-logo-map.json";
import { FairOddsSignalBrowser } from "@/components/fair-odds-lab/FairOddsSignalBrowser";
import { sampleSignals } from "@/components/fair-odds-lab/__fixtures__/sample-signals";
import type { LabArtifact, LabHighlight, Signal } from "@/components/fair-odds-lab/types";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Anytime Goalscorer Value Spots | Goalscorer Fair Odds Lab",
  description:
    "Live anytime goalscorer value spots from Il Margine, comparing our model's fair odds with bookmaker prices for likely and confirmed starters.",
  keywords: [
    "anytime goalscorer tips",
    "goalscorer value bets",
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
      "Anytime goalscorer value spots where Il Margine's model price is shorter than the bookmaker market price.",
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
      "Anytime goalscorer value spots where Il Margine's model price is shorter than the bookmaker market price.",
    images: [`${BASE_URL}/og.png`],
  },
};

export const dynamic = "force-dynamic";
const REMOTE_ARTIFACT_REVALIDATE_SECONDS = 300;

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
  if (signal.kickoffUtc) {
    const kickoffMs = Date.parse(signal.kickoffUtc);
    return Number.isFinite(kickoffMs) && kickoffMs > nowMs;
  }

  const dateOnly = signal.kickoff.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!dateOnly) return false;

  const [, year, month, day] = dateOnly;
  const fallbackDateMs = Date.UTC(Number(year), Number(month) - 1, Number(day));
  const now = new Date(nowMs);
  const todayStartMs = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());

  // Date-only rows are safe to show only for future dates; same-day rows need an exact kickoff.
  return Number.isFinite(fallbackDateMs) && fallbackDateMs > todayStartMs;
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

  const artifactSignals = raw.signals
    .map(mapArtifactSignal)
    .filter((signal: Signal | null): signal is Signal => signal !== null)
    .filter((signal: Signal) => isPreKickoffSignal(signal));

  return {
    generatedAt: asText(raw.generated_at) || null,
    edgeThresholdPp: asNumber(raw.edge_threshold_pp) ?? 6,
    fixturesEvaluated: asNumber(raw.fixtures_evaluated) ?? 0,
    signalsQualifying: asNumber(raw.signals_qualifying) ?? artifactSignals.length,
    leaguesCovered: Array.isArray(raw.leagues_covered)
      ? raw.leagues_covered.map((league: unknown) => asText(league)).filter(Boolean)
      : [],
    featuredSignalId: asText(raw.featured_signal_id) || artifactSignals[0]?.id,
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
    bestBookmaker: asText(raw.best_bookmaker, "Best market"),
    bestOdds,
    fairOdds,
    modelChancePct,
    marketChancePct,
    priceGapPp,
    goalsScored,
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

function formatHighlightDate(value: string) {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value || "Recent";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "Europe/London",
  }).format(timestamp);
}

function LabHitsSection({ highlights }: { highlights: LabHighlight[] }) {
  if (!highlights.length) return null;
  const gridColumns = highlights.length >= 3 ? "md:grid-cols-2 xl:grid-cols-3" : "md:grid-cols-2";

  return (
    <section className="mt-8 overflow-hidden rounded-[2rem] border border-emerald-400/20 bg-[#0c0f14] shadow-[0_24px_90px_rgba(0,0,0,0.28)]">
      <div className="flex flex-col gap-3 border-b border-slate-800/80 px-5 py-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-300">
            Lab hits
          </div>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-50">
            Flagged by the model. Finished by the player.
          </h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-slate-400">
          Winning goalscorer value spots recently surfaced by the Fair Odds Lab.
        </p>
      </div>

      <div className={`grid gap-px bg-slate-800/70 ${gridColumns}`}>
        {highlights.map((highlight) => (
          <article key={highlight.id} className="bg-[#0c0f14] p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {formatHighlightDate(highlight.date)} | {highlight.competition}
                </div>
                <h3 className="mt-3 text-2xl font-black leading-tight tracking-tight text-slate-50">
                  {highlight.player}
                </h3>
                <div className="mt-1 truncate text-sm text-slate-500">{highlight.match}</div>
              </div>
              <span className="shrink-0 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-black uppercase tracking-[0.14em] text-emerald-200">
                Scored
              </span>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Fair
                </div>
                <div className="mt-1 font-mono text-xl font-black text-emerald-200">
                  {formatOdds(highlight.fairOdds)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-3">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Market
                </div>
                <div className="mt-1 font-mono text-xl font-black text-slate-100">
                  {formatOdds(highlight.bestOdds)}
                </div>
              </div>
              <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.07] p-3">
                <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-200/80">
                  Gap
                </div>
                <div className="mt-1 font-mono text-xl font-black text-amber-200">
                  +{highlight.priceGapPp.toFixed(1)}pp
                </div>
              </div>
            </div>

            <div className="mt-4 text-sm leading-6 text-slate-400">
              The Lab priced him shorter than {highlight.bestBookmaker}&apos;s market price.
              {highlight.goalsScored > 1 ? ` He scored ${highlight.goalsScored}.` : ""}
            </div>
          </article>
        ))}
      </div>
    </section>
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
          "Anytime goalscorer value spots where Il Margine compares model fair odds with bookmaker market prices.",
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
                  )}, market price ${formatOdds(signal.bestBookOdds)}.`,
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
        No current value spots right now
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

export default async function FairOddsLabPage() {
  const artifact = await readLabArtifact();
  const highlights = await readLabHighlights();
  const featured =
    artifact.signals.find((signal) => signal.id === artifact.featuredSignalId) ??
    artifact.signals[0];
  const signals = featured
    ? [featured, ...artifact.signals.filter((signal) => signal.id !== featured.id)]
    : artifact.signals;
  const leagueCount = new Set(signals.map((signal) => signal.competition)).size;
  const boardStatus = featured ? featured.player : "Quiet board";
  const coverageLabel = leagueCount.toString();
  const refreshedLabel = formatRefreshed(artifact.generatedAt);
  const structuredData = buildFairOddsLabStructuredData({
    signals,
    highlights,
    generatedAt: artifact.generatedAt,
  });

  return (
    <main className="min-h-screen overflow-hidden bg-[#07090d] text-slate-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />
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
              ["Top value spot", boardStatus],
              ["Current spots", signals.length.toString()],
              ["Competitions", coverageLabel],
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

        <section className="mt-5 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.055] px-4 py-3 text-sm leading-6 text-emerald-100 sm:px-5">
          Intelligence board. Prices and team news can move. Likely starters
          update to Confirmed XI when official teams land, or drop out if the
          lineup no longer supports the signal.
        </section>

        <section className="mt-5">
          <div className="rounded-2xl border border-slate-700/45 bg-[#0c0f14] p-5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
              How to read this
            </div>
            {featured ? (
              <p className="mt-3 text-sm leading-7 text-slate-300">
                The model estimates a player&apos;s true chance of scoring. If our
                fair odds are {formatOdds(featured.fairOdds)} and the bookmaker
                offers {formatOdds(featured.bestBookOdds)}, the bookmaker is
                paying more than our price says it should. In plain words, a{" "}
                {`+${probabilityGap(featured).toFixed(1)}pp`} gap means our
                model sees a bigger scoring chance than the market price
                implies.
              </p>
            ) : (
              <p className="mt-3 text-sm leading-7 text-slate-300">
                The model estimates a player&apos;s true chance of scoring and
                compares that fair price with the bookmaker&apos;s market price.
                When our price is shorter than the market, the difference is a
                probability gap: the model sees a bigger scoring chance than
                the odds imply.
              </p>
            )}
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

        <LabHitsSection highlights={highlights} />

      </div>
    </main>
  );
}


