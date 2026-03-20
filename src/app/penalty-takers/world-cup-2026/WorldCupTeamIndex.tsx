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
  likely_primary?: string;
  slug: string;
  flagUrl: string;
  initials: string;
};

type Props = {
  teams: IndexTeam[];
  confederations: ConfederationFilter[];
};

const ALL_FILTER = "All";

function filterFromHash(hash: string): string {
  const clean = hash.replace(/^#/, "").trim().toLowerCase();
  if (!clean) return ALL_FILTER;
  const match = ["UEFA", "CONMEBOL", "Concacaf", "AFC", "CAF", "OFC"].find(
    (confederation) => confederation.toLowerCase() === clean,
  );
  return match ?? ALL_FILTER;
}

export default function WorldCupTeamIndex({ teams, confederations }: Props) {
  const [activeFilter, setActiveFilter] = useState<string>(ALL_FILTER);

  useEffect(() => {
    setActiveFilter(filterFromHash(window.location.hash));
  }, []);

  const filteredTeams = useMemo(() => {
    if (activeFilter === ALL_FILTER) return teams;
    return teams.filter((team) => team.confederation === activeFilter);
  }, [activeFilter, teams]);

  return (
    <section className="mt-6 rounded-3xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-[0_18px_50px_rgba(0,0,0,0.18)]">
      <div className="font-mono text-xs uppercase tracking-[0.28em] text-emerald-400">Nation Index</div>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-100">Quick answers by nation</h2>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-400">
            Filter the field by confederation or scan the full list alphabetically. Every card jumps straight to the country page with the full evidence trail underneath it.
          </p>
        </div>
        <Link
          href="/penalty-takers"
          className="rounded-full border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
        >
          Club penalty takers
        </Link>
      </div>

      <div className="sticky top-3 z-20 mt-6 rounded-2xl border border-slate-800/80 bg-slate-950/92 p-3 backdrop-blur">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveFilter(ALL_FILTER)}
            className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
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
              className={`rounded-full border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] transition ${
                activeFilter === confederation.key
                  ? confederation.badgeClassName
                  : "border-slate-700 bg-slate-950 text-slate-400 hover:border-slate-500 hover:text-slate-200"
              }`}
            >
              {confederation.key} <span className="text-white/55">{confederation.count}</span>
            </button>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="text-slate-500">Jump to editorial notes:</span>
          {confederations.map((confederation) => (
            <a
              key={`jump-${confederation.key}`}
              href={`#${confederation.key.toLowerCase()}`}
              onClick={() => setActiveFilter(confederation.key)}
              className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-[11px] text-slate-300 transition hover:border-slate-500 hover:text-slate-100"
            >
              {confederation.key}
            </a>
          ))}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between gap-3">
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
            key={`az-${team.team}`}
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
                <div className="truncate text-sm font-semibold text-slate-100">{team.team}</div>
                <div className="rounded-full border border-slate-700 bg-slate-950 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">
                  {team.confederation}
                </div>
              </div>
              <div className="mt-1 truncate text-xs text-slate-400">{team.likely_primary || "Board still being built"}</div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
