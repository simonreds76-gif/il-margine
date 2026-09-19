"use client";

import Image from "next/image";
import PageHomeLink from "@/components/PageHomeLink";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { DisclosureCue } from "./DisclosureCue";
import { PlayerLabelGuide } from "./PlayerLabelGuide";
import { resolveTeamLogoPath } from "@/lib/team-logos";
import "./daily-pitch.css";
import "./editorial-pitch.css";

import { isDailyBoard, type BoardPlayer, type BoardFixture, type DailyBoard } from "./daily-board-data";
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const decimal = (n: unknown) => finite(n) ? (n >= 100 ? n.toFixed(1) : n.toFixed(2)) : "—";
const priceVerdict = (gap: number | null) => gap === null ? "Not compared" : gap > 0 ? "Better price" : gap < 0 ? "Below fair" : "Matches fair";
const stamp = (s: string | null) => s && Number.isFinite(Date.parse(s)) ? new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" }).format(new Date(s)) : "Not available";
const day = (n: number) => new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(n));

function openSection(id: string) {
  const element = document.getElementById(id);
  if (!element) return;
  let ancestor: HTMLElement | null = element;
  while (ancestor) {
    if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
    ancestor = ancestor.parentElement;
  }
  element.scrollIntoView({ block: "start", behavior: "instant" });
}

function Portrait({ player }: { player: BoardPlayer }) {
  const [failed, setFailed] = useState(false);
  const photo = player.photoUrl?.match(/^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/);
  return photo && !failed ? <Image unoptimized src={player.photoUrl!} alt="" width={42} height={42} className="ip-photo" onError={() => setFailed(true)} /> : <span className="ip-shirt" aria-hidden="true">{player.number ?? ""}</span>;
}

function ClubBadge({ name, path, league }: { name: string; path?: string; league: string }) {
  const [failedPath, setFailedPath] = useState<string | null>(null);
  const category = ({ epl: "pl", "serie-a": "seriea", "la-liga": "laliga", "ligue-1": "ligue1" } as Record<string, string>)[league] ?? league;
  const source = path?.startsWith("/team-logos/") ? path : resolveTeamLogoPath(name, category);
  return <span className="ip-club-badge">{source && failedPath !== source
    ? <Image unoptimized src={source} alt={`${name} crest`} width={48} height={48} onError={() => setFailedPath(source)} />
    : <span aria-label={name}>{name.split(/\s+/).map(word => word[0]).slice(0, 3).join("")}</span>}</span>;
}

function comparison(p: BoardPlayer, f: BoardFixture, now: number, snapshot: string | null) {
  const capture = Date.parse(p.priceCapturedAt ?? "");
  const change = Date.parse(f.lineupChangedAt ?? "");
  const snapshotAge = now - Date.parse(snapshot ?? "");
  const started = now >= Date.parse(f.kickoffUtc);
  const fresh = Number.isFinite(capture) && now >= capture && now - capture <= 65 * 60_000 &&
    (!Number.isFinite(change) || capture >= change) && snapshotAge >= -60_000 && snapshotAge <= 90 * 60_000;
  const pModel = finite(p.modelProbability) && p.modelProbability > 0 && p.modelProbability < 1 ? p.modelProbability : null;
  const odds = finite(p.bookmakerOdds) && p.bookmakerOdds > 1 ? p.bookmakerOdds : null;
  const comparable = !!(pModel && odds && fresh && !started && p.pricingStatus !== "limited_data");
  return { started, fresh, fair: pModel ? 1 / pModel : null, gap: comparable ? 100 * (pModel! - 1 / odds!) : null, ev: comparable ? 100 * (pModel! * odds! - 1) : null };
}

type PlayerSelection = { fixtureId: string; side: number; id: string };
const detailIdFor = (id: string) => `player-detail-${encodeURIComponent(id)}`;

