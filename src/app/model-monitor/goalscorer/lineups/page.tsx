import { notFound } from "next/navigation";

import { type GoalscorerFixtureLineup, readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";

import {
  EmptyState,
  HeroCard,
  LeagueLabel,
  MatchLabel,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  SectionCard,
  StatCard,
  StatusPill,
  TeamLabel,
  formatDateTimeLabel,
  formatOdds,
  formatPct,
  statusTone,
  toneClass,
} from "../../shared";

export const dynamic = "force-dynamic";

function kickoffSortValue(value?: string | null) {
  if (!value) return Number.MAX_SAFE_INTEGER;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00Z`).getTime();
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : Number.MAX_SAFE_INTEGER;
}

function groupFixturesByLeague(rows: GoalscorerFixtureLineup[]) {
  const grouped = new Map<string, GoalscorerFixtureLineup[]>();
  for (const row of [...rows].sort((a, b) => kickoffSortValue(a.kickoff) - kickoffSortValue(b.kickoff))) {
    const bucket = grouped.get(row.league_label) ?? [];
    bucket.push(row);
    grouped.set(row.league_label, bucket);
  }
  return [...grouped.entries()];
}

// --- Player row -------------------------------------------------------------

function PlayerRow({
  player,
}: {
  player: GoalscorerFixtureLineup["home"]["attackers"][number];
}) {
  return (
    <div className="rounded-xl border border-slate-800/60 bg-slate-950/40 px-3 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-white">{player.name}</div>
          <div className="text-[11px] text-slate-500">
            {player.position}
            {player.expected_minutes ? ` | ${Math.round(player.expected_minutes)} min` : ""}
          </div>
        </div>
        <StatusPill
          label={player.action_label || player.action || "monitor"}
          tone={statusTone(player.action_label || player.action)}
        />
      </div>
      <div className="mt-2.5 grid gap-1.5 sm:grid-cols-3">
        <StatCard compact label="Odds" value={formatOdds(player.odds)} />
        <StatCard compact label="Fair" value={formatOdds(player.fair)} />
        <StatCard compact label="Edge" value={formatPct(player.ev_pct)} tone={toneClass(player.ev_pct)} />
      </div>
      {player.penalty_meta ? (
        <p className="mt-2 rounded-lg border border-amber-500/15 bg-amber-500/6 px-2.5 py-1.5 text-[11px] text-amber-300">
          {player.penalty_meta.compact}
        </p>
      ) : null}
      {player.note ? <p className="mt-1.5 text-[11px] text-slate-500">{player.note}</p> : null}
    </div>
  );
}

// --- Player section ----------------------------------------------------------

function PlayerSection({
  label,
  rows,
}: {
  label: string;
  rows: GoalscorerFixtureLineup["home"]["attackers"];
}) {
  if (rows.length === 0) return null;
  return (
    <div className="space-y-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">{label}</div>
      <div className="space-y-1.5">
        {rows.map((player) => (
          <PlayerRow key={player.key} player={player} />
        ))}
      </div>
    </div>
  );
}

// --- Team column --------------------------------------------------------------

function TeamColumn({
  leagueKey,
  side,
}: {
  leagueKey: string;
  side: GoalscorerFixtureLineup["home"];
}) {
  return (
    <div className="rounded-xl border border-slate-800/60 bg-slate-950/30 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <TeamLabel
            league={leagueKey}
            team={side.team}
            iconSize={22}
            teamClassName="text-sm font-semibold text-white"
            detail={side.lineup_status || "No lineup status"}
            detailClassName="mt-0.5 text-xs text-slate-500"
          />
        </div>
        <div className="text-right text-[11px] text-slate-600">
          <div>{side.total_players} projected</div>
          <div>{side.matched_players} priced</div>
        </div>
      </div>

      <div className="mt-3 space-y-2.5">
        {side.keeper ? (
          <div className="space-y-1.5">
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">Keeper</div>
            <PlayerRow player={side.keeper} />
          </div>
        ) : null}
        <PlayerSection label="Attack" rows={side.attackers} />
        <PlayerSection label="Wide / attacking mid" rows={side.wide_players} />
        <PlayerSection label="Midfield" rows={side.midfielders} />
        <PlayerSection label="Centre-backs" rows={side.centre_backs} />
        <PlayerSection label="Unplaced" rows={side.unplaced} />
      </div>
    </div>
  );
}

// --- Fixture card -------------------------------------------------------------

function FixtureCard({ fixture }: { fixture: GoalscorerFixtureLineup }) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(15,20,33,0.97),rgba(10,13,22,0.97))] p-5 shadow-[0_8px_32px_rgba(0,0,0,0.28)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <LeagueLabel
            league={fixture.league_key}
            label={fixture.competition}
            className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600"
            iconSize={14}
          />
          <div className="mt-1">
            <MatchLabel
              league={fixture.league_key}
              homeTeam={fixture.home_team}
              awayTeam={fixture.away_team}
              iconSize={20}
              textClassName="text-base font-semibold text-white"
            />
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            {formatDateTimeLabel(fixture.kickoff || fixture.match_date)} | {fixture.bookmaker || "Unknown book"}
          </p>
        </div>
        <StatusPill
          label={fixture.health?.status_label ?? (fixture.has_any_lineup ? "lineups loaded" : "no lineup data")}
          tone={statusTone(
            fixture.health?.trust_tier ??
              fixture.health?.status_label ??
              (fixture.has_any_lineup ? "confirmed" : "no feed"),
          )}
        />
      </div>

      <div className="mt-3 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard compact label="Priced rows" value={String(fixture.matched_player_prices)} />
        <StatCard compact label="Home matched" value={String(fixture.home.matched_players)} />
        <StatCard compact label="Away matched" value={String(fixture.away.matched_players)} />
        <StatCard compact label="Health" value={fixture.health?.trust_tier || "-"} detail={fixture.health?.summary ?? undefined} />
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <TeamColumn leagueKey={fixture.league_key} side={fixture.home} />
        <TeamColumn leagueKey={fixture.league_key} side={fixture.away} />
      </div>
    </article>
  );
}

// --- Page --------------------------------------------------------------------

export default async function GoalscorerLineupsPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const snapshot = await readGoalscorerMonitorSnapshot();

  if (!snapshot) {
    return (
      <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <MonitorNav current="lineups" />
          <HeroCard title="Goalscorer Lineups" eyebrow="Snapshot-first lineups">
            <span className="text-slate-400">
              The lineups snapshot is not available yet. Once the hosted monitor snapshot is published,
              this page renders from the same payload as the main goalscorer monitor.
            </span>
          </HeroCard>
        </div>
      </div>
    );
  }

  const fixtures = snapshot.fixture_lineups;
  const grouped = groupFixturesByLeague(fixtures);
  const fixturesWithLineups = fixtures.filter((f) => f.has_any_lineup).length;
  const matchedRows = fixtures.reduce((t, f) => t + f.matched_player_prices, 0);

  return (
    <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">

        <MonitorNav current="lineups" />

        {/* -- Hero -- */}
        <HeroCard title="Goalscorer Lineups" eyebrow="Snapshot-backed fixture view">
          <span className="text-slate-300">Fixture cards rendered from the compact goalscorer monitor snapshot.</span>
          <span className="mx-2 text-slate-700">|</span>
          <span className="text-slate-500">Generated {formatDateTimeLabel(snapshot.generated_at)}</span>
        </HeroCard>

        {/* -- KPI strip -- */}
        <section className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
          <StatCard label="Fixtures"        value={String(fixtures.length)} />
          <StatCard label="With lineups"    value={String(fixturesWithLineups)} />
          <StatCard label="Matched prices"  value={String(matchedRows)} />
          <StatCard label="Flagged"         value={String(snapshot.fixture_health.flagged_rows.length)} detail="fixture health flags" />
          <StatCard label="Penalty reviews" value={String(snapshot.penalty_watchlist.row_count)} />
        </section>

        {/* -- Fixture groups -- */}
        {grouped.length === 0 ? (
          <SectionCard title="Fixtures" subtitle="No fixture lineup rows are present in the snapshot.">
            <EmptyState message="No fixture lineup data is available." />
          </SectionCard>
        ) : (
          grouped.map(([league, rows]) => (
            <SectionCard
              key={league}
              title={<LeagueLabel league={league} label={league} className="text-[15px] font-semibold text-slate-100" iconSize={16} />}
              subtitle={`${rows.length} ${rows.length === 1 ? "fixture" : "fixtures"}`}
            >
              <div className="flex flex-col gap-4">
                {rows.map((fixture) => (
                  <FixtureCard key={fixture.key} fixture={fixture} />
                ))}
              </div>
            </SectionCard>
          ))
        )}

      </div>
    </div>
  );
}

