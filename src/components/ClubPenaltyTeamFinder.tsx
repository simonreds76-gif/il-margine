"use client";

import { useState } from "react";

type ClubFinderTeam = {
  name: string;
  slug: string;
  logoPath: string;
  initials: string;
};

type Props = {
  leagueLabel: string;
  teams: ClubFinderTeam[];
};

function normalizeSearch(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function ClubJumpLink({ team, onNavigate }: { team: ClubFinderTeam; onNavigate?: () => void }) {
  return (
    <a
      href={`#club-${team.slug}`}
      onClick={onNavigate}
      title={team.name}
      className="group flex min-h-12 min-w-0 items-center gap-2 rounded-xl border border-slate-700/75 bg-slate-950/75 px-2.5 py-2.5 transition hover:border-emerald-400/40 hover:bg-emerald-400/8 focus-visible:border-emerald-300 sm:gap-3 sm:px-3"
      aria-label={`Jump to ${team.name}`}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white/15 bg-white">
        {team.logoPath ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={team.logoPath} alt="" className="h-6 w-6 object-contain" loading="lazy" />
        ) : (
          <span className="font-mono text-[9px] font-bold text-slate-700">{team.initials}</span>
        )}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-200 transition group-hover:text-emerald-100">
        {team.name}
      </span>
      <span aria-hidden="true" className="hidden shrink-0 text-emerald-400/80 sm:inline">&darr;</span>
    </a>
  );
}

export default function ClubPenaltyTeamFinder({ leagueLabel, teams }: Props) {
  const [query, setQuery] = useState("");
  const normalizedQuery = normalizeSearch(query);
  const matches = normalizedQuery
    ? teams.filter((team) => normalizeSearch(`${team.name} ${team.initials}`).includes(normalizedQuery))
    : teams;

  return (
    <section
      id="club-finder"
      aria-labelledby="club-finder-title"
      className="scroll-mt-24 rounded-3xl border border-emerald-400/20 bg-[linear-gradient(145deg,rgba(6,25,20,0.95),rgba(8,14,24,0.98))] p-4 shadow-[0_18px_50px_rgba(0,0,0,0.22)] sm:p-5"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-emerald-400">Club shortcuts</div>
          <h2 id="club-finder-title" className="mt-1.5 text-xl font-semibold text-slate-100">Find a {leagueLabel} club</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">Search or browse the full league, then jump straight to its penalty order.</p>
        </div>
        <span className="w-fit rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-slate-300">
          {teams.length} clubs
        </span>
      </div>

      <div role="search" className="mt-4">
        <label htmlFor="club-finder-search" className="mb-2 block text-xs font-semibold text-slate-300">
          Search by club name
        </label>
        <div className="relative">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500">
            <path d="m21 21-4.4-4.4m2.4-5.1a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <input
            id="club-finder-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${leagueLabel} clubs`}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-controls={normalizedQuery ? "club-search-results" : "club-browse-list"}
            className="min-h-12 w-full rounded-xl border border-slate-700 bg-slate-950/85 py-3 pl-11 pr-4 text-base text-slate-100 placeholder:text-slate-600 transition focus:border-emerald-400/60 focus:outline-none focus:ring-2 focus:ring-emerald-400/15"
          />
        </div>
      </div>

      {normalizedQuery ? (
        <div id="club-search-results" className="mt-3">
          <p role="status" aria-live="polite" aria-atomic="true" className="mb-2 text-xs text-slate-400">
            {matches.length ? `${matches.length} ${matches.length === 1 ? "club" : "clubs"} found` : "No clubs found"}
          </p>
          {matches.length ? (
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {matches.map((team) => (
                <li key={team.slug}>
                  <ClubJumpLink team={team} onNavigate={() => setQuery("")} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-xl border border-amber-300/20 bg-amber-400/8 px-4 py-3 text-sm text-amber-100">
              Try another spelling or clear the search to browse every club.
            </div>
          )}
        </div>
      ) : (
        <details className="group mt-3 rounded-2xl border border-slate-700/75 bg-slate-950/45">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-200 marker:content-none hover:text-emerald-100 [&::-webkit-details-marker]:hidden">
            <span>Browse all {teams.length} clubs</span>
            <span aria-hidden="true" className="text-emerald-400 transition group-open:rotate-180">&darr;</span>
          </summary>
          <ul id="club-browse-list" className="grid grid-cols-2 gap-2 border-t border-slate-800 p-3 lg:grid-cols-4">
            {teams.map((team) => (
              <li key={team.slug}>
                <ClubJumpLink team={team} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