function MatchPitch({ fixture: f, now, snapshot, view, selected, setSelected }: { fixture: BoardFixture; now: number; snapshot: string | null; view: string; selected: PlayerSelection | null; setSelected: (value: {side: number; id: string} | null) => void }) {
  const [side, setSide] = useState(0);
  const player = selected ? f.teams[selected.side]?.players.find(p => p.id === selected.id) : null;
  const metrics = player ? comparison(player, f, now, snapshot) : null;
  const detailId = detailIdFor(f.id);
  const started = now >= Date.parse(f.kickoffUtc);
  return <details id={`match-${f.id}`} className="ip-match" aria-label={`${f.teams[0].name} versus ${f.teams[1].name}`}>
    <summary className="ip-match-summary">
      <div className="ip-match-meta"><span>{f.competition} · {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" }).format(new Date(f.kickoffUtc))} · {stamp(f.kickoffUtc)} UK</span><span className={`ip-status-chip ${f.lineupStatus === "confirmed" ? "positive" : "pending"}`}>{started ? "Pre-match snapshot" : f.lineupStatus === "confirmed" ? "Confirmed lineups" : f.lineupStatus === "pending" ? "Lineups pending" : "Expected lineups"}</span></div>
      <div className="ip-fixture-preview">{f.teams.map((team, i) => {
        const outfield = team.players.filter(p => p.role !== "GK");
        return <div className="ip-preview-team" key={team.name}><ClubBadge name={team.name} path={team.logoPath} league={f.league} /><div><span className="ip-preview-side">{i === 0 ? "Home" : "Away"}{team.formation ? ` · ${team.formation}` : ""}</span><h3>{team.name}</h3><span className="ip-preview-coverage">Our fair odds <strong>{outfield.filter(p => p.modelProbability !== null).length}/{outfield.length}</strong> · Bet365 odds <strong>{outfield.filter(p => p.bookmakerOdds !== null).length}/{outfield.length}</strong></span></div></div>;
      })}</div>
      <span className="ip-expand-hint"><span><strong>Lineups &amp; player odds</strong><small>Lineup checked {stamp(f.lineupObservedAt)} UK</small></span><DisclosureCue /></span>
    </summary>
    <div className="ip-match-context"><div><span className="ip-context-icon" aria-hidden="true">◎</span><div><strong>Match notes</strong><p>{f.lineupStatus === "confirmed" ? "Official starting XIs received. Player prices reflect the supplied lineup." : "Expected XIs. Our fair odds assume each listed player starts."}</p></div></div><div><span className="ip-context-icon" aria-hidden="true">P</span><div><strong>Penalty duties in this XI</strong><p>{f.teams.map(t => `${t.name}: ${t.activePenaltyTaker || "Not assigned"}`).join(" · ")}</p></div></div></div>
    {f.teams.filter(t => t.penaltyInheritedFrom && t.activePenaltyTaker).map(t => <div className="ip-pennews" key={t.name}><strong>Expected penalty duty</strong><span>{t.penaltyInheritedFrom} not starting → {t.activePenaltyTaker}</span></div>)}
    {view === "pitch" && <div className="ip-switch ip-teamtabs" aria-label="Team">{f.teams.map((t, i) => <button key={t.name} type="button" aria-pressed={side === i} onClick={() => setSide(i)}><ClubBadge name={t.name} path={t.logoPath} league={f.league} /><span>{t.name}<small>{i === 0 ? "Home" : "Away"}{t.formation ? ` · ${t.formation}` : ""}</small></span></button>)}</div>}
    {view === "pitch" ? <div className="ip-board">{f.teams.map((team, teamIndex) => {
      const validLines = team.players.every(p => Number.isInteger(p.lineIndex)) && team.players.filter(p => p.lineIndex === -1).length === 1 && !!team.formation;
      const lines = validLines ? [...new Set(team.players.map(p => p.lineIndex!))].sort((a, b) => b - a).map(line => team.players.filter(p => p.lineIndex === line)) : [team.players];
      return <section key={team.name} className={`ip-club ${side === teamIndex ? "ip-active" : ""}`} style={{ "--ip-kit": team.primaryColor?.match(/^#[0-9a-f]{6}$/i) ? team.primaryColor : teamIndex ? "#efc2d1" : "#c6e7ff", "--ip-kit-ink": "#ffffff" } as CSSProperties}>
        <div className="ip-clubhead"><span className="ip-clubname"><ClubBadge name={team.name} path={team.logoPath} league={f.league} />{team.name}</span><span className="ip-sub">{validLines ? team.formation : "Positions pending"}</span></div>
        {!team.lineupComplete && <p className="ip-bench">Lineup incomplete · {team.players.length}/11 players supplied</p>}
        <div className="ip-pitch-key"><span>↑ Attacking direction</span><span><i /> Our fair odds <b /> Bet365</span></div><div className={`ip-field ${validLines ? "" : "ip-ungrouped"}`}><div className="ip-lines" aria-hidden="true"><div className="ip-center" /><div className="ip-area top" /><div className="ip-area bottom" /></div>
          {lines.map((line, i) => <div key={i} className="ip-row">{line.map(p => { const c = comparison(p, f, now, snapshot); return <button key={p.id} type="button" className="ip-player" aria-label={`${p.name}, our fair odds ${decimal(c.fair)}, Bet365 odds ${decimal(p.bookmakerOdds)}${!c.fresh ? ", bookmaker odds unavailable or awaiting an update" : ""}`} aria-pressed={selected?.side === teamIndex && selected.id === p.id} aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}><Portrait player={p} />{p.penaltyActive && <span className="ip-pen">PEN</span>}<span className="ip-name">{p.name}</span><span className={`ip-price ${!c.fresh ? "ip-aged" : ""}`}><span className="ip-fair" title={p.pricingStatus === "limited_data" ? "Estimate based on limited player history." : "Our estimated fair odds"}><span className="ip-price-label">Our fair odds</span><strong>{c.fair === null ? "Unpriced" : decimal(c.fair)}{p.pricingStatus === "limited_data" ? "*" : ""}</strong></span><span className="ip-book" title={p.bookmakerOdds === null ? "We haven’t received Bet365 odds for this player yet." : "Bet365 decimal odds"}><span className="ip-price-label">Bet365</span><strong>{p.bookmakerOdds === null ? "No odds" : decimal(p.bookmakerOdds)}</strong></span></span><span className={`ip-gap ${c.gap !== null && c.gap < 0 ? "minus" : ""}`}>{c.gap === null ? p.pricingStatus === "limited_data" ? "Estimate*" : started ? "Match started" : p.bookmakerOdds && !c.fresh ? "Odds need rechecking" : "Not compared" : priceVerdict(c.gap)}</span></button>; })}</div>)}
        </div><details className="ip-bench"><summary>Bench · {team.substitutes.length} players <DisclosureCue /></summary><p>{team.substitutes.join(" · ") || "Substitutes not supplied"}</p></details>
      </section>;
    })}</div> : <div className="ip-list"><table><thead><tr><th>Player</th><th>Our fair odds</th><th>Bet365 odds</th><th>Price check</th></tr></thead><tbody>{f.teams.flatMap((team, teamIndex) => team.players.map(p => { const c = comparison(p, f, now, snapshot); return <tr key={`${teamIndex}-${p.id}`}><td><button type="button" aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}>{p.name}{p.penaltyActive ? " · PEN" : ""}<span className="ip-sub ip-block">{team.name} · {p.role || "Role pending"}</span></button></td><td>{c.fair === null ? <span className="ip-sub">{p.role === "GK" ? "GK unpriced" : "Data pending"}</span> : decimal(c.fair)}{p.pricingStatus === "limited_data" && <span className="ip-estimate ip-block">Estimate</span>}</td><td>{p.bookmakerOdds === null ? <span className="ip-sub">No odds</span> : decimal(p.bookmakerOdds)}{p.bookmakerOdds && !c.fresh ? <span className="ip-sub ip-block">Odds need rechecking</span> : null}</td><td><span className={`ip-verdict ${c.gap !== null && c.gap > 0 ? "ip-positive" : ""}`}>{priceVerdict(c.gap)}</span></td></tr>; }))}</tbody></table></div>}
    {player && metrics && <section id={detailId} className="ip-detail" role="region" aria-label={`${player.name} pricing detail`} aria-live="polite"><div><div className="ip-detail-head"><span className="ip-avatar"><Portrait player={player} /></span><div><h3>{player.name}</h3><span className="ip-sub">{player.role} · {f.lineupStatus === "confirmed" ? "Confirmed" : "Expected"} starter</span></div><button className="ip-close" type="button" aria-label="Close player details" onClick={() => setSelected(null)}>×</button></div><div className="ip-duty">{player.penaltyActive ? player.penaltyInheritedFrom ? `Expected to inherit penalties: ${player.penaltyInheritedFrom} is not starting.` : "Expected first-choice penalty taker in this XI." : "No first-choice penalty duty assigned."}</div></div><div><div className="ip-metrics">{[["Our fair odds", decimal(metrics.fair)], ["Bet365 odds", decimal(player.bookmakerOdds)]].map(([label, value]) => <div key={label}><div className="ip-label">{label}</div><div className="ip-number">{value}</div></div>)}</div><p className="ip-sub">{finite(player.modelProbability) ? `Our estimated chance of scoring: ${(100 * player.modelProbability).toFixed(1)}%` : player.pricingStatus === "goalkeeper_unpriced" ? "Goalkeeper pricing unavailable" : "Awaiting a complete model forecast"}{finite(player.expectedMinutes) ? ` · Expected minutes ${player.expectedMinutes.toFixed(0)}` : ""}</p>{metrics.gap !== null && <p className="ip-comparison-note"><strong>{priceVerdict(metrics.gap)}.</strong> {metrics.gap > 0 ? "Bet365 offers higher odds than our fair price — better value according to our model, not a guaranteed winner." : metrics.gap < 0 ? "Bet365 offers lower odds than our fair price." : "Bet365 matches our estimated fair price."} The bookmaker odds imply a {(100 / player.bookmakerOdds!).toFixed(1)}% chance of scoring.</p>}{player.pricingStatus === "limited_data" && <p className="ip-estimate">We have limited playing history for this player. We show an estimated price, but leave them out of the value shortlist.</p>}{player.bookmakerOdds === null && <p className="ip-sub">We haven’t received Bet365 odds for this player yet.</p>}<p className="ip-sub">Bet365 odds last checked: {stamp(player.priceCapturedAt)} UK<br />Our fair odds last updated: {stamp(player.modelGeneratedAt)} UK</p>{!metrics.fresh && player.bookmakerOdds !== null && !metrics.started && <p className="ip-estimate">These bookmaker odds need checking again. We’ll show a value comparison once updated odds arrive.</p>}{f.lineupStatus !== "confirmed" && <p className="ip-sub">The starting lineup is not confirmed. These fair odds assume {player.name} starts and may change when the team is announced.</p>}</div></section>}
  </details>;
}

export function DailyPitchBoard({ initial, boardUrl, asOf, preview = false, highlights }: { initial: DailyBoard; boardUrl: string; asOf: number; preview?: boolean; highlights?: ReactNode }) {
  const [board, setBoard] = useState(initial);
  const [now, setNow] = useState(asOf);
  const [date, setDate] = useState("upcoming");
  const [league, setLeague] = useState("all");
  const [view, setView] = useState("pitch");
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState<PlayerSelection | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  useEffect(() => {
    const followHash = () => {
      const id = window.location.hash.slice(1);
      if (["lab-signals", "lab-matches", "lab-hits", "lab-guide"].includes(id)) openSection(id);
    };
    followHash();
    window.addEventListener("hashchange", followHash);
    return () => window.removeEventListener("hashchange", followHash);
  }, []);
  useEffect(() => {
    let alive = true, busy = false, last = 0;
    const controller = new AbortController();
    async function refresh() {
      if (preview || busy || document.hidden || Date.now() - last < 240_000) return;
      busy = true; last = Date.now();
      try {
        const response = await fetch(boardUrl, { signal: controller.signal, cache: "default" });
        if (!response.ok) throw new Error("Snapshot unavailable");
        const data: unknown = await response.json();
        if (!isDailyBoard(data)) throw new Error("Invalid snapshot");
        if (alive) { setBoard(previous => Date.parse(data.generatedAt ?? "") >= Date.parse(previous.generatedAt ?? "1970-01-01") ? data : previous); setRefreshFailed(false); }
      } catch { if (alive) setRefreshFailed(true); } finally { busy = false; }
    }
    const tick = setInterval(() => setNow(Date.now()), 30_000);
    const poll = setInterval(refresh, 300_000);
    document.addEventListener("visibilitychange", refresh);
    void refresh();
    return () => { alive = false; controller.abort(); clearInterval(tick); clearInterval(poll); document.removeEventListener("visibilitychange", refresh); };
  }, [boardUrl, preview]);
  const today = day(now);
  const dates = [...new Set([...Array.from({ length: 4 }, (_, i) => day(now + i * 86400_000)), ...board.fixtures.map(f => f.date)])].sort();
  const leagues = [["epl", "Premier League"], ["serie-a", "Serie A"], ["la-liga", "La Liga"], ["bundesliga", "Bundesliga"], ["ligue-1", "Ligue 1"]];
  const inDate = (f: BoardFixture) => date === "upcoming" ? f.date >= today : f.date === date;
  const searchKey = (value: string) => value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const search = searchKey(query.trim());
  const fixtures = board.fixtures.filter(f => inDate(f) && (league === "all" || f.league === league) &&
    (!search || searchKey([f.competition, ...f.teams.flatMap(t => [t.name, ...t.players.map(p => p.name)])].join(" ")).includes(search)));
  const comparisons = fixtures.flatMap(f => f.teams.flatMap((team, side) => team.players.map(p => ({ f, team, side, p, c: comparison(p, f, now, board.generatedAt) }))));
  const shortlist = comparisons
    .filter(row => row.c.ev !== null && row.c.ev > 0 && row.team.lineupComplete && row.f.lineupStatus !== "pending")
    .sort((a, b) => (b.c.ev ?? 0) - (a.c.ev ?? 0));
  function choosePlayer(f: BoardFixture, side: number, p: BoardPlayer) {
    setSelection({fixtureId: f.id, side, id: p.id});
    openSection(`match-${f.id}`);
    // Wait for the selected detail panel to render, without a network request.
    setTimeout(() => document.getElementById(detailIdFor(f.id))?.scrollIntoView({block: "center"}), 0);
  }
  const groups = [...new Set(fixtures.map(f => f.league))].map(id => ({id, name: fixtures.find(f => f.league === id)!.competition, fixtures: fixtures.filter(f => f.league === id)}));
  const leagueName = leagues.find(([id]) => id === league)?.[1] ?? "All leagues";
  const nextFixture = board.fixtures.find(f => f.date > date && (league === "all" || f.league === league));
  const dateLabel = (d: string) => d === today ? "Today" : d === day(now + 86400_000) ? "Tomorrow" : new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Europe/London" }).format(new Date(d + "T12:00:00Z"));
  const old = !board.generatedAt || now - Date.parse(board.generatedAt) > 90 * 60_000;
  const upcoming = comparisons.filter(row => !row.c.started && row.p.role !== "GK");
  const missingOdds = upcoming.filter(row => row.p.bookmakerOdds === null).length;
  const staleOdds = upcoming.filter(row => row.p.bookmakerOdds !== null && !row.c.fresh).length;
  const checkedPlayers = upcoming.filter(row => row.c.ev !== null).length;
  return <div id="im-pitch-lab"><div className="ip-main"><PageHomeLink /><div className="ip-head"><div><div className="ip-eyebrow">INDEPENDENT GOALSCORER ANALYSIS</div><h1>Fair Odds <span>Lab</span></h1><p className="ip-sub">Explore the lineups. Compare our fair odds with Bet365. Open a player for the detail.</p></div><div className="ip-headlinks"><span className="ip-beta">Free beta</span><a href="#lab-hits">Latest hits ↗</a></div></div>
    <nav className="ip-section-nav" aria-label="Fair Odds Lab sections">{[["lab-signals", "Price comparisons"], ["lab-matches", "Matches & odds"], ["lab-hits", "Latest hits"], ["lab-guide", "How to read it"]].map(([id, label]) => <a key={id} href={`#${id}`} onClick={event => { event.preventDefault(); openSection(id); history.replaceState(null, "", `#${id}`); }}>{label}{id === "lab-signals" && <span>{shortlist.length}</span>}</a>)}</nav>
    {preview && <p role="status" className="ip-pennews">Design preview · illustrative prices, not current markets</p>}
    <nav className="ip-leagues" aria-label="Competition">
      {[["all", "All leagues"], ...leagues].map(([id, name]) => <button key={id} type="button" aria-pressed={league === id} onClick={() => setLeague(id)}>{id === "all" ? <span className="ip-all-icon" aria-hidden="true">◈</span> : <Image unoptimized src={`/league-logos/${id}.png`} width={26} height={26} alt="" />}<span>{name}</span><span className="ip-count">{board.fixtures.filter(f => inDate(f) && (id === "all" || f.league === id)).length}</span></button>)}
    </nav>
    <label className="ip-search"><span>Find a team or player</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search Adams, Napoli, Marseille…" /></label>
    <div className="ip-controls"><div className="ip-dates" aria-label="Match date"><button type="button" aria-pressed={date === "upcoming"} onClick={() => setDate("upcoming")}>Upcoming<span>All available</span></button>{dates.map(d => <button key={d} type="button" aria-pressed={date === d} onClick={() => setDate(d)}>{dateLabel(d)}<span>{board.fixtures.filter(f => f.date === d && (league === "all" || f.league === league)).length} matches</span></button>)}</div><div className="ip-switch" aria-label="Comparison view">{["pitch", "list"].map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{v === "pitch" ? "Pitch" : "List"}</button>)}</div></div>
    {highlights}
    <PlayerLabelGuide />
    {(old || refreshFailed) && <p className="ip-pennews" role="status">{old ? "The latest update is overdue. You can still browse the last prices, but they won’t appear in the value shortlist until checked again." : "We couldn’t load the latest update. Showing the last available prices."}</p>}
    <details id="lab-signals" className="ip-shortlist" aria-label="Price comparisons">
      <summary className="ip-shortlist-head"><div><span className="ip-eyebrow">BET365 · ANYTIME GOALSCORER</span><h2>Price comparisons</h2><p>Bet365 prices above our model estimate. A beta research shortlist, not recommended bets. Filter by league, date or player.</p></div><span className="ip-summary-actions"><span className="ip-shortlist-count">{shortlist.length} {shortlist.length === 1 ? "player" : "players"}</span><DisclosureCue /></span></summary>
      <div className="ip-signal-health" role="status"><span>{checkedPlayers} players with usable comparisons</span><span>{staleOdds} odds awaiting a fresh check</span><span>{missingOdds} players without Bet365 odds</span></div>
      {shortlist.length ? <><div className="ip-shortlist-grid">{shortlist.map(({f,team,side,p,c}) => <article className="ip-shortlist-card" key={`${f.id}-${side}-${p.id}`}>
        <span className={`ip-lineup-badge ${f.lineupStatus === "confirmed" ? "confirmed" : ""}`}>{f.lineupStatus === "confirmed" ? "Confirmed starter" : "Expected starter · check lineup"}</span>
        <div className="ip-shortlist-player"><Portrait player={p} /><div><h3>{p.name}</h3><span>{team.name}{p.penaltyActive ? " · Penalty taker" : ""}</span></div></div>
        <p className="ip-shortlist-match">{f.teams[0].name} vs {f.teams[1].name}<br />{f.competition} · {dateLabel(f.date)} · {stamp(f.kickoffUtc)} UK</p>
        <div className="ip-shortlist-prices"><div><span>Our fair odds</span><strong>{decimal(c.fair)}</strong></div><div><span>Bet365 odds</span><strong>{decimal(p.bookmakerOdds)}</strong></div></div>
        <p className="ip-shortlist-checked">Bet365 odds checked {stamp(p.priceCapturedAt)} UK</p>
        <button type="button" aria-controls={detailIdFor(f.id)} onClick={() => choosePlayer(f,side,p)}>Why {p.name}? <span aria-hidden="true">↗</span></button>
      </article>)}</div><p className="ip-shortlist-note">These are model-based comparisons, not guaranteed winners. Expected starters can change. Eligible comparisons recorded with confirmed lineups are tracked before kickoff; winning results can appear in Latest hits, including Super Sub wins.</p></> : <p className="ip-shortlist-empty">{!upcoming.length ? "No pre-match players in this view. Choose another date to see upcoming opportunities." : staleOdds > 0 || old ? "Waiting for refreshed Bet365 odds. Older prices remain visible in Matches & odds, but are not current comparisons. This does not mean there is no value." : checkedPlayers === 0 ? "We do not yet have enough usable prices and player data to check for value in this view." : "No positive comparisons in this view currently meet the data checks. Browse all player prices below, or change the date or league."}</p>}
    </details>
    <details id="lab-matches" className="ip-matches-panel"><summary className="ip-panel-summary"><span><strong>Matches &amp; odds</strong><small>Open a match to view both teams, lineups and prices</small></span><span className="ip-summary-actions"><span>{fixtures.length} matches</span><DisclosureCue /></span></summary>
    <div className="ip-resultshead"><div><span className="ip-eyebrow">{leagueName}</span><h2>{date === "upcoming" ? "Upcoming matches" : dateLabel(date)}</h2></div><span className="ip-sub" aria-live="polite">{fixtures.length} matches · {fixtures.filter(f => f.lineupStatus === "confirmed").length} confirmed XIs</span></div>
    {fixtures.length ? groups.map(group => <section className="ip-league-group" key={group.id} aria-label={group.name}><header className="ip-grouphead"><h2>{group.name}</h2><span>{group.fixtures.length} {group.fixtures.length === 1 ? "match" : "matches"}</span></header>{group.fixtures.map(f => <MatchPitch key={f.id} fixture={f} now={now} snapshot={board.generatedAt} view={view} selected={selection?.fixtureId === f.id ? selection : null} setSelected={value => setSelection(value ? {...value, fixtureId: f.id} : null)} />)}</section>) : <section className="ip-empty"><div className="ip-empty-pitch" aria-hidden="true"><span /><i /></div><div><span className="ip-eyebrow">{leagueName} · {date === "upcoming" ? "Upcoming" : dateLabel(date)}</span><h2>{search ? "No matching team or player" : date === "upcoming" ? "Waiting for the next lineups" : "No lineups available for this date"}</h2><p>Scheduled matches and expected XIs appear as our feed supplies them. Official lineups update the player prices and penalty duties.</p><div className="ip-empty-actions">{query && <button type="button" onClick={() => setQuery("")}>Clear search</button>}{date !== "upcoming" && <button type="button" onClick={() => setDate(nextFixture?.date ?? "upcoming")}>{nextFixture ? `Next available · ${dateLabel(nextFixture.date)}` : "Browse upcoming matches"} →</button>}{league !== "all" && <button type="button" onClick={() => setLeague("all")}>Show all leagues</button>}<a href="#lab-hits">Explore the latest hits ↗</a></div><p className="ip-sub">Current collection window: today + 3 days. Missing lineups do not mean no fixtures are scheduled.</p></div></section>}
    </details>
    <p className="ip-footnote">Fair odds are model estimates. Expected lineups and penalty duties may change. A player scoring and a qualifying replacement scoring are different outcomes; promotion coverage is not included in the named-player probability.</p>
  </div></div>;
}
