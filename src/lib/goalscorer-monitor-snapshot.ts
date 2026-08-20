import "server-only";

import path from "node:path";
import { promises as fs } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { getSupabaseAdmin } from "@/lib/supabase-server";

export type GoalscorerSnapshotStatusKey = "live_file" | "no_feed" | "not_run";

export type GoalscorerLeagueCard = {
  key: string;
  label: string;
  status_key: GoalscorerSnapshotStatusKey;
  status_label: string;
  status_detail?: string;
  updated_at: string | null;
  live_rows: number;
  public_now: number;
  shadow_now: number;
  clean_fixtures: number;
  degraded_fixtures: number;
  quarantined_fixtures: number;
  public_record: {
    settled: number;
    wins: number;
    losses: number;
    roi: number;
    pnl_units: number;
  };
  shadow_record: {
    signals: number;
    settled: number;
    open: number;
    wins: number;
    losses: number;
    voids: number;
    roi: number;
    pnl_units: number;
  };
};

export type GoalscorerLiveBetRow = {
  key: string;
  status: "PUBLIC" | "SHADOW";
  action: string;
  action_label: string;
  league_key: string;
  league_label: string;
  competition: string;
  player: string;
  team: string;
  opponent: string;
  match: string;
  match_date: string;
  kickoff: string;
  bookmaker: string;
  lineup_short: string;
  lineup_label: string;
  lineup_status: string;
  odds: number | null;
  fair: number | null;
  edge_pct: number | null;
  stake_label: string;
};

export type GoalscorerSettledRow = {
  key: string;
  player: string;
  team: string;
  match: string;
  competition: string;
  league_key: string;
  kickoff: string;
  compared_at: string;
  settled_at: string;
  date: string;
  lineup_state: string;
  best_bookmaker_odds: number | null;
  model_fair_odds: number | null;
  ev_pct: number | null;
  settled: boolean;
  bet_outcome: string;
  settlement_note: string;
  pnl_units: number | null;
  tracking_tier?: string;
  quarantine_reason?: string;
  evaluation_stake_units?: number | null;
};

export type GoalscorerFixtureHealthRow = {
  key: string;
  league_key: string;
  league_label: string;
  match_date: string;
  home_team: string;
  away_team: string;
  competition: string;
  bookmaker: string;
  lineup_input: string;
  trust_tier: string;
  corruption_score: number | null;
  corruption_flags: string[];
  status_label: string;
  summary: string;
};

export type GoalscorerPenaltyWatchlistRow = {
  row_id: string;
  date?: string;
  league?: string;
  review_source?: string;
  review_priority?: string;
  review_type?: string;
  hierarchy_status?: string;
  match?: string;
  team?: string;
  public_team?: string;
  opponent?: string;
  actual_taker?: string;
  actual_role_pre_match?: string;
  penalties_attempted?: number;
  penalties_scored?: number;
  distinct_takers_in_match?: number;
  minute?: string;
  event_type?: string;
  event_result?: string;
  primary_pre_match?: string;
  secondary_pre_match?: string;
  tertiary_pre_match?: string;
  primary_lineup_status?: string;
  secondary_lineup_status?: string;
  tertiary_lineup_status?: string;
  active_taker_pre_match?: string;
  active_slot_pre_match?: string;
  team_lineup_status?: string;
  penalty_transfer_pre_match?: number;
  inherited_from_pre_match?: string;
  transfer_level_pre_match?: string;
  editorial_note?: string;
  context_generated_at?: string;
  context_source_path?: string;
  primary_on_pitch_at_penalty?: string;
  active_on_pitch_at_penalty?: string;
  actual_taker_on_pitch_at_penalty?: string;
};

export type GoalscorerPreseasonRoleReviewRow = {
  row_id: string;
  generated_at: string;
  season: string;
  league: string;
  team: string;
  review_source: string;
  review_priority: string;
  review_type: string;
  current_primary: string;
  current_secondary: string;
  current_tertiary: string;
  proposed_primary: string;
  fpl_penalty_order: Array<{
    order: number | null;
    player: string;
    web_name: string;
    element_id: string;
    status: string;
  }>;
  current_primary_in_fpl_roster: boolean;
  reason: string;
  editorial_note: string;
  auto_apply: false;
  status: string;
};

