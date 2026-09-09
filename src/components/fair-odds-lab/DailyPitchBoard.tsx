"use client";

import Image from "next/image";
import { useEffect, useState, type CSSProperties } from "react";
import "./daily-pitch.css";

import { isDailyBoard, type BoardPlayer, type BoardFixture, type DailyBoard } from "./daily-board-data";
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const decimal = (n: unknown) => finite(n) ? (n >= 100 ? n.toFixed(1) : n.toFixed(2)) : "—";
const priceVerdict = (gap: number | null) => gap === null ? "Not compared" : gap > 0 ? "Better price" : gap < 0 ? "Below fair" : "Matches fair";
const stamp = (s: string | null) => s && Number.isFinite(Date.parse(s)) ? new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" }).format(new Date(s)) : "Not available";
const day = (n: number) => new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(n));

function Portrait({ player }: { player: BoardPlayer }) {
  const [failed, setFailed] = useState(false);
  const photo = player.photoUrl?.match(/^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/);
  return photo && !failed ? <Image unoptimized src={player.photoUrl!} alt="" width={42} height={42} className="ip-photo" onError={() => setFailed(true)} /> : <span className="ip-shirt" aria-hidden="true">{player.number ?? ""}</span>;
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
  return <article className="ip-match" aria-label={`${f.teams[0].name} versus ${f.teams[1].name}`}>
    <div className="ip-matchhead"><div><div className="ip-label">{f.competition} · {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" }).format(new Date(f.kickoffUtc))} · {stamp(f.kickoffUtc)} UK</div><h2 className="ip-fixturetitle">{f.teams[0].name} <span className="ip-sub">vs</span> {f.teams[1].name}</h2><div className="ip-sub">{started ? "Kickoff passed · pre-match snapshot" : f.lineupStatus === "confirmed" ? "Starting lineup confirmed" : f.lineupStatus === "pending" ? "Starting lineups pending" : "Predicted starting lineup · not confirmed"} · Lineup checked {stamp(f.lineupObservedAt)}</div></div></div>
    <div className="ip-coverage">{f.teams.map(team => <span key={team.name}><strong>{team.name}</strong> · Fair {team.players.filter(p => p.modelProbability !== null).length}/{team.players.filter(p => p.role !== "GK").length} outfield · Bet365 {team.players.filter(p => p.bookmakerOdds !== null).length}/{team.players.length}</span>)}</div>
    {f.teams.filter(t => t.penaltyInheritedFrom && t.activePenaltyTaker).map(t => <div className="ip-pennews" key={t.name}><strong>Expected penalty duty</strong><span>{t.penaltyInheritedFrom} not starting → {t.activePenaltyTaker}</span></div>)}
    {view === "pitch" && <div className="ip-switch ip-teamtabs" aria-label="Team">{f.teams.map((t, i) => <button key={t.name} type="button" aria-pressed={side === i} onClick={() => setSide(i)}>{t.name}</button>)}</div>}
    {view === "pitch" ? <div className="ip-board">{f.teams.map((team, teamIndex) => {
      const validLines = team.players.every(p => Number.isInteger(p.lineIndex)) && team.players.filter(p => p.lineIndex === -1).length === 1 && !!team.formation;
      const lines = validLines ? [...new Set(team.players.map(p => p.lineIndex!))].sort((a, b) => b - a).map(line => team.players.filter(p => p.lineIndex === line)) : [team.players];
      return <section key={team.name} className={`ip-club ${side === teamIndex ? "ip-active" : ""}`} style={{ "--ip-kit": team.primaryColor?.match(/^#[0-9a-f]{6}$/i) ? team.primaryColor : teamIndex ? "#efc2d1" : "#c6e7ff", "--ip-kit-ink": "#ffffff" } as CSSProperties}>
        <div className="ip-clubhead"><span className="ip-clubname">{team.logoPath?.startsWith("/team-logos/") ? <Image src={team.logoPath} alt="" width={30} height={34} unoptimized /> : <span className="ip-crest" aria-hidden="true">{team.name.slice(0, 1)}</span>}{team.name}</span><span className="ip-sub">{validLines ? team.formation : "Positions pending"}</span></div>
        {!team.lineupComplete && <p className="ip-bench">Lineup incomplete · {team.players.length}/11 players supplied</p>}
        <div className={`ip-field ${validLines ? "" : "ip-ungrouped"}`}><div className="ip-lines" aria-hidden="true"><div className="ip-center" /><div className="ip-area top" /><div className="ip-area bottom" /></div>
          {lines.map((line, i) => <div key={i} className="ip-row">{line.map(p => { const c = comparison(p, f, now, snapshot); return <button key={p.id} type="button" className="ip-player" aria-label={`${p.name}, our fair odds ${decimal(c.fair)}, Bet365 odds ${decimal(p.bookmakerOdds)}${!c.fresh ? ", bookmaker odds unavailable or awaiting an update" : ""}`} aria-pressed={selected?.side === teamIndex && selected.id === p.id} aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}><Portrait player={p} />{p.penaltyActive && <span className="ip-pen">PEN</span>}<span className="ip-name">{p.name}</span><span className={`ip-price ${!c.fresh ? "ip-aged" : ""}`}><span className="ip-fair" title={p.pricingStatus === "limited_data" ? "Estimate based on limited player history." : "Our estimated fair odds"}><span className="ip-price-label">Our fair odds</span><strong>{c.fair === null ? "Unpriced" : decimal(c.fair)}{p.pricingStatus === "limited_data" ? "*" : ""}</strong></span><span className="ip-book" title={p.bookmakerOdds === null ? "We haven’t received Bet365 odds for this player yet." : "Bet365 decimal odds"}><span className="ip-price-label">Bet365</span><strong>{p.bookmakerOdds === null ? "No odds" : decimal(p.bookmakerOdds)}</strong></span></span><span className={`ip-gap ${c.gap !== null && c.gap < 0 ? "minus" : ""}`}>{c.gap === null ? p.pricingStatus === "limited_data" ? "Estimate*" : started ? "Match started" : p.bookmakerOdds && !c.fresh ? "Update due" : "Not compared" : priceVerdict(c.gap)}</span></button>; })}</div>)}
        </div><details className="ip-bench"><summary>Bench · {team.substitutes.length} players</summary><p>{team.substitutes.join(" · ") || "Substitutes not supplied"}</p></details>
      </section>;
    })}</div> : <div className="ip-list"><table><thead><tr><th>Player</th><th>Our fair odds</th><th>Bet365 odds</th><th>Price check</th></tr></thead><tbody>{f.teams.flatMap((team, teamIndex) => team.players.map(p => { const c = comparison(p, f, now, snapshot); return <tr key={`${teamIndex}-${p.id}`}><td><button type="button" aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}>{p.name}{p.penaltyActive ? " · PEN" : ""}<span className="ip-sub ip-block">{team.name} · {p.role || "Role pending"}</span></button></td><td>{c.fair === null ? <span className="ip-sub">{p.role === "GK" ? "GK unpriced" : "Data pending"}</span> : decimal(c.fair)}{p.pricingStatus === "limited_data" && <span className="ip-estimate ip-block">Estimate</span>}</td><td>{p.bookmakerOdds === null ? <span className="ip-sub">No odds</span> : decimal(p.bookmakerOdds)}{p.bookmakerOdds && !c.fresh ? <span className="ip-sub ip-block">Update due</span> : null}</td><td><span className={`ip-verdict ${c.gap !== null && c.gap > 0 ? "ip-positive" : ""}`}>{priceVerdict(c.gap)}</span></td></tr>; }))}</tbody></table></div>}
    {player && metrics && <section id={detailId} className="ip-detail" role="region" aria-label={`${player.name} pricing detail`} aria-live="polite"><div><div className="ip-detail-head"><span className="ip-avatar">{player.number ?? player.name.slice(0, 1)}</span><div><h3>{player.name}</h3><span className="ip-sub">{player.role} · {f.lineupStatus === "confirmed" ? "Confirmed" : "Expected"} starter</span></div><button className="ip-close" type="button" aria-label="Close player details" onClick={() => setSelected(null)}>×</button></div><div className="ip-duty">{player.penaltyActive ? player.penaltyInheritedFrom ? `Expected to inherit penalties: ${player.penaltyInheritedFrom} is not starting.` : "Expected first-choice penalty taker in this XI." : "No first-choice penalty duty assigned."}</div></div><div><div className="ip-metrics">{[["Our fair odds", decimal(metrics.fair)], ["Bet365 odds", decimal(player.bookmakerOdds)]].map(([label, value]) => <div key={label}><div className="ip-label">{label}</div><div className="ip-number">{value}</div></div>)}</div><p className="ip-sub">{finite(player.modelProbability) ? `Our estimated chance of scoring: ${(100 * player.modelProbability).toFixed(1)}%` : player.pricingStatus === "goalkeeper_unpriced" ? "Goalkeeper pricing unavailable" : "Awaiting a complete model forecast"}{finite(player.expectedMinutes) ? ` · Expected minutes ${player.expectedMinutes.toFixed(0)}` : ""}</p>{metrics.gap !== null && <p className="ip-comparison-note"><strong>{priceVerdict(metrics.gap)}.</strong> {metrics.gap > 0 ? "Bet365 offers higher odds than our fair price — better value according to our model, not a guaranteed winner." : metrics.gap < 0 ? "Bet365 offers lower odds than our fair price." : "Bet365 matches our estimated fair price."} The bookmaker odds imply a {(100 / player.bookmakerOdds!).toFixed(1)}% chance of scoring.</p>}{player.pricingStatus === "limited_data" && <p className="ip-estimate">We have limited playing history for this player. We show an estimated price, but leave them out of the value shortlist.</p>}{player.bookmakerOdds === null && <p className="ip-sub">We haven’t received Bet365 odds for this player yet.</p>}<p className="ip-sub">Bet365 odds last checked: {stamp(player.priceCapturedAt)} UK<br />Our fair odds last updated: {stamp(player.modelGeneratedAt)} UK</p>{!metrics.fresh && player.bookmakerOdds !== null && !metrics.started && <p className="ip-estimate">These bookmaker odds need checking again. We’ll show a value comparison once updated odds arrive.</p>}{f.lineupStatus !== "confirmed" && <p className="ip-sub">The starting lineup is not confirmed. These fair odds assume {player.name} starts and may change when the team is announced.</p>}</div></section>}
  </article>;
}

export function DailyPitchBoard({ initial, boardUrl, asOf, preview = false }: { initial: DailyBoard; boardUrl: string; asOf: number; preview?: boolean }) {
  const [board, setBoard] = useState(initial);
  const [now, setNow] = useState(asOf);
  const [date, setDate] = useState("upcoming");
  const [league, setLeague] = useState("all");
  const [view, setView] = useState("pitch");
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState<PlayerSelection | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
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
  const shortlist = fixtures.flatMap(f => f.teams.flatMap((team, side) => team.players.map(p => ({ f, team, side, p, c: comparison(p, f, now, board.generatedAt) }))))
    .filter(row => row.c.ev !== null && row.c.ev > 0 && row.team.lineupComplete && row.f.lineupStatus !== "pending")
    .sort((a, b) => (b.c.ev ?? 0) - (a.c.ev ?? 0));
  function choosePlayer(f: BoardFixture, side: number, p: BoardPlayer) {
    setSelection({fixtureId: f.id, side, id: p.id});
    // Wait for the selected detail panel to render, without a network request.
    setTimeout(() => document.getElementById(detailIdFor(f.id))?.scrollIntoView({block: "center"}), 0);
  }
  const groups = [...new Set(fixtures.map(f => f.league))].map(id => ({id, name: fixtures.find(f => f.league === id)!.competition, fixtures: fixtures.filter(f => f.league === id)}));
  const leagueName = leagues.find(([id]) => id === league)?.[1] ?? "All leagues";
  const nextFixture = board.fixtures.find(f => f.date > date && (league === "all" || f.league === league));
  const dateLabel = (d: string) => d === today ? "Today" : d === day(now + 86400_000) ? "Tomorrow" : new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "Europe/London" }).format(new Date(d + "T12:00:00Z"));
  const old = !board.generatedAt || now - Date.parse(board.generatedAt) > 90 * 60_000;
  return <div id="im-pitch-lab"><div className="ip-main"><div className="ip-head"><div><div className="ip-eyebrow">THE GOALSCORER WORKBENCH</div><h1>Fair Odds <span>Lab</span></h1><p className="ip-sub">Read the XI. Compare the price. Find your edge.</p></div><div className="ip-headlinks"><span className="ip-beta">Free beta</span><a href="#lab-hits">Latest hits ↗</a></div></div>
    {preview && <p role="status" className="ip-pennews">Design preview · illustrative prices, not current markets</p>}
    <nav className="ip-leagues" aria-label="Competition">
      {[["all", "All leagues"], ...leagues].map(([id, name]) => <button key={id} type="button" aria-pressed={league === id} onClick={() => setLeague(id)}>{id === "all" ? <span className="ip-all-icon" aria-hidden="true">◈</span> : <Image unoptimized src={`/league-logos/${id}.png`} width={26} height={26} alt="" />}<span>{name}</span><span className="ip-count">{board.fixtures.filter(f => inDate(f) && (id === "all" || f.league === id)).length}</span></button>)}
    </nav>
    <label className="ip-search"><span>Find a team or player</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search Adams, Napoli, Marseille…" /></label>
    <div className="ip-controls"><div className="ip-dates" aria-label="Match date"><button type="button" aria-pressed={date === "upcoming"} onClick={() => setDate("upcoming")}>Upcoming<span>All available</span></button>{dates.map(d => <button key={d} type="button" aria-pressed={date === d} onClick={() => setDate(d)}>{dateLabel(d)}<span>{board.fixtures.filter(f => f.date === d && (league === "all" || f.league === league)).length} matches</span></button>)}</div><div className="ip-switch" aria-label="Comparison view">{["pitch", "list"].map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{v === "pitch" ? "Pitch" : "List"}</button>)}</div></div>
    <div className="ip-resultshead"><div><span className="ip-eyebrow">{leagueName}</span><h2>{date === "upcoming" ? "Upcoming matches" : dateLabel(date)}</h2></div><span className="ip-sub" aria-live="polite">{fixtures.length} matches · {fixtures.filter(f => f.lineupStatus === "confirmed").length} confirmed XIs</span></div>
    <div className="ip-price-guide"><div><span className="ip-guide-label">Our fair odds</span><p>The price our model estimates for this player to score.</p></div><div><span className="ip-guide-label ip-guide-book">Bet365</span><p>The bookmaker’s offered odds for the same player.</p></div><div><span className="ip-guide-label ip-guide-value">Better price</span><p>Bet365 odds are higher than our fair odds. That suggests value according to our model.</p></div></div><div className="ip-legend"><span>Decimal odds include your stake: 3.00 returns £3 per £1 if the bet wins.</span><span>* Estimate = limited player history; no value comparison</span><span>PEN = expected penalty taker · Goalkeepers unpriced</span><span>Tap a player for details · All times UK · Updated {stamp(board.generatedAt)}</span></div>
    {(old || refreshFailed) && <p className="ip-pennews" role="status">{old ? "The latest update is overdue. You can still browse the last prices, but they won’t appear in the value shortlist until checked again." : "We couldn’t load the latest update. Showing the last available prices."}</p>}
    <section className="ip-shortlist" aria-label="Value shortlist">
      <header className="ip-shortlist-head"><div><span className="ip-eyebrow">BET365 · ANYTIME GOALSCORER</span><h2>Value shortlist</h2><p>All recently checked Bet365 prices above our fair odds, together in one place. Matches your league, date and search filters.</p></div><span className="ip-shortlist-count">{shortlist.length} {shortlist.length === 1 ? "player" : "players"}</span></header>
      {shortlist.length ? <><div className="ip-shortlist-grid">{shortlist.map(({f,team,side,p,c}) => <article className="ip-shortlist-card" key={`${f.id}-${side}-${p.id}`}>
        <span className={`ip-lineup-badge ${f.lineupStatus === "confirmed" ? "confirmed" : ""}`}>{f.lineupStatus === "confirmed" ? "Confirmed starter" : "Expected starter · check lineup"}</span>
        <div className="ip-shortlist-player"><Portrait player={p} /><div><h3>{p.name}</h3><span>{team.name}{p.penaltyActive ? " · Penalty taker" : ""}</span></div></div>
        <p className="ip-shortlist-match">{f.teams[0].name} vs {f.teams[1].name}<br />{f.competition} · {dateLabel(f.date)} · {stamp(f.kickoffUtc)} UK</p>
        <div className="ip-shortlist-prices"><div><span>Our fair odds</span><strong>{decimal(c.fair)}</strong></div><div><span>Bet365 odds</span><strong>{decimal(p.bookmakerOdds)}</strong></div></div>
        <p className="ip-shortlist-checked">Bet365 odds checked {stamp(p.priceCapturedAt)} UK</p>
        <button type="button" aria-controls={detailIdFor(f.id)} onClick={() => choosePlayer(f,side,p)}>Why {p.name}? <span aria-hidden="true">↗</span></button>
      </article>)}</div><p className="ip-shortlist-note">These are model-based comparisons, not guaranteed winners. Expected starters can change. Eligible comparisons recorded with confirmed lineups are tracked before kickoff; winning results can appear in Latest hits, including Super Sub wins.</p></> : <p className="ip-shortlist-empty">{old ? "Waiting for updated Bet365 odds before showing a value shortlist." : "No players currently qualify for these filters. We only list recently checked odds above our fair price, with enough player data and a complete predicted or confirmed lineup."} Browse the pitches below to see all available prices.</p>}
    </section>
    {fixtures.length ? groups.map(group => <section className="ip-league-group" key={group.id} aria-label={group.name}><header className="ip-grouphead"><h2>{group.name}</h2><span>{group.fixtures.length} {group.fixtures.length === 1 ? "match" : "matches"}</span></header>{group.fixtures.map(f => <MatchPitch key={f.id} fixture={f} now={now} snapshot={board.generatedAt} view={view} selected={selection?.fixtureId === f.id ? selection : null} setSelected={value => setSelection(value ? {...value, fixtureId: f.id} : null)} />)}</section>) : <section className="ip-empty"><div className="ip-empty-pitch" aria-hidden="true"><span /><i /></div><div><span className="ip-eyebrow">{leagueName} · {date === "upcoming" ? "Upcoming" : dateLabel(date)}</span><h2>{search ? "No matching team or player" : date === "upcoming" ? "Waiting for the next lineups" : "No lineups available for this date"}</h2><p>Scheduled matches and expected XIs appear as our feed supplies them. Official lineups update the player prices and penalty duties.</p><div className="ip-empty-actions">{query && <button type="button" onClick={() => setQuery("")}>Clear search</button>}{date !== "upcoming" && <button type="button" onClick={() => setDate(nextFixture?.date ?? "upcoming")}>{nextFixture ? `Next available · ${dateLabel(nextFixture.date)}` : "Browse upcoming matches"} →</button>}{league !== "all" && <button type="button" onClick={() => setLeague("all")}>Show all leagues</button>}<a href="#lab-hits">Explore the latest hits ↗</a></div><p className="ip-sub">Current collection window: today + 3 days. Missing lineups do not mean no fixtures are scheduled.</p></div></section>}
    <p className="ip-footnote">Fair odds are model estimates. Expected lineups and penalty duties may change. A player scoring and a qualifying replacement scoring are different outcomes; promotion coverage is not included in the named-player probability.</p>
  </div></div>;
}
