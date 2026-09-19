"use client";

import Link from "next/link";
import { useState } from "react";
import { foldNameText } from "@/lib/player-name-matching";
import PenaltyTakerPortrait from "./PenaltyTakerPortrait";

type League = { key: string; label: string; logoPath: string; teams: {
  name: string; url: string; logoPath: string; players: string[]; portraits?: (string | null)[];
}[] };

const normalize = (value: string) => foldNameText(value).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const control = "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300";

export default function PenaltyDirectory({ leagues, initialLeague = "all", boardHref = "#league-guides", hasUpdates = true }: {
  leagues: League[]; initialLeague?: string; boardHref?: string; hasUpdates?: boolean;
}) {
  const [selected, setSelected] = useState(initialLeague);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const tokens = normalize(query).split(" ").filter(Boolean);
  const available = leagues.filter(league => selected === "all" || league.key === selected);
  const matches = available.flatMap(league => league.teams.map(team => ({ ...team, league: league.label })))
    .filter(team => tokens.every(token => normalize(`${team.name} ${team.players.join(" ")} ${team.league}`).includes(token)));
  const visible = expanded || tokens.length ? matches : matches.slice(0, 4);

  return <section id="penalty-finder" aria-labelledby="penalty-finder-title" className="mb-8 scroll-mt-24 rounded-3xl border border-emerald-300/20 bg-[linear-gradient(135deg,#102621,#101820)] p-4 sm:p-6">
    <nav aria-label="Penalty taker sections" className="mb-5 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      <a href="#penalty-finder" className={`${control} border-emerald-300/30 bg-emerald-300/15 text-emerald-100`}>Find a taker <span aria-hidden="true">⌕</span></a>
      <a href={boardHref} className={`${control} border-white/10 bg-white/5 text-slate-200`}>Full hierarchies <span aria-hidden="true">↓</span></a>
      {hasUpdates && <a href="#latest-penalty-taker-updates" className={`${control} border-white/10 bg-white/5 text-slate-200`}>Latest changes <span aria-hidden="true">↓</span></a>}
      <Link prefetch={false} href="/penalty-takers/methodology" className={`${control} border-white/10 bg-white/5 text-slate-200`}>How it works <span aria-hidden="true">↗</span></Link>
    </nav>
    <h2 id="penalty-finder-title" className="text-xl font-semibold tracking-tight text-white sm:text-2xl">Find your team or penalty taker</h2>
    <p className="mt-1 text-sm leading-6 text-slate-300">Choose a league or search any player in the penalty order.</p>
    <div role="group" aria-label="Filter penalty takers by league" className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {[{ key: "all", label: "All leagues", logoPath: "", teams: leagues.flatMap(league => league.teams) }, ...leagues].map(league => (
        <button key={league.key} type="button" aria-pressed={selected === league.key} onClick={() => { setSelected(league.key); setExpanded(false); }} className={`${control} justify-start text-left ${selected === league.key ? "border-emerald-300 bg-emerald-300/15 text-emerald-100 shadow-[inset_0_-2px_0_#6ee7b7]" : "border-slate-600/60 bg-slate-900/60 text-slate-300 hover:border-emerald-300/60 hover:bg-emerald-300/10"}`}>
          {league.logoPath ? <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={league.logoPath} alt="" width="22" height="22" className="h-5 w-5 object-contain" />
          </span> : <span aria-hidden="true" className="text-xl text-emerald-300">◇</span>}
          <span className="min-w-0 flex-1 text-xs sm:text-sm">{league.label}</span>
          <span className="rounded bg-black/20 px-1.5 py-0.5 text-[10px] tabular-nums">{league.teams.length}</span>
        </button>
      ))}
    </div>
    <div role="search" className="mt-5">
      <label htmlFor="penalty-directory-search" className="mb-2 block text-sm font-semibold text-slate-200">Search teams or players</label>
      <div className="flex gap-2">
        <input id="penalty-directory-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Try Arsenal, Palmer or Grimaldo…" autoComplete="off" autoCapitalize="off" spellCheck={false} aria-controls="penalty-directory-results" className="min-h-12 min-w-0 flex-1 rounded-xl border border-slate-500/70 bg-slate-950/70 px-4 py-3 text-base text-white placeholder:text-slate-400 focus:border-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-300/20" />
        {query && <button type="button" onClick={() => setQuery("")} className={`${control} border-slate-600 text-slate-200`}>Clear</button>}
      </div>
    </div>
    <p role="status" aria-live="polite" className="my-3 text-xs text-slate-400">{tokens.length ? `${matches.length} matching ${matches.length === 1 ? "club" : "clubs"}` : `${matches.length} clubs • Open a club to see its full order and evidence`}</p>
    <ul id="penalty-directory-results" className="grid gap-2 sm:grid-cols-2">
      {visible.map(team => <li key={team.url}>
        <Link prefetch={false} href={team.url} className="group block h-full rounded-2xl border border-slate-700/70 bg-slate-950/50 p-4 transition hover:border-emerald-300/50 hover:bg-emerald-300/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-300">
          <span className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={team.logoPath} alt="" width="36" height="36" loading="lazy" className="h-9 w-9 shrink-0 rounded-lg bg-white object-contain p-1" />
          <span className="min-w-0 flex-1">
            <span className="flex items-center justify-between gap-2 font-semibold text-slate-100"><span>{team.name}</span><span aria-hidden="true" className="text-emerald-300">↗</span></span>
            <span className="mb-2 block text-[11px] text-slate-400">{team.league}</span>
          </span></span>
            <span className="penalty-preview-order">
              {team.players.map((name, i) => <span key={`${i}-${name}`} className={`penalty-preview-player ${i === 0 ? "penalty-preview-primary" : ""}`}>
                <PenaltyTakerPortrait name={name} src={team.portraits?.[i]} rank={i + 1} size={i === 0 ? "medium" : "small"} />
                <span><small>{i === 0 ? "First choice" : i === 1 ? "Second choice" : "Third choice"}</small><strong>{name}</strong></span>
              </span>)}
            </span>
            <span className="mt-3 block text-xs font-semibold text-emerald-300">View order &amp; evidence <span aria-hidden="true">→</span></span>
        </Link>
      </li>)}
    </ul>
    {!matches.length && <div className="rounded-xl border border-slate-600 p-4 text-sm text-slate-200">No matching taker in this league. Try another name or <button type="button" className="font-semibold text-emerald-300 underline" onClick={() => setSelected("all")}>search all leagues</button>.</div>}
    {!tokens.length && matches.length > 4 && <button type="button" aria-expanded={expanded} aria-controls="penalty-directory-results" onClick={() => setExpanded(!expanded)} className={`${control} mt-3 w-full border-emerald-300/25 bg-emerald-300/10 text-emerald-100`}>{expanded ? "Show fewer clubs" : `Browse all ${matches.length} clubs`} <span aria-hidden="true" className="text-lg">{expanded ? "↑" : "↓"}</span></button>}
  </section>;
}