export type GoalscorerLineupSignal = {
  key: string;
  name: string;
  position: string;
  note: string | null;
  has_price: boolean;
  odds: number | null;
  fair: number | null;
  ev_pct: number | null;
  expected_minutes: number | null;
  action: string;
  action_label: string;
  penalty_meta: {
    compact: string;
    detail: string;
  } | null;
};

export type GoalscorerFixtureLineupTeam = {
  team: string;
  lineup_status: string;
  total_players: number;
  matched_players: number;
  keeper: GoalscorerLineupSignal | null;
  attackers: GoalscorerLineupSignal[];
  midfielders: GoalscorerLineupSignal[];
  wide_players: GoalscorerLineupSignal[];
  centre_backs: GoalscorerLineupSignal[];
  unplaced: GoalscorerLineupSignal[];
};

export type GoalscorerFixtureLineup = {
  key: string;
  league_key: string;
  league_label: string;
  competition: string;
  match_date: string;
  kickoff: string;
  bookmaker: string;
  home_team: string;
  away_team: string;
  matched_player_prices: number;
  health: GoalscorerFixtureHealthRow | null;
  home: GoalscorerFixtureLineupTeam;
  away: GoalscorerFixtureLineupTeam;
  has_any_lineup: boolean;
};

export type GoalscorerMonitorSnapshot = {
  schema_version: number;
  generated_at: string;
  source_status: {
    compared_at: string | null;
    hot_live_updated_at: string | null;
    expected_refresh_updated_at: string | null;
    settlement_updated_at: string | null;
    scheduler_heartbeat_at: string | null;
    snapshot_generated_at: string | null;
    live_status_state: string | null;
    live_status_message: string | null;
  };
  league_cards: GoalscorerLeagueCard[];
  live_bets: GoalscorerLiveBetRow[];
  fixture_health: {
    rows: GoalscorerFixtureHealthRow[];
    clean_count: number;
    degraded_count: number;
    quarantined_count: number;
    hidden_pending_count: number;
    hidden_expected_count: number;
    flagged_rows: GoalscorerFixtureHealthRow[];
  };
  fixture_lineups: GoalscorerFixtureLineup[];
  penalty_watchlist: {
    generated_at: string | null;
    row_count: number;
    rows: GoalscorerPenaltyWatchlistRow[];
  };
  preseason_role_review?: {
    generated_at: string | null;
    row_count: number;
    rows: GoalscorerPreseasonRoleReviewRow[];
  };
  shadow_summary: {
    by_league: Array<{
      key: string;
      label: string;
      signals: number;
      settled: number;
      open: number;
      wins: number;
      losses: number;
      voids: number;
      roi: number;
      pnl_units: number;
    }>;
    recent_rows: GoalscorerSettledRow[];
    settled_today: GoalscorerSettledRow[];
    settled_yesterday: GoalscorerSettledRow[];
  };
  public_summary: {
    by_league: Array<{
      key: string;
      label: string;
      settled: number;
      wins: number;
      losses: number;
      roi: number;
      pnl_units: number;
    }>;
  };
  extreme_gap_quarantine: {
    registered: number;
    settled: number;
    pending: number;
    wins: number;
    losses: number;
    voids: number;
    staked_units: number;
    pnl_units: number;
    roi: number | null;
    by_league: Array<{
      key: string;
      label: string;
      registered: number;
      settled: number;
      pending: number;
      wins: number;
      losses: number;
      voids: number;
      staked_units: number;
      pnl_units: number;
      roi: number | null;
    }>;
    recent_rows: GoalscorerSettledRow[];
  };
  diagnostics: {
    matched_rows: number;
    suppressed_rows: number;
    fixtures_with_confirmed_lineups: number;
    fixtures_with_expected_xis: number;
    history_mapped_rows: number;
    roster_mapped_rows: number;
    fallback_rows: number;
    low_confidence_rows: number;
    missing_player_history_rows: number;
    starter_rows: number;
    expected_starter_rows: number;
    avg_ev_pct: number | null;
    source_feed_gap_leagues: Array<{
      key: string;
      label: string;
      detail: string;
    }>;
    raw_monitor_summary: string;
  };
  research_status?: {
    status: "RESEARCH_ONLY";
    model_variant: string;
    updated_at: string | null;
    parity: {
      decision: string;
      golden_rows: number;
      mean_abs_delta: number | null;
      max_abs_delta: number | null;
      gate: number | null;
    };
    calibration: {
      candidate: string;
      n: number;
      brier: number | null;
      log_loss: number | null;
      ece: number | null;
      predicted: number | null;
      actual: number | null;
      raw_brier: number | null;
      raw_log_loss: number | null;
      raw_ece: number | null;
      evaluated_folds: number;
      fold_wins: number;
      probability_gate: string;
      market_roi_gate: string;
      decision: string;
    };
    segments: {
      rows: number;
      position_sub_rows: number;
      minutes_gap_pct: number | null;
      minutes_gate: string;
    };
    clv: {
      signals: number;
      captures_loaded: number;
      matched: number;
      coverage_pct: number;
      true_closes: number;
      lagged_closes: number;
      pinnacle_references: number;
      missing: number;
    };
  };
};

