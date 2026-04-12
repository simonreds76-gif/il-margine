import { notFound } from "next/navigation";

import { type GoalscorerFixtureLineup, readGoalscorerMonitorSnapshot } from "@/lib/goalscorer-monitor-snapshot";

import {
  EmptyState,
  HeroCard,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  SectionCard,
  StatCard,
  StatusPill,
  formatDateTimeLabel,
  formatOdds,
  formatPct,
  statusTone,
  toneClass,
} from "../shared";

export const dynamic = "force-dynamic";

function kickoffSortValue(value?: string | null) {
  if (!value) return Number.MAX_SAFE_INTEGER;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00Z`).getTime();
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : Number.MAX_SAFE_INTEGER;
}

function groupFixturesByLeague(rows: GoalscorerFixtureLineup[]) {
  const grouped = new Map<string, GoalscorerFixtureLineup[]>();
  for (const row of [...rows].sort((a, b) => kickoffSortValue(a.kickoff) - kickoffSortValue(b.kickoff))) {
    const bucket = grouped.get(row.league_label) || [];
    bucket.push(row);
    grouped.set(row.league_label, bucket);
  }
  return [...grouped.entries()];
}

function PlayerRow({
  player,
}: {
  player: GoalscorerFixtureLineup["home"]["attackers"][number];
}) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-white">{player.name}</div>
          <div className="mt-1 text-xs text-slate-500">{player.position}{player.expected_minutes ? ` · ${Math.round(player.expected_minutes)} mins` : ""}</div>
        </div>
        <StatusPill label={player.action_label || player.action || "monitor"} tone={statusTone(player.action_label || player.action)} />
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <StatCard label="Odds" value={formatOdds(player.odds)} />
        <StatCard label="Fair" value={formatOdds(player.fair)} />
        <StatCard label="Edge" value={formatPct(player.ev_pct)} tone={toneClass(player.ev_pct)} />
      </div>
      {player.penalty_meta ? <p className="mt-3 text-xs text-amber-200">{player.penalty_meta.compact}</p> : null}
      {player.note ? <p className="mt-2 text-xs text-slate-500">{player.note}</p> : null}
    </div>
  );
}

function PlayerSection({
  label,
  rows,
}: {
  label: string;
  rows: GoalscorerFixtureLineup["home"]["attackers"];
}) {
  if (rows.length === 0) return null;
  return (
    <div className="space-y-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="space-y-3">
        {rows.map((player) => (
          <PlayerRow key={player.key} player={player} />
        ))}
      </div>
    </div>
  );
}

function TeamColumn({
  side,
}: {
  side: GoalscorerFixtureLineup["home"];
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/25 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{side.team}</h3>
          <p className="mt-1 text-sm text-slate-400">{side.lineup_status || "No lineup status"}</p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{side.total_players} projected players</div>
          <div>{side.matched_players} priced rows matched</div>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {side.keeper ? (
          <div className="space-y-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Keeper</div>
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

function FixtureCard({ fixture }: { fixture: GoalscorerFixtureLineup }) {
  return (
    <article className="rounded-3xl border border-slate-800 bg-[linear-gradient(180deg,rgba(17,24,39,0.96),rgba(10,14,23,0.92))] p-5 shadow-[0_20px_60px_rgba(2,6,23,0.35)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{fixture.competition}</div>
          <h2 className="mt-2 text-2xl font-semibold text-white">{fixture.home_team} vs {fixture.away_team}</h2>
          <p className="mt-1 text-sm text-slate-400">{formatDateTimeLabel(fixture.kickoff || fixture.match_date)} · {fixture.bookmaker || "Unknown book"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill
            label={fixture.health?.status_label || (fixture.has_any_lineup ? "lineups loaded" : "no lineup data")}
            tone={statusTone(fixture.health?.trust_tier || fixture.health?.status_label || (fixture.has_any_lineup ? "confirmed" : "no feed"))}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-4">
        <StatCard label="Priced rows" value={String(fixture.matched_player_prices)} />
        <StatCard label="Home matched" value={String(fixture.home.matched_players)} />
        <StatCard label="Away matched" value={String(fixture.away.matched_players)} />
        <StatCard label="Health" value={fixture.health?.trust_tier || "-"} detail={fixture.health?.summary || undefined} />
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <TeamColumn side={fixture.home} />
        <TeamColumn side={fixture.away} />
      </div>
    </article>
  );
}

export default async function GoalscorerLineupsPage() {
  if (!MODEL_MONITOR_ENABLED) notFound();

  const snapshot = await readGoalscorerMonitorSnapshot();
  if (!snapshot) {
    return (
      <div className="min-h-screen bg-[#0a0f19] px-6 py-8 text-slate-200">
        <div className="mx-auto max-w-7xl">
          <MonitorNav current="lineups" />
          <HeroCard title="Goalscorer Lineups" eyebrow="Snapshot-first lineups">
            The lineups snapshot is not available yet. Once the hosted monitor snapshot is published, this page will
            render from the same payload as the main goalscorer monitor.
          </HeroCard>
        </div>
      </div>
    );
  }

  const fixtures = snapshot.fixture_lineups;
  const grouped = groupFixturesByLeague(fixtures);
  const fixturesWithLineups = fixtures.filter((fixture) => fixture.has_any_lineup).length;
  const matchedRows = fixtures.reduce((total, fixture) => total + fixture.matched_player_prices, 0);

  return (
    <div className="min-h-screen bg-[#0a0f19] px-6 py-8 text-slate-200">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <MonitorNav current="lineups" />

        <HeroCard title="Goalscorer Lineups" eyebrow="Snapshot-backed fixture view">
          <p>Every fixture card below is rendered from the compact goalscorer monitor snapshot.</p>
          <p className="mt-2 text-slate-400">Snapshot generated {formatDateTimeLabel(snapshot.generated_at)}.</p>
        </HeroCard>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard label="Fixtures" value={String(fixtures.length)} />
          <StatCard label="With lineups" value={String(fixturesWithLineups)} />
          <StatCard label="Matched prices" value={String(matchedRows)} />
          <StatCard label="Flagged fixtures" value={String(snapshot.fixture_health.flagged_rows.length)} />
          <StatCard label="Penalty reviews" value={String(snapshot.penalty_watchlist.row_count)} />
        </section>

        {grouped.length === 0 ? (
          <SectionCard title="Fixtures" subtitle="No fixture lineup rows are present in the snapshot.">
            <EmptyState message="No fixture lineup data is available." />
          </SectionCard>
        ) : (
          grouped.map(([league, rows]) => (
            <SectionCard key={league} title={league} subtitle={`${rows.length} fixtures in the snapshot`}>
              <div className="flex flex-col gap-5">
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

