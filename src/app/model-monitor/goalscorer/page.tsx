import Link from "next/link";
import { notFound } from "next/navigation";

import { readPenaltyReviewState } from "@/lib/goalscorer-penalty-review-state";
import { type GoalscorerMonitorSnapshot, readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";

import { PenaltyReviewActions, type PenaltyReviewStatus } from "./PenaltyReviewActions";
import {
  EmptyState,
  HeroCard,
  LeagueLabel,
  MatchLabel,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  PhaseLabel,
  SectionCard,
  StatCard,
  StatusPill,
  TeamLabel,
  actionTone,
  formatDateLabel,
  formatDateTimeLabel,
  formatOdds,
  formatPct,
  formatUnits,
  statusTone,
  toneClass,
} from "./shared";

export const dynamic = "force-dynamic";

type SnapshotPenaltyRow = GoalscorerMonitorSnapshot["penalty_watchlist"]["rows"][number] & {
  resolutionStatus?: PenaltyReviewStatus;
  resolutionUpdatedAt?: string;
};

type SnapshotRoleRow = NonNullable<GoalscorerMonitorSnapshot["preseason_role_review"]>["rows"][number] & {
  resolutionStatus?: PenaltyReviewStatus;
  resolutionUpdatedAt?: string;
};

function numericSum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((total, v) => total + (v ?? 0), 0);
}

function renderSourceDetail(snapshot: GoalscorerMonitorSnapshot) {
  const s = snapshot.source_status;
  const parts = [
    s.hot_live_updated_at ? `Hot live ${formatDateTimeLabel(s.hot_live_updated_at)}` : null,
    s.expected_refresh_updated_at ? `Expected ${formatDateTimeLabel(s.expected_refresh_updated_at)}` : null,
    s.settlement_updated_at ? `Settlement ${formatDateTimeLabel(s.settlement_updated_at)}` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" | ") : "Source timestamps unavailable";
}

function parseIso(value?: string | null) {
  if (!value) return null;
  const ts = Date.parse(value);
  return Number.isNaN(ts) ? null : ts;
}

function hostedHeartbeat(snapshot: GoalscorerMonitorSnapshot) {
  const s = snapshot.source_status;
  const snapshotTs = parseIso(snapshot.generated_at);
  const hotLiveTs = parseIso(s.hot_live_updated_at);
  const schedulerTs = parseIso(s.scheduler_heartbeat_at);
  const freshestTs = [hotLiveTs, schedulerTs].filter((v): v is number => v !== null).sort((a, b) => b - a)[0] ?? null;
  const ageMinutes =
    snapshotTs !== null && freshestTs !== null
      ? Math.max(0, Math.round((snapshotTs - freshestTs) / 60000))
      : null;

  const state = (s.live_status_state || "").trim().toLowerCase();
  const isHealthy = state === "idle" || state === "warning" || state === "skipped";
  const tone =
    state === "failed"
      ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
      : ageMinutes !== null && ageMinutes > 35
        ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
        : isHealthy
          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
          : "bg-slate-700/40 text-slate-300 border-slate-600/40";

  const label =
    state === "failed"
      ? "Hosted stale"
      : ageMinutes !== null && ageMinutes > 35
        ? "Hosted delayed"
        : "Hosted healthy";

  const detailParts = [
    s.hot_live_updated_at ? `Hot live ${formatDateTimeLabel(s.hot_live_updated_at)}` : null,
    s.scheduler_heartbeat_at ? `Heartbeat ${formatDateTimeLabel(s.scheduler_heartbeat_at)}` : null,
    ageMinutes !== null ? `${ageMinutes}m behind snapshot` : null,
    s.live_status_state ? `State ${s.live_status_state}` : null,
  ].filter(Boolean);

  return {
    label,
    tone,
    detail: detailParts.join(" | ") || "Hosted heartbeat unavailable",
    message: s.live_status_message || "",
  };
}

function splitFixtureMatch(match?: string | null): [string, string] {
  const [home = "", away = ""] = (match ?? "").split(" vs ");
  return [home, away];
}

// --- Tone helpers ------------------------------------------------------------

function reviewPriorityTone(priority?: string) {
  const n = (priority || "").toLowerCase();
  if (n === "high")   return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  if (n === "medium") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-slate-700/40 text-slate-400 border-slate-600/40";
}

function resolutionTone(status?: PenaltyReviewStatus) {
  if (status === "applied")  return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (status === "accepted") return "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
  if (status === "deferred") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (status === "ignored")  return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  return "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
}

/** Subtle row tint for the settlements table to surface won/lost at a glance. */
function settlementRowTint(outcome?: string | null) {
  const n = (outcome || "").toLowerCase();
  if (n.includes("won"))  return "bg-emerald-950/25";
  if (n.includes("lost")) return "bg-rose-950/25";
  return "";
}

function evidenceOutcomeLabel(row: SettlementRow) {
  if (row.settled) return row.bet_outcome || "settled";
  return "pending";
}

// --- Penalty review card -----------------------------------------------------