const SNAPSHOT_TABLE = "goalscorer_live_snapshot";
const SNAPSHOT_KEY = process.env.GOALSCORER_MONITOR_SNAPSHOT_KEY || "monitor_state";
const LOCAL_SNAPSHOT_FILE = "data/goalscorer/goalscorer-monitor-snapshot.json";
const GITHUB_RAW_BASE =
  process.env.MONITOR_GITHUB_RAW_BASE ||
  "https://raw.githubusercontent.com/simonreds76-gif/il-margine/golden-with-speed-insights";
const GIT_REMOTE_REF = process.env.MONITOR_GIT_REMOTE_REF || "origin/golden-with-speed-insights";
const CACHE_TTL_MS = process.env.NODE_ENV === "development" ? 15 * 1000 : 5 * 60 * 1000;
const execFileAsync = promisify(execFile);

let cache: { expiresAt: number; payload: GoalscorerMonitorSnapshot | null } | null = null;

function repairMojibakeString(value: string): string {
  if (!/[ÃÂâÎ\ufffd]/.test(value)) return value;
  try {
    const repaired = Buffer.from(value, "latin1").toString("utf8");
    if (repaired) return repaired;
  } catch {
    // Fall through to the original value.
  }
  return value;
}

function repairSnapshotValue<T>(value: T): T {
  if (typeof value === "string") {
    return repairMojibakeString(value) as T;
  }
  if (Array.isArray(value)) {
    return value.map((item) => repairSnapshotValue(item)) as T;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, innerValue]) => [key, repairSnapshotValue(innerValue)]),
    ) as T;
  }
  return value;
}

function parseSnapshotTimestamp(value?: string | null): number {
  if (!value) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
}

function snapshotFreshness(payload: GoalscorerMonitorSnapshot | null): number {
  if (!payload) return Number.NEGATIVE_INFINITY;
  return Math.max(
    parseSnapshotTimestamp(payload.source_status?.compared_at),
    parseSnapshotTimestamp(payload.source_status?.settlement_updated_at),
    parseSnapshotTimestamp(payload.source_status?.expected_refresh_updated_at),
    parseSnapshotTimestamp(payload.source_status?.hot_live_updated_at),
    parseSnapshotTimestamp(payload.preseason_role_review?.generated_at),
    parseSnapshotTimestamp(payload.generated_at),
  );
}

function derivePnlUnits(row: GoalscorerSettledRow): number | null {
  if (row.pnl_units !== null && row.pnl_units !== undefined && Number.isFinite(row.pnl_units)) {
    return row.pnl_units;
  }
  const outcome = (row.bet_outcome || "").toLowerCase();
  if (outcome.includes("lost")) return -1;
  if (outcome.includes("void") || outcome.includes("push")) return 0;
  if (outcome.includes("won")) {
    const odds = row.best_bookmaker_odds;
    return odds !== null && odds !== undefined && Number.isFinite(odds) ? odds - 1 : null;
  }
  return null;
}

