"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type ConfederationFilter = {
  key: string;
  count: number;
  badgeClassName: string;
};

type IndexTeam = {
  team: string;
  confederation: string;
  group?: string;
  likely_primary?: string;
  slug: string;
  flagUrl: string;
  initials: string;
};

type GroupEntry =
  | (IndexTeam & {
      kind: "team";
      group: string;
    })
  | {
      kind: "placeholder";
      team: string;
      group: string;
      initials: string;
      note: string;
    };

type GroupFilter = {
  key: string;
  count: number;
  entries: GroupEntry[];
};

type Props = {
  teams: IndexTeam[];
  confederations: ConfederationFilter[];
  groups: GroupFilter[];
};

const ALL_FILTER = "All";
const ALL_GROUPS = "All groups";

function filterFromHash(hash: string): string {
  const clean = hash.replace(/^#/, "").trim().toLowerCase();
  if (!clean) return ALL_FILTER;
  const match = ["UEFA", "CONMEBOL", "Concacaf", "AFC", "CAF", "OFC"].find(
    (confederation) => confederation.toLowerCase() === clean,
  );
  return match ?? ALL_FILTER;
}

export default function WorldCupTeamIndex({ teams, confederations, groups }: Props) {
  const [viewMode, setViewMode] = useState<"confederation" | "group">("confederation");
  const [activeFilter, setActiveFilter] = useState<string>(ALL_FILTER);
  const [activeGroup, setActiveGroup] = useState<string>(ALL_GROUPS);

  useEffect(() => {
    setActiveFilter(filterFromHash(window.location.hash));
  }, []);

  const filteredTeams = useMemo(() => {
    if (activeFilter === ALL_FILTER) return teams;
    return teams.filter((team) => team.confederation === activeFilter);
  }, [activeFilter, teams]);

  const visibleGroups = useMemo(() => {
    if (activeGroup === ALL_GROUPS) return groups;
    return groups.filter((group) => group.key === activeGroup);
  }, [activeGroup, groups]);

  return (
    <section className="mt-6 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-5 shadow-[0_12px_32px_rgba(0,0,0,0.16)] sm:p-6 sm:shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Nation Index</div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-100">Quick answers by nation</h2>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
            Use confederation view for the qualification context, or flip to groups for the tournament lens.
            Every live nation card jumps straight to the penalty-taker page with the evidence trail underneath it.
          </p>
        </div>
        <Link
          href="/penalty-takers"
          className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
        >
          Club penalty takers
        </Link>
      </div>

      <div className="mt-6 rounded-2xl border border-slate-800/80 bg-slate-950/96 p-3 lg:sticky lg:top-4 lg:z-20 lg:backdrop-blur">
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:px-0">
          <button
            type="button"
            onClick={() => setViewMode("confederation")}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
              viewMode === "confederation"
                ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
                : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
            }`}
          >
            By confederation
          </button>
          <button
            type="button"
            onClick={() => setViewMode("group")}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
              viewMode === "group"
                ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
                : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
            }`}
          >
            By group
          </button>
        </div>

        {viewMode === "confederation" ? (
          <>
            <div className="mt-3 -mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
              <button
                type="button"
                onClick={() => setActiveFilter(ALL_FILTER)}
                className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
                  activeFilter === ALL_FILTER
                    ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
                    : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                }`}
              >
                All teams
              </button>
              {confederations.map((confederation) => (
                <button
                  key={confederation.key}
                  type="button"
                  onClick={() => setActiveFilter(confederation.key)}
                  className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
                    activeFilter === confederation.key
                      ? confederation.badgeClassName
                      : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                  }`}
                >
                  {confederation.key} <span className="text-white/55">{confederation.count}</span>
                </button>
              ))}
            </div>

            <div className="mt-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Jump to editorial notes</div>
              <div className="-mx-1 mt-2 flex gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
                {confederations.map((confederation) => (
                  <a
                    key={`jump-${confederation.key}`}
                    href={`#${confederation.key.toLowerCase()}`}
                    onClick={() => setActiveFilter(confederation.key)}
                    className="shrink-0 rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-[11px] text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
                  >
                    {confederation.key}
                  </a>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="mt-3 -mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:px-0">
              <button
                type="button"
                onClick={() => setActiveGroup(ALL_GROUPS)}
                className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
                  activeGroup === ALL_GROUPS
                    ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
                    : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                }`}
              >
                All groups
              </button>
              {groups.map((group) => (
                <button
                  key={group.key}
                  type="button"
                  onClick={() => setActiveGroup(group.key)}
                  className={`shrink-0 rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
                    activeGroup === group.key
                      ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
                      : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
                  }`}
                >
                  Group {group.key} <span className="text-white/55">{group.count}</span>
                </button>
              ))}
            </div>

            <div className="mt-3 rounded-2xl border border-slate-800/80 bg-slate-900/80 px-3 py-3 text-sm leading-6 text-slate-400">
              Group view is the tournament lens. Grey cards mark unresolved UEFA or intercontinental slots that drop
              straight into their final group once the play-offs finish.
            </div>
          </>
        )}
      </div>

      {viewMode === "confederation" ? (
        <>
          <div className="mt-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <div className="text-sm text-slate-400">
              Showing <span className="text-slate-100">{filteredTeams.length}</span>{" "}
              {activeFilter === ALL_FILTER ? "qualified teams" : `${activeFilter} teams`}
            </div>
            {activeFilter !== ALL_FILTER ? (
              <a
                href={`#${activeFilter.toLowerCase()}`}
                className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
              >
                Jump to {activeFilter} notes
              </a>
            ) : null}
          </div>

          <div className="mt-6 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {filteredTeams.map((team) => (
              <Link
                key={`conf-${team.team}`}
                href={`/penalty-takers/world-cup-2026/${team.slug}`}
                className="flex items-center gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/70 px-3 py-3 transition hover:border-slate-600 hover:bg-slate-950"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/80">
                  {team.flagUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={team.flagUrl} alt={`${team.team} flag`} className="h-6 w-8 rounded-[3px] object-cover" />
                  ) : (
                    <span className="font-mono text-[11px] text-slate-200">{team.initials}</span>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="truncate text-sm font-semibold text-slate-100">{team.team} penalty taker</div>
                    <div className="rounded-full border border-slate-700 bg-slate-950 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">
                      {team.confederation}
                    </div>
                    {team.group ? (
                      <div className="rounded-full border border-slate-700 bg-slate-950 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-500">
                        Group {team.group}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-1 truncate text-xs text-slate-400">{team.likely_primary || "Board still being built"}</div>
                </div>
              </Link>
            ))}
          </div>
        </>
      ) : (
        <div className="mt-6 space-y-4">
          {visibleGroups.map((group) => (
            <section key={`group-${group.key}`} className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-xl font-semibold tracking-tight text-slate-100">Group {group.key}</h3>
                  <div className="mt-1 text-sm text-slate-400">{group.count} slots locked into this part of the draw.</div>
                </div>
                <span className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                  Tournament view
                </span>
              </div>

              <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {group.entries.map((entry) =>
                  entry.kind === "team" ? (
                    <Link
                      key={`group-team-${group.key}-${entry.team}`}
                      href={`/penalty-takers/world-cup-2026/${entry.slug}`}
                      className="flex items-center gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/80 px-3 py-3 transition hover:border-slate-600 hover:bg-slate-950"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/80">
                        {entry.flagUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={entry.flagUrl} alt={`${entry.team} flag`} className="h-6 w-8 rounded-[3px] object-cover" />
                        ) : (
                          <span className="font-mono text-[11px] text-slate-200">{entry.initials}</span>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-slate-100">{entry.team}</div>
                        <div className="mt-1 truncate text-xs text-slate-400">{entry.likely_primary || "Board still being built"}</div>
                      </div>
                    </Link>
                  ) : (
                    <div
                      key={`group-placeholder-${group.key}-${entry.team}`}
                      className="flex items-center gap-3 rounded-2xl border border-dashed border-slate-700/80 bg-slate-950/45 px-3 py-3"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-900/70">
                        <span className="font-mono text-[11px] text-slate-400">{entry.initials}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-slate-300">{entry.team}</div>
                        <div className="mt-1 text-xs text-slate-500">{entry.note}</div>
                      </div>
                    </div>
                  ),
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