function PenaltyReviewCard({ row }: { row: SnapshotPenaltyRow }) {
  const minuteAside = row.minute
    ? `min ${row.minute}${row.event_result ? ` | ${row.event_result}` : row.event_type ? ` | ${row.event_type}` : ""}`
    : undefined;
  const primaryTakerPitchValue =
    row.primary_on_pitch_at_penalty?.trim() ||
    (row.primary_pre_match ? "Unknown" : "-");
  const secondaryTakerPitchValue =
    row.secondary_on_pitch_at_penalty?.trim() ||
    (row.secondary_pre_match ? "Unknown" : "-");
  const tertiaryTakerPitchValue =
    row.tertiary_on_pitch_at_penalty?.trim() ||
    (row.tertiary_pre_match ? "Unknown" : "-");
  const preMatchActiveTakerValue =
    row.active_taker_pre_match?.trim() ||
    (row.primary_pre_match ? "Unknown" : "-");
  const preMatchActiveTakerDetail =
    row.active_slot_pre_match ||
    (preMatchActiveTakerValue === "Unknown" ? "lineup unresolved" : undefined);
  const actualTakerPitchValue =
    row.actual_taker_match_status?.trim() ||
    row.actual_taker_on_pitch_at_penalty?.trim() ||
    (row.actual_taker ? "On pitch" : "-");
  const actualRole = row.actual_role_pre_match?.trim().toLowerCase() || "none";
  const takerRank = ({
    primary: "No.1 primary",
    secondary: "No.2 backup",
    tertiary: "No.3 backup",
    none: "Unranked taker",
  } as Record<string, string>)[actualRole] || "Unranked taker";
  const hasTransferContext =
    Boolean(row.inherited_from_pre_match?.trim()) || Boolean(row.transfer_level_pre_match?.trim());
  const editorialNote = row.editorial_note
    ? row.event_result && !row.editorial_note.toLowerCase().includes(row.event_result.toLowerCase())
      ? `Penalty ${row.event_result}. ${row.editorial_note}`
      : row.editorial_note
    : "";

  return (
    <article className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      {/* -- Header -- */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
            <LeagueLabel league={row.league} label={row.league || "League"} iconSize={14} />
            <span>|</span>
            <span>{row.review_source || "Penalty review"}</span>
          </div>
          <h3 className="mt-1 text-base font-semibold text-white">
            {row.actual_taker || "Unknown taker"}
          </h3>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-slate-400">
            <MatchLabel
              league={row.league}
              homeTeam={row.team || "?"}
              awayTeam={row.opponent || "?"}
              iconSize={18}
              textClassName="text-sm text-slate-400"
            />
            <span>|</span>
            <span>{formatDateLabel(row.date)}</span>
          </div>
        </div>
        <div className="flex w-full min-w-0 flex-wrap items-center gap-1.5 sm:w-auto sm:shrink-0 sm:justify-end">
          {row.review_priority ? (
            <StatusPill label={row.review_priority} tone={reviewPriorityTone(row.review_priority)} />
          ) : null}
          {row.hierarchy_status ? (
            <StatusPill
              label={`${row.hierarchy_status} hierarchy`}
              tone={
                row.hierarchy_status === "conditional" || row.hierarchy_status === "disputed"
                  ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                  : "bg-slate-700/40 text-slate-400 border-slate-600/40"
              }
            />
          ) : null}
          {row.event_result ? (
            <StatusPill
              label={row.event_result}
              tone={
                row.event_result.toLowerCase().includes("scor")
                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                  : row.event_result.toLowerCase().includes("miss") || row.event_result.toLowerCase().includes("save")
                    ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                    : "bg-slate-700/40 text-slate-400 border-slate-600/40"
              }
            />
          ) : null}
          <StatusPill
            label={takerRank}
            tone={actualRole === "none"
              ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
              : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"}
          />
          {row.review_type ? (
            <StatusPill
              label={row.review_type.replaceAll("_", " ")}
              tone="bg-cyan-500/10 text-cyan-300 border-cyan-500/20"
            />
          ) : null}
          <StatusPill
            label={row.resolutionStatus ? row.resolutionStatus.replaceAll("_", " ") : "active"}
            tone={resolutionTone(row.resolutionStatus)}
          />
        </div>
      </div>

      {/* -- Phase groups -- */}
      <div className="mt-4 space-y-3">
        {/* Pre-match */}
        <div className="space-y-2">
          <PhaseLabel label="Pre-match" />
          <div className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard compact label="Primary" value={row.primary_pre_match || "-"} />
            <StatCard compact label="Backup" value={row.secondary_pre_match || "-"} />
            <StatCard compact label="Third choice" value={row.tertiary_pre_match || "-"} />
            <StatCard
              compact
              label="Pre-match active taker"
              value={preMatchActiveTakerValue}
              detail={preMatchActiveTakerDetail}
            />
          </div>
        </div>

        {/* At penalty */}
        <div className="space-y-2">
          <PhaseLabel label="At penalty" aside={minuteAside} />
          <div className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard compact label={`No.1 | ${row.primary_pre_match || "Unfiled"}`} value={primaryTakerPitchValue} />
            <StatCard compact label={`No.2 | ${row.secondary_pre_match || "Unfiled"}`} value={secondaryTakerPitchValue} />
            <StatCard compact label={`No.3 | ${row.tertiary_pre_match || "Unfiled"}`} value={tertiaryTakerPitchValue} />
            <StatCard
              compact
              label={`Actual | ${row.actual_taker || "Unknown"}`}
              value={takerRank}
              detail={actualTakerPitchValue}
              tone="text-slate-100"
            />
          </div>
        </div>

        {/* Transfer */}
        {hasTransferContext ? (
          <div className="space-y-2">
            <PhaseLabel label="Transfer & assignment" />
            <div className="grid gap-1.5 sm:grid-cols-2">
              <StatCard compact label="Inherited duty from" value={row.inherited_from_pre_match || "-"} />
              <StatCard compact label="Transfer confidence" value={row.transfer_level_pre_match || "-"} />
            </div>
          </div>
        ) : null}
      </div>

      {/* -- Footer -- */}
      {editorialNote ? (
        <p className="mt-3 border-t border-slate-800/60 pt-3 text-xs text-slate-400">
          {editorialNote}
        </p>
      ) : null}
      {row.row_id ? (
        <PenaltyReviewActions rowId={row.row_id} status={row.resolutionStatus} />
      ) : null}
      {row.resolutionUpdatedAt ? (
        <p className="mt-2 text-[11px] text-slate-600">
          Updated {formatDateTimeLabel(row.resolutionUpdatedAt)}
        </p>
      ) : null}
    </article>
  );
}

function PreseasonRoleReviewCard({ row }: { row: SnapshotRoleRow }) {
  return (
    <article className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
            {row.season} source check
          </div>
          <div className="mt-1">
            <TeamLabel league="epl" team={row.team} iconSize={22} teamClassName="text-base font-semibold text-white" />
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatusPill label={row.review_priority} tone={reviewPriorityTone(row.review_priority)} />
          <StatusPill
            label={row.review_type.replaceAll("_", " ")}
            tone="bg-cyan-500/10 text-cyan-300 border-cyan-500/20"
          />
          <StatusPill
            label={row.resolutionStatus ? row.resolutionStatus.replaceAll("_", " ") : "active"}
            tone={resolutionTone(row.resolutionStatus)}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        <StatCard compact label="Current primary" value={row.current_primary || "Unknown"} />
        <StatCard compact label="Source first order" value={row.proposed_primary || "No ranked player"} />
        <StatCard
          compact
          label="Automatic change"
          value="Blocked"
          detail="Human evidence review required"
          tone="text-amber-300"
        />
      </div>

      {row.fpl_penalty_order.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {row.fpl_penalty_order.map((item) => (
            <span
              key={`${item.order}-${item.element_id}-${item.player}`}
              className="rounded-full border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-300"
            >
              {item.order}. {item.player}
            </span>
          ))}
        </div>
      ) : null}

      <p className="mt-3 border-t border-slate-800/60 pt-3 text-xs leading-5 text-slate-400">
        {row.reason} Verify squad status and direct match evidence before changing the public hierarchy.
      </p>
      <PenaltyReviewActions rowId={row.row_id} status={row.resolutionStatus} mode="source" />
      {row.resolutionUpdatedAt ? (
        <p className="mt-2 text-[11px] text-slate-600">
          Updated {formatDateTimeLabel(row.resolutionUpdatedAt)}
        </p>
      ) : null}
    </article>
  );
}

// --- Live Bets table ---------------------------------------------------------

function LiveBetsTable({ rows }: { rows: GoalscorerMonitorSnapshot["live_bets"] }) {
  if (rows.length === 0) {
    return <EmptyState message="No current goalscorer bets are live in the snapshot." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-800/80">
            {(["Player", "Fixture", "Lineup", "Book"] as const).map((h) => (
              <th key={h} className="pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                {h}
              </th>
            ))}
            {(["Odds", "Fair", "Edge"] as const).map((h) => (
              <th key={h} className="pb-2.5 pr-4 text-right text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                {h}
              </th>
            ))}
            <th className="pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">Stake</th>
            <th className="pb-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">Track</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-slate-900/50 align-middle transition-colors hover:bg-white/[0.02]"
            >
              <td className="py-2.5 pr-4">
                <div className="font-medium text-white">{row.player}</div>
                <div className="mt-1">
                  <TeamLabel
                    league={row.league_key}
                    team={row.team}
                    detail={row.league_label}
                    iconSize={18}
                    teamClassName="text-[11px] text-slate-300"
                    detailClassName="text-[11px] text-slate-500"
                  />
                </div>
              </td>
              <td className="py-2.5 pr-4">
                <MatchLabel
                  league={row.league_key}
                  homeTeam={row.team}
                  awayTeam={row.opponent}
                  iconSize={18}
                  textClassName="text-slate-300"
                />
                <div className="text-[11px] tabular-nums text-slate-500">
                  {formatDateTimeLabel(row.kickoff || row.match_date)}
                </div>
              </td>
              <td className="py-2.5 pr-4">
                <div className="text-slate-300">{row.lineup_short || "-"}</div>
                <div className="text-[11px] text-slate-500">{row.lineup_label}</div>
              </td>
              <td className="py-2.5 pr-4 text-slate-400">{row.bookmaker || "-"}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-slate-200">{formatOdds(row.odds)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-slate-500">{formatOdds(row.fair, 2)}</td>
              <td className={`py-2.5 pr-4 text-right tabular-nums font-semibold ${toneClass(row.edge_pct)}`}>
                {formatPct(row.edge_pct)}
              </td>
              <td className="py-2.5 pr-4 text-slate-400">{row.stake_label || "-"}</td>
              <td className="py-2.5">
                <StatusPill
                  label={row.status === "PUBLIC" ? "public" : row.action_label || "shadow"}
                  tone={actionTone(row.action)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Recent Shadow Settlements ------------------------------------------------
//
// Desktop (lg+): dense table - kickoff lives as sub-text under the fixture
//   cell so we avoid a separate timestamp column. 8 columns total, all fit
//   within the lg viewport without horizontal scrolling.
//
// Mobile/tablet (< lg): stacked cards - each row becomes a small block with
//   outcome pill, fixture, financial metrics, and both timestamps on one line.

type SettlementRow = GoalscorerMonitorSnapshot["shadow_summary"]["recent_rows"][number];

function SettlementCard({ row }: { row: SettlementRow }) {
  return (
    <div
      className={`rounded-xl border border-slate-800/60 p-3 ${settlementRowTint(row.bet_outcome)}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-medium text-white">{row.player}</div>
          <div className="mt-1">
            <TeamLabel
              league={row.league_key}
              team={row.team}
              detail={row.league_key}
              iconSize={18}
              teamClassName="text-[11px] text-slate-300"
              detailClassName="text-[11px] text-slate-500"
            />
          </div>
        </div>
        <StatusPill label={evidenceOutcomeLabel(row)} tone={statusTone(evidenceOutcomeLabel(row))} />
      </div>
      <div className="mt-1">
        <MatchLabel
          league={row.league_key}
          homeTeam={splitFixtureMatch(row.match)[0]}
          awayTeam={splitFixtureMatch(row.match)[1]}
          iconSize={16}
          textClassName="truncate text-xs text-slate-400"
        />
      </div>
      {row.quarantine_reason ? (
        <div className="mt-2 text-[11px] text-amber-300/80">
          {row.quarantine_reason.replaceAll("_", " ")}
        </div>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs tabular-nums">
        <span className="text-slate-500">
          Odds <span className="text-slate-300">{formatOdds(row.best_bookmaker_odds)}</span>
        </span>
        <span className="text-slate-500">
          Fair <span className="text-slate-300">{formatOdds(row.model_fair_odds)}</span>
        </span>
        <span className="text-slate-500">
          Edge{" "}
          <span className={`font-semibold ${toneClass(row.ev_pct)}`}>{formatPct(row.ev_pct)}</span>
        </span>
        <span className="text-slate-500">
          P&amp;L{" "}
          <span className={`font-semibold ${toneClass(row.pnl_units)}`}>{formatUnits(row.pnl_units)}</span>
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] tabular-nums text-slate-600">
        <span>KO {formatDateTimeLabel(row.kickoff || row.date)}</span>
        <span>Settled {formatDateTimeLabel(row.settled_at)}</span>
      </div>
    </div>
  );
}

function RecentSettlementsTable({
  rows,
  emptyMessage = "No settled shadow rows are available in the snapshot yet.",
}: {
  rows: GoalscorerMonitorSnapshot["shadow_summary"]["recent_rows"];
  emptyMessage?: string;
}) {
  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <>
      {/* -- Mobile / tablet: card list (hidden at lg) -- */}
      <div className="space-y-2 lg:hidden">
        {rows.map((row) => (
          <SettlementCard key={row.key} row={row} />
        ))}
      </div>

      {/* -- Desktop: dense table (shown at lg+) -- */}
      <div className="hidden lg:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-800/80">
              <th className="w-[148px] pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Player
              </th>
              <th className="pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Fixture
              </th>
              <th className="w-[86px] pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Outcome
              </th>
              <th className="w-[52px] pb-2.5 pr-4 text-right text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Odds
              </th>
              <th className="w-[52px] pb-2.5 pr-4 text-right text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Fair
              </th>
              <th className="w-[62px] pb-2.5 pr-4 text-right text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Edge
              </th>
              <th className="w-[62px] pb-2.5 pr-4 text-right text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                P&amp;L
              </th>
              <th className="w-[108px] pb-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                Settled
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.key}
                className={`border-b border-slate-900/50 align-middle transition-colors hover:bg-white/[0.025] ${settlementRowTint(row.bet_outcome)}`}
              >
                <td className="py-2.5 pr-4">
                  <div className="font-medium leading-tight text-white">{row.player}</div>
                  {row.quarantine_reason ? (
                    <div className="mt-0.5 text-[10px] text-amber-300/75">
                      {row.quarantine_reason.replaceAll("_", " ")}
                    </div>
                  ) : null}
                  <div className="mt-1">
                    <TeamLabel
                      league={row.league_key}
                      team={row.team}
                      iconSize={18}
                      teamClassName="text-[11px] leading-tight text-slate-300"
                    />
                  </div>
                </td>
                <td className="py-2.5 pr-4">
                  <MatchLabel
                    league={row.league_key}
                    homeTeam={splitFixtureMatch(row.match)[0]}
                    awayTeam={splitFixtureMatch(row.match)[1]}
                    iconSize={16}
                    textClassName="text-slate-300"
                  />
                  <div className="text-[11px] tabular-nums text-slate-500">
                    KO {formatDateTimeLabel(row.kickoff || row.date)}
                  </div>
                </td>
                <td className="py-2.5 pr-4">
                  <StatusPill label={evidenceOutcomeLabel(row)} tone={statusTone(evidenceOutcomeLabel(row))} />
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-slate-300">
                  {formatOdds(row.best_bookmaker_odds)}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-slate-500">
                  {formatOdds(row.model_fair_odds)}
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums font-semibold ${toneClass(row.ev_pct)}`}>
                  {formatPct(row.ev_pct)}
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums font-semibold ${toneClass(row.pnl_units)}`}>
                  {formatUnits(row.pnl_units)}
                </td>
                <td className="py-2.5">
                  <span className="whitespace-nowrap text-xs tabular-nums text-slate-400">
                    {formatDateTimeLabel(row.settled_at)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// --- Fixture Diagnostics table ------------------------------------------------

function FixtureDiagnosticsTable({
  rows,
}: {
  rows: GoalscorerMonitorSnapshot["fixture_health"]["flagged_rows"];
}) {
  if (rows.length === 0) {
    return (
      <EmptyState message="No degraded or quarantined fixtures are flagged in the current snapshot." />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[740px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-800/80">
            {["Fixture", "League", "Lineup input", "Trust", "Flags", "Summary"].map((h) => (
              <th
                key={h}
                className="pb-2.5 pr-4 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600 last:pr-0"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.key}
              className="border-b border-slate-900/50 align-top transition-colors hover:bg-white/[0.02]"
            >
              <td className="py-2.5 pr-4">
                <MatchLabel
                  league={row.league_key}
                  homeTeam={row.home_team}
                  awayTeam={row.away_team}
                  iconSize={18}
                  textClassName="font-medium text-slate-200"
                />
                <div className="text-[11px] text-slate-500">
                  {formatDateLabel(row.match_date)} | {row.bookmaker || "-"}
                </div>
              </td>
              <td className="py-2.5 pr-4 text-slate-400">
                <LeagueLabel league={row.league_key} label={row.league_label} iconSize={14} />
              </td>
              <td className="py-2.5 pr-4 text-slate-400">{row.lineup_input || "-"}</td>
              <td className="py-2.5 pr-4">
                <StatusPill label={row.trust_tier || "unknown"} tone={statusTone(row.trust_tier)} />
              </td>
              <td className="py-2.5 pr-4 text-xs text-slate-500">
                {row.corruption_flags?.length ? row.corruption_flags.join(", ") : "-"}
              </td>
              <td className="py-2.5 text-xs text-slate-400">{row.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Page --------------------------------------------------------------------

export default async function GoalscorerMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const [snapshot, penaltyState] = await Promise.all([
    readGoalscorerMonitorSnapshot(),
    readPenaltyReviewState(),
  ]);

  if (!snapshot) {
    return (
      <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <MonitorNav current="goalscorer" />
          <HeroCard title="Goalscorer Monitor" eyebrow="Snapshot-first monitor">
            <span className="text-slate-400">
              The goalscorer monitor snapshot is not available yet. Once the hosted goalscorer
              workflows publish{" "}
              <code className="rounded bg-slate-950/60 px-1.5 py-0.5 text-[11px]">
                goalscorer-monitor-snapshot.json
              </code>{" "}
              the page will render from that single payload.
            </span>
          </HeroCard>
        </div>
      </div>
    );
  }

  const publicNow = numericSum(snapshot.league_cards.map((c) => c.public_now));
  const shadowNow = numericSum(snapshot.league_cards.map((c) => c.shadow_now));
  const heartbeat = hostedHeartbeat(snapshot);
  const research = snapshot.research_status;
  const extremeGap = snapshot.extreme_gap_quarantine;
  const rawCalibrationEce = research?.calibration.raw_ece ?? null;
  const betaBrierDelta =
    research?.calibration.brier !== null &&
    research?.calibration.brier !== undefined &&
    research.calibration.raw_brier !== null &&
    research.calibration.raw_brier !== undefined
      ? research.calibration.brier - research.calibration.raw_brier
      : null;

  const activePenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows
    .filter((row) => !penaltyState[row.row_id])
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  const acceptedPenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows
    .filter((row) => penaltyState[row.row_id]?.status === "accepted")
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  const deferredPenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows
    .filter((row) => penaltyState[row.row_id]?.status === "deferred")
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  const resolvedPenaltyRows: SnapshotPenaltyRow[] = snapshot.penalty_watchlist.rows
    .filter((row) => {
      const status = penaltyState[row.row_id]?.status;
      return status === "ignored" || status === "applied";
    })
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  const sourceRoleRows = snapshot.preseason_role_review?.rows || [];
  const activeSourceRoleRows: SnapshotRoleRow[] = sourceRoleRows
    .filter((row) => !penaltyState[row.row_id])
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));
  const resolvedSourceRoleRows: SnapshotRoleRow[] = sourceRoleRows
    .filter((row) => Boolean(penaltyState[row.row_id]))
    .map((row) => ({
      ...row,
      resolutionStatus: penaltyState[row.row_id]?.status,
      resolutionUpdatedAt: penaltyState[row.row_id]?.updated_at,
    }));

  return (
    <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">

        <MonitorNav current="goalscorer" />

        {/* -- Hero ----------------------------------------------------------- */}
        <HeroCard title="Goalscorer Monitor" eyebrow="Snapshot-first architecture">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-slate-300">Generated {formatDateTimeLabel(snapshot.generated_at)}</span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-500">{renderSourceDetail(snapshot)}</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <StatusPill label={heartbeat.label} tone={heartbeat.tone} />
            <span className="text-xs text-slate-500">{heartbeat.detail}</span>
          </div>
          {heartbeat.message ? (
            <div className="mt-2 text-xs text-slate-400">{heartbeat.message}</div>
          ) : null}
        </HeroCard>

        {/* -- KPI strip ------------------------------------------------------ */}
        <section className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Live bets"       value={String(snapshot.live_bets.length)} />
          <StatCard label="Public now"      value={String(publicNow)}      detail="Rows surfaced to public" />
          <StatCard label="Shadow now"      value={String(shadowNow)}      detail="Shadow rows still open" />
          <StatCard
            label="Evidence reviews"
            value={String(activePenaltyRows.length + activeSourceRoleRows.length)}
            detail={`${activeSourceRoleRows.length} source | ${activePenaltyRows.length} match-event`}
          />
          <StatCard
            label="Flagged fixtures"
            value={String(snapshot.fixture_health.flagged_rows.length)}
            detail={`${snapshot.fixture_health.rows.length} in snapshot`}
          />
          <StatCard
            label="Avg EV"
            value={formatPct(snapshot.diagnostics.avg_ev_pct)}
            tone={toneClass(snapshot.diagnostics.avg_ev_pct)}
          />
        </section>

        {/* -- Research model gate ------------------------------------------ */}
        {research ? (
          <SectionCard
            title="Goalscorer v2 Research Gate"
            subtitle="Expected-minutes and absolute-share repair. Internal evidence only; public Fair Odds Lab remains on the incumbent model."
            collapsible
            defaultOpen
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill
                label={`Parity ${research.parity.decision}`}
                tone={research.parity.decision === "PASS" ? statusTone("healthy") : statusTone("failed")}
              />
              <StatusPill label="Public unchanged" tone={statusTone("warning")} />
              <span className="text-xs text-slate-500">
                {research.model_variant.replaceAll("_", " ")}
                {research.updated_at ? ` | refreshed ${formatDateTimeLabel(research.updated_at)}` : ""}
              </span>
            </div>

            <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                compact
                label="Live/backtest parity"
                value={research.parity.max_abs_delta === null ? "-" : `${(research.parity.max_abs_delta * 100).toFixed(3)}pp`}
                detail={`${research.parity.golden_rows} golden rows | gate ${research.parity.gate === null ? "-" : `${(research.parity.gate * 100).toFixed(2)}pp`}`}
                tone={research.parity.decision === "PASS" ? "text-emerald-300" : "text-rose-300"}
              />
              <StatCard
                compact
                label="Beta candidate ECE"
                value={research.calibration.ece === null ? "-" : `${(research.calibration.ece * 100).toFixed(2)}%`}
                detail={`Raw ${rawCalibrationEce === null ? "-" : `${(rawCalibrationEce * 100).toFixed(2)}%`} | ${research.calibration.fold_wins}/${research.calibration.evaluated_folds} fold wins`}
                tone={research.calibration.ece !== null && rawCalibrationEce !== null && research.calibration.ece < rawCalibrationEce ? "text-emerald-300" : "text-amber-300"}
              />
              <StatCard
                compact
                label="Segment integrity"
                value={research.segments.minutes_gate}
                detail={`${research.segments.rows.toLocaleString()} rows | Sub rows ${research.segments.position_sub_rows}`}
                tone={research.segments.minutes_gate === "PASS" ? "text-emerald-300" : "text-amber-300"}
              />
              <StatCard
                compact
                label="Real-price CLV coverage"
                value={`${research.clv.matched}/${research.clv.signals}`}
                detail={`${research.clv.coverage_pct.toFixed(1)}% matched | ${research.clv.true_closes} true closes`}
                tone={research.clv.matched > 0 ? "text-emerald-300" : "text-amber-300"}
              />
            </div>

            <p className="mt-3 text-xs leading-5 text-slate-500">
              Held-out beta calibration has {betaBrierDelta === null ? "no comparable Brier result yet" : `changed pooled Brier by ${betaBrierDelta >= 0 ? "+" : ""}${betaBrierDelta.toFixed(5)} versus raw`}. Promotion remains blocked until the fifth walk-forward fold exists and real captured ATGS prices prove non-negative ROI/CLV. Probability improvements alone do not create a betting edge.
            </p>
          </SectionCard>
        ) : null}

        <SectionCard
          title={`Extreme-gap Quarantine | ${extremeGap.registered} registered`}
          subtitle="Rows rejected by the public 10pp / 1.5x probability guard. Zero recommended stake; tracked at a fixed 1u evaluation stake."
          collapsible
          defaultOpen
        >
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label="Research only" tone={statusTone("warning")} />
            <StatusPill label="Public routing unchanged" tone={statusTone("healthy")} />
            <span className="text-xs text-slate-500">
              The cohort tests whether large disagreements contain edge without exposing public users to unproven prices.
            </span>
          </div>

          <div className="mt-4 grid gap-2.5 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard compact label="Registered" value={String(extremeGap.registered)} detail={`${extremeGap.pending} pending`} />
            <StatCard compact label="Settled" value={String(extremeGap.settled)} detail={`${extremeGap.wins}W / ${extremeGap.losses}L / ${extremeGap.voids}V`} />
            <StatCard compact label="Evaluation P&L" value={formatUnits(extremeGap.pnl_units)} tone={toneClass(extremeGap.pnl_units)} detail={`${extremeGap.staked_units.toFixed(2)}u evaluated`} />
            <StatCard compact label="Evaluation ROI" value={formatPct(extremeGap.roi)} tone={toneClass(extremeGap.roi)} detail="Not a public track record" />
            <StatCard compact label="Public stake" value="0.00u" detail="Fail-closed guard" />
          </div>

          {extremeGap.by_league.some((row) => row.registered > 0) ? (
            <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
              {extremeGap.by_league.filter((row) => row.registered > 0).map((row) => (
                <div key={row.key} className="rounded-lg border border-slate-800/60 bg-slate-950/40 px-3 py-2">
                  <div className="text-xs font-medium text-slate-300">{row.label}</div>
                  <div className="mt-1 text-[11px] tabular-nums text-slate-500">
                    {row.settled}/{row.registered} settled | <span className={toneClass(row.pnl_units)}>{formatUnits(row.pnl_units)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-4">
            <RecentSettlementsTable
              rows={extremeGap.recent_rows}
              emptyMessage="No otherwise-eligible extreme-gap rows have been registered yet. The guard remains active and the cohort will populate automatically."
            />
          </div>
        </SectionCard>

        {/* -- League Scoreboard ----------------------------------------------- */}
        <SectionCard
          title="League Scoreboard"
          subtitle={`${snapshot.league_cards.length} leagues | page-ready KPIs from snapshot builder`}
          collapsible
          defaultOpen
        >
          <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
            {snapshot.league_cards.map((card) => (
              <article
                key={card.key}
                className="rounded-xl border border-slate-800/60 bg-slate-950/50 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{card.label}</h3>
                    <p className="mt-0.5 text-[11px] text-slate-600">
                      Updated {formatDateTimeLabel(card.updated_at)}
                    </p>
                  </div>
                  <StatusPill label={card.status_label} tone={statusTone(card.status_key)} />
                </div>
                {card.status_detail ? (
                  <p className="mt-2 text-xs text-slate-500">{card.status_detail}</p>
                ) : null}
                <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
                  <StatCard compact label="Live rows"       value={String(card.live_rows)} />
                  <StatCard compact label="Public / shadow" value={`${card.public_now} / ${card.shadow_now}`} />
                  <StatCard
                    compact
                    label="Fixture health"
                    value={`${card.clean_fixtures} clean`}
                    detail={`${card.degraded_fixtures} deg | ${card.quarantined_fixtures} quar`}
                  />
                  <StatCard
                    compact
                    label="Shadow open"
                    value={String(card.shadow_record.open)}
                    detail={`${card.shadow_record.settled} settled`}
                  />
                  <StatCard
                    compact
                    label="Shadow ROI"
                    value={formatPct(card.shadow_record.roi)}
                    tone={toneClass(card.shadow_record.roi)}
                    detail={formatUnits(card.shadow_record.pnl_units, 3)}
                  />
                  <StatCard
                    compact
                    label="Public ROI"
                    value={formatPct(card.public_record.roi)}
                    tone={toneClass(card.public_record.roi)}
                    detail={formatUnits(card.public_record.pnl_units, 3)}
                  />
                </div>
              </article>
            ))}
          </div>
        </SectionCard>

        {/* -- Live Bets ------------------------------------------------------- */}
        <SectionCard
          title={`Live Bets${snapshot.live_bets.length ? ` | ${snapshot.live_bets.length}` : ""}`}
          subtitle="Public and shadow rows backed by the current snapshot."
          collapsible
          defaultOpen
        >
          <LiveBetsTable rows={snapshot.live_bets} />
        </SectionCard>

        <div id="preseason-role-review" className="scroll-mt-24">
          <SectionCard
            title={`Preseason Role Review${activeSourceRoleRows.length ? ` | ${activeSourceRoleRows.length} active` : ""}`}
            subtitle="Official FPL role fields are evidence tickets only. They never rewrite the public hierarchy automatically."
            collapsible
            defaultOpen
          >
            <div className="space-y-3">
              {activeSourceRoleRows.length === 0 ? (
                <EmptyState message="No active preseason role conflicts in the current snapshot." />
              ) : (
                activeSourceRoleRows.map((row) => <PreseasonRoleReviewCard key={row.row_id} row={row} />)
              )}
            </div>
            {resolvedSourceRoleRows.length ? (
              <details className="group mt-4 rounded-xl border border-slate-800/50 bg-slate-950/30">
                <summary className="cursor-pointer select-none px-4 py-3 text-xs font-medium text-slate-500">
                  Resolved source rows ({resolvedSourceRoleRows.length})
                </summary>
                <div className="space-y-3 border-t border-slate-800/50 px-4 pb-4 pt-3">
                  {resolvedSourceRoleRows.map((row) => <PreseasonRoleReviewCard key={row.row_id} row={row} />)}
                </div>
              </details>
            ) : null}
          </SectionCard>
        </div>

        {/* -- Penalty Watchlist ----------------------------------------------- */}
        <div id="penalty-watchlist" className="scroll-mt-24">
          <SectionCard
            title={`Penalty Watchlist${activePenaltyRows.length ? ` | ${activePenaltyRows.length} active` : ""}`}
            subtitle="Conditional and disputed clubs are prioritised. Ticket actions never edit the public hierarchy automatically."
            collapsible
            defaultOpen
          >
            <div className="space-y-3">
              {activePenaltyRows.length === 0 ? (
                <EmptyState message="No active penalty review rows in the current snapshot." />
              ) : (
                activePenaltyRows.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
              )}
            </div>

            <div className="mt-5 border-t border-slate-800/60 pt-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-cyan-200">
                    Accepted, awaiting hierarchy edit ({acceptedPenaltyRows.length})
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    “Mark applied” is blocked until the observed taker appears in the hierarchy and both audit dates cover the event.
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {acceptedPenaltyRows.length === 0 ? (
                  <EmptyState message="No accepted evidence is waiting for a hierarchy edit." />
                ) : (
                  acceptedPenaltyRows.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
                )}
              </div>
            </div>

            {/* Deferred rows - collapsed */}
            <details className="group mt-4 rounded-xl border border-slate-800/50 bg-slate-950/30">
              <summary className="flex cursor-pointer select-none list-none items-center justify-between gap-3 px-4 py-3 marker:hidden hover:bg-white/[0.02]">
                <span className="text-xs font-medium text-slate-500">
                  Deferred for more evidence ({deferredPenaltyRows.length})
                </span>
                <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-700 transition-transform duration-200 group-open:rotate-180">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden><polyline points="6 9 12 15 18 9" /></svg>
                </span>
              </summary>
              <div className="space-y-3 border-t border-slate-800/50 px-4 pb-4 pt-3">
                {deferredPenaltyRows.length === 0 ? (
                  <EmptyState message="No penalty tickets are currently deferred." />
                ) : (
                  deferredPenaltyRows.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
                )}
              </div>
            </details>

            {/* Resolved rows - collapsed */}
            <details className="group mt-4 rounded-xl border border-slate-800/50 bg-slate-950/30">
              <summary className="flex cursor-pointer select-none list-none items-center justify-between gap-3 px-4 py-3 marker:hidden hover:bg-white/[0.02]">
                <span className="text-xs font-medium text-slate-500">
                  Applied or ignored ({resolvedPenaltyRows.length})
                </span>
                <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-700 transition-transform duration-200 group-open:rotate-180">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden><polyline points="6 9 12 15 18 9" /></svg>
                </span>
              </summary>
              <div className="space-y-3 border-t border-slate-800/50 px-4 pb-4 pt-3">
                {resolvedPenaltyRows.length === 0 ? (
                  <EmptyState message="No penalty tickets have been applied or ignored." />
                ) : (
                  resolvedPenaltyRows.map((row) => <PenaltyReviewCard key={row.row_id} row={row} />)
                )}
              </div>
            </details>
          </SectionCard>
        </div>

        {/* -- Recent Shadow Settlements ---------------------------------------- */}
        <SectionCard
          title={`Recent Shadow Settlements${snapshot.shadow_summary.recent_rows.length ? ` | ${snapshot.shadow_summary.recent_rows.length}` : ""}`}
          subtitle={`${snapshot.shadow_summary.settled_today.length} today | ${snapshot.shadow_summary.settled_yesterday.length} yesterday`}
          collapsible
          defaultOpen
        >
          <RecentSettlementsTable rows={snapshot.shadow_summary.recent_rows.slice(0, 50)} />
        </SectionCard>

        {/* -- Fixture Diagnostics (collapsed) --------------------------------- */}
        <SectionCard
          title={`Fixture Diagnostics | ${snapshot.fixture_health.flagged_rows.length} flagged`}
          subtitle={`${snapshot.fixture_health.clean_count} clean | ${snapshot.fixture_health.degraded_count} degraded | ${snapshot.fixture_health.quarantined_count} quarantined`}
          collapsible
          defaultOpen={false}
        >
          <FixtureDiagnosticsTable rows={snapshot.fixture_health.flagged_rows} />
        </SectionCard>

        {/* -- Related Tools (collapsed) ---------------------------------------- */}
        <SectionCard
          title="Related Tools"
          subtitle="Lineups view and raw penalty watchlist API."
          collapsible
          defaultOpen={false}
        >
          <div className="flex flex-wrap gap-3">
            <Link
              href="/model-monitor/goalscorer/lineups"
              className="inline-flex items-center gap-1.5 rounded-full border border-cyan-500/20 bg-cyan-500/8 px-3 py-1.5 text-sm text-cyan-300 transition-colors hover:border-cyan-400/30 hover:bg-cyan-500/12"
            >
              Open lineups view
            </Link>
            <Link
              href="/api/model-monitor/goalscorer/penalty-watchlist"
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-900/60 px-3 py-1.5 text-sm text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-200"
            >
              Penalty watchlist API
            </Link>
          </div>
        </SectionCard>

      </div>
    </div>
  );
}