function normalizeSettledRows(rows: GoalscorerSettledRow[] | undefined): GoalscorerSettledRow[] {
  return [...(rows || [])]
    .filter((row) => row?.settled || Boolean(row?.bet_outcome) || Boolean(row?.settled_at))
    .map((row) => ({
      ...row,
      pnl_units: derivePnlUnits(row),
    }))
    .sort((left, right) => {
      const leftTs = parseSnapshotTimestamp(left?.settled_at || left?.compared_at || left?.kickoff || left?.date);
      const rightTs = parseSnapshotTimestamp(right?.settled_at || right?.compared_at || right?.kickoff || right?.date);
      return rightTs - leftTs;
    });
}

function normalizeSnapshot(payload: GoalscorerMonitorSnapshot | null): GoalscorerMonitorSnapshot | null {
  if (!payload) return null;
  payload = repairSnapshotValue(payload);
  const fixtureHealthRows = payload.fixture_health?.rows || [];
  const flaggedRows =
    payload.fixture_health?.flagged_rows ||
    fixtureHealthRows.filter((row) => row?.trust_tier === "T3" || (row?.corruption_score || 0) > 0);
  const diagnostics = payload.diagnostics || {
    matched_rows: 0,
    suppressed_rows: 0,
    fixtures_with_confirmed_lineups: 0,
    fixtures_with_expected_xis: 0,
    history_mapped_rows: 0,
    roster_mapped_rows: 0,
    fallback_rows: 0,
    low_confidence_rows: 0,
    missing_player_history_rows: 0,
    starter_rows: 0,
    expected_starter_rows: 0,
    avg_ev_pct: null,
    source_feed_gap_leagues: [],
    raw_monitor_summary: "",
  };
  return {
    ...payload,
    fixture_health: {
      rows: fixtureHealthRows,
      clean_count:
        payload.fixture_health?.clean_count ??
        fixtureHealthRows.filter((row) => row?.trust_tier === "T1").length,
      degraded_count:
        payload.fixture_health?.degraded_count ??
        fixtureHealthRows.filter((row) => row?.trust_tier === "T2").length,
      quarantined_count:
        payload.fixture_health?.quarantined_count ??
        fixtureHealthRows.filter((row) => row?.trust_tier === "T3").length,
      hidden_pending_count: payload.fixture_health?.hidden_pending_count ?? 0,
      hidden_expected_count: payload.fixture_health?.hidden_expected_count ?? 0,
      flagged_rows: flaggedRows,
    },
    shadow_summary: {
      ...payload.shadow_summary,
      recent_rows: normalizeSettledRows(payload.shadow_summary?.recent_rows).slice(0, 50),
      settled_today: normalizeSettledRows(payload.shadow_summary?.settled_today),
      settled_yesterday: normalizeSettledRows(payload.shadow_summary?.settled_yesterday),
    },
    extreme_gap_quarantine: {
      registered: payload.extreme_gap_quarantine?.registered ?? 0,
      settled: payload.extreme_gap_quarantine?.settled ?? 0,
      pending: payload.extreme_gap_quarantine?.pending ?? 0,
      wins: payload.extreme_gap_quarantine?.wins ?? 0,
      losses: payload.extreme_gap_quarantine?.losses ?? 0,
      voids: payload.extreme_gap_quarantine?.voids ?? 0,
      staked_units: payload.extreme_gap_quarantine?.staked_units ?? 0,
      pnl_units: payload.extreme_gap_quarantine?.pnl_units ?? 0,
      roi: payload.extreme_gap_quarantine?.roi ?? null,
      by_league: payload.extreme_gap_quarantine?.by_league ?? [],
      recent_rows: normalizeSettledRows(payload.extreme_gap_quarantine?.recent_rows).slice(0, 50),
    },
    research_status: payload.research_status
      ? {
          ...payload.research_status,
          calibration: {
            ...payload.research_status.calibration,
            raw_brier: payload.research_status.calibration?.raw_brier ?? null,
            raw_log_loss: payload.research_status.calibration?.raw_log_loss ?? null,
            raw_ece: payload.research_status.calibration?.raw_ece ?? null,
          },
        }
      : undefined,
    preseason_role_review: payload.preseason_role_review || {
      generated_at: null,
      row_count: 0,
      rows: [],
    },
    diagnostics: {
      matched_rows: diagnostics.matched_rows ?? 0,
      suppressed_rows: diagnostics.suppressed_rows ?? 0,
      fixtures_with_confirmed_lineups: diagnostics.fixtures_with_confirmed_lineups ?? 0,
      fixtures_with_expected_xis: diagnostics.fixtures_with_expected_xis ?? 0,
      history_mapped_rows: diagnostics.history_mapped_rows ?? 0,
      roster_mapped_rows: diagnostics.roster_mapped_rows ?? 0,
      fallback_rows: diagnostics.fallback_rows ?? 0,
      low_confidence_rows: diagnostics.low_confidence_rows ?? 0,
      missing_player_history_rows: diagnostics.missing_player_history_rows ?? 0,
      starter_rows: diagnostics.starter_rows ?? 0,
      expected_starter_rows: diagnostics.expected_starter_rows ?? 0,
      avg_ev_pct:
        diagnostics.avg_ev_pct !== null && diagnostics.avg_ev_pct !== undefined
          ? diagnostics.avg_ev_pct
          : null,
      source_feed_gap_leagues: diagnostics.source_feed_gap_leagues || [],
      raw_monitor_summary: diagnostics.raw_monitor_summary || "",
    },
  };
}

function chooseFreshestSnapshot(candidates: Array<GoalscorerMonitorSnapshot | null>): GoalscorerMonitorSnapshot | null {
  let best: GoalscorerMonitorSnapshot | null = null;
  let bestFreshness = Number.NEGATIVE_INFINITY;
  for (const candidate of candidates) {
    const freshness = snapshotFreshness(candidate);
    if (freshness > bestFreshness) {
      bestFreshness = freshness;
      best = candidate;
    }
  }
  return best;
}

async function readLocalSnapshot(): Promise<GoalscorerMonitorSnapshot | null> {
  try {
    const text = await fs.readFile(path.join(process.cwd(), LOCAL_SNAPSHOT_FILE), "utf8");
    return JSON.parse(text) as GoalscorerMonitorSnapshot;
  } catch {
    return null;
  }
}

async function readGitRemoteSnapshot(): Promise<GoalscorerMonitorSnapshot | null> {
  if (process.env.NODE_ENV !== "development") return null;
  try {
    const { stdout } = await execFileAsync("git", ["show", `${GIT_REMOTE_REF}:${LOCAL_SNAPSHOT_FILE}`], {
      cwd: process.cwd(),
      maxBuffer: 64 * 1024 * 1024,
    });
    return JSON.parse(stdout) as GoalscorerMonitorSnapshot;
  } catch {
    return null;
  }
}

async function readSupabaseSnapshot(): Promise<GoalscorerMonitorSnapshot | null> {
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from(SNAPSHOT_TABLE)
      .select("payload")
      .eq("snapshot_key", SNAPSHOT_KEY)
      .maybeSingle();
    if (error || !data?.payload || typeof data.payload !== "object") {
      return null;
    }
    return data.payload as GoalscorerMonitorSnapshot;
  } catch {
    return null;
  }
}

async function readGithubSnapshot(): Promise<GoalscorerMonitorSnapshot | null> {
  try {
    const response = await fetch(`${GITHUB_RAW_BASE}/${LOCAL_SNAPSHOT_FILE}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as GoalscorerMonitorSnapshot;
  } catch {
    return null;
  }
}

export async function readGoalscorerMonitorSnapshot(): Promise<GoalscorerMonitorSnapshot | null> {
  if (cache && cache.expiresAt > Date.now()) {
    return cache.payload;
  }

  let payload: GoalscorerMonitorSnapshot | null = null;
  if (process.env.NODE_ENV === "development") {
    const [gitSnapshot, supabaseSnapshot, localSnapshot] = await Promise.all([
      readGitRemoteSnapshot(),
      readSupabaseSnapshot(),
      readLocalSnapshot(),
    ]);
    payload = chooseFreshestSnapshot([gitSnapshot, supabaseSnapshot, localSnapshot]);
  } else {
    const [supabaseSnapshot, githubSnapshot, localSnapshot] = await Promise.all([
      readSupabaseSnapshot(),
      readGithubSnapshot(),
      readLocalSnapshot(),
    ]);
    payload = chooseFreshestSnapshot([supabaseSnapshot, githubSnapshot, localSnapshot]);
  }

  payload = normalizeSnapshot(payload);

  cache = {
    expiresAt: Date.now() + CACHE_TTL_MS,
    payload,
  };
  return payload;
}
