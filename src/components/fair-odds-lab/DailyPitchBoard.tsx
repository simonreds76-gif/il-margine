"use client";

import Image from "next/image";
import { useEffect, useState, type CSSProperties } from "react";
import "./daily-pitch.css";

import { isDailyBoard, type BoardPlayer, type BoardFixture, type DailyBoard } from "./daily-board-data";
const finite = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);
const decimal = (n: unknown) => finite(n) ? n.toFixed(2) : "—";
const signed = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(1)}`;
const stamp = (s: string | null) => s && Number.isFinite(Date.parse(s)) ? new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/London", hour: "2-digit", minute: "2-digit" }).format(new Date(s)) : "Pending";
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
  const comparable = !!(pModel && odds && fresh && !started);
  return { started, fresh, fair: pModel ? 1 / pModel : null, gap: comparable ? 100 * (pModel! - 1 / odds!) : null, ev: comparable ? 100 * (pModel! * odds! - 1) : null };
}

function MatchPitch({ fixture: f, now, snapshot, view }: { fixture: BoardFixture; now: number; snapshot: string | null; view: string }) {
  const [side, setSide] = useState(0);
  const [selected, setSelected] = useState<{ side: number; id: string } | null>(null);
  const player = selected ? f.teams[selected.side]?.players.find(p => p.id === selected.id) : null;
  const metrics = player ? comparison(player, f, now, snapshot) : null;
  const detailId = `player-detail-${f.id.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const started = now >= Date.parse(f.kickoffUtc);
  return <article className="ip-match" aria-label={`${f.teams[0].name} versus ${f.teams[1].name}`}>
    <div className="ip-matchhead"><div><div className="ip-label">{f.competition} · {stamp(f.kickoffUtc)} UK</div><h2 className="ip-fixturetitle">{f.teams[0].name} <span className="ip-sub">vs</span> {f.teams[1].name}</h2><div className="ip-sub">{started ? "Kickoff passed · pre-match snapshot" : f.lineupStatus === "confirmed" ? "Official starting XIs" : f.lineupStatus === "pending" ? "Starting lineups pending" : "Expected XIs · provisional"} · Lineup checked {stamp(f.lineupObservedAt)}</div></div></div>
    {f.teams.filter(t => t.penaltyInheritedFrom && t.activePenaltyTaker).map(t => <div className="ip-pennews" key={t.name}><strong>Expected penalty duty</strong><span>{t.penaltyInheritedFrom} not starting → {t.activePenaltyTaker}</span></div>)}
    {view === "pitch" && <div className="ip-switch ip-teamtabs" aria-label="Team">{f.teams.map((t, i) => <button key={t.name} type="button" aria-pressed={side === i} onClick={() => setSide(i)}>{t.name}</button>)}</div>}
    {view === "pitch" ? <div className="ip-board">{f.teams.map((team, teamIndex) => {
      const validLines = team.players.every(p => Number.isInteger(p.lineIndex)) && team.players.filter(p => p.lineIndex === -1).length === 1 && !!team.formation;
      const lines = validLines ? [...new Set(team.players.map(p => p.lineIndex!))].sort((a, b) => b - a).map(line => team.players.filter(p => p.lineIndex === line)) : [team.players];
      return <section key={team.name} className={`ip-club ${side === teamIndex ? "ip-active" : ""}`} style={{ "--ip-kit": team.primaryColor?.match(/^#[0-9a-f]{6}$/i) ? team.primaryColor : teamIndex ? "#efc2d1" : "#c6e7ff", "--ip-kit-ink": "#ffffff" } as CSSProperties}>
        <div className="ip-clubhead"><span className="ip-clubname">{team.logoPath?.startsWith("/team-logos/") ? <Image src={team.logoPath} alt="" width={30} height={34} unoptimized /> : <span className="ip-crest" aria-hidden="true">{team.name.slice(0, 1)}</span>}{team.name}</span><span className="ip-sub">{validLines ? team.formation : "Positions pending"}</span></div>
        {!team.lineupComplete && <p className="ip-bench">Lineup incomplete · {team.players.length}/11 players supplied</p>}
        <div className={`ip-field ${validLines ? "" : "ip-ungrouped"}`}><div className="ip-lines" aria-hidden="true"><div className="ip-center" /><div className="ip-area top" /><div className="ip-area bottom" /></div>
          {lines.map((line, i) => <div key={i} className="ip-row">{line.map(p => { const c = comparison(p, f, now, snapshot); return <button key={p.id} type="button" className="ip-player" aria-label={`${p.name}, model fair ${decimal(c.fair)}, Bet365 ${decimal(p.bookmakerOdds)}${!c.fresh ? ", quote missing or stale" : ""}`} aria-pressed={selected?.side === teamIndex && selected.id === p.id} aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}><Portrait player={p} />{p.penaltyActive && <span className="ip-pen">PEN</span>}<span className="ip-name">{p.name}</span><span className={`ip-price ${!c.fresh ? "ip-aged" : ""}`}><span>{decimal(c.fair)}</span><span className="ip-book">{decimal(p.bookmakerOdds)}</span></span><span className={`ip-gap ${c.gap !== null && c.gap < 0 ? "minus" : ""}`}>{c.gap === null ? started ? "Locked" : p.bookmakerOdds && !c.fresh ? "Old quote" : "—" : `${signed(c.gap)} pp`}</span></button>; })}</div>)}
        </div><details className="ip-bench"><summary>Bench · {team.substitutes.length} players</summary><p>{team.substitutes.join(" · ") || "Substitutes not supplied"}</p></details>
      </section>;
    })}</div> : <div className="ip-list"><table><thead><tr><th>Player</th><th>Fair</th><th>Bet365</th><th>Δ pp</th></tr></thead><tbody>{f.teams.flatMap((team, teamIndex) => team.players.map(p => { const c = comparison(p, f, now, snapshot); return <tr key={`${teamIndex}-${p.id}`}><td><button type="button" aria-controls={detailId} onClick={() => setSelected({ side: teamIndex, id: p.id })}>{p.name}{p.penaltyActive ? " · PEN" : ""}<span className="ip-sub ip-block">{team.name} · {p.role || "Role pending"}</span></button></td><td>{decimal(c.fair)}</td><td>{decimal(p.bookmakerOdds)}{p.bookmakerOdds && !c.fresh ? <span className="ip-sub ip-block">Old quote</span> : null}</td><td>{c.gap === null ? "—" : signed(c.gap)}</td></tr>; }))}</tbody></table></div>}
    {player && metrics && <section id={detailId} className="ip-detail" role="region" aria-label={`${player.name} pricing detail`} aria-live="polite"><div><div className="ip-detail-head"><span className="ip-avatar">{player.number ?? player.name.slice(0, 1)}</span><div><h3>{player.name}</h3><span className="ip-sub">{player.role} · {f.lineupStatus === "confirmed" ? "Confirmed" : "Expected"} starter</span></div><button className="ip-close" type="button" aria-label="Close player details" onClick={() => setSelected(null)}>×</button></div><div className="ip-duty">{player.penaltyActive ? player.penaltyInheritedFrom ? `Expected to inherit penalties: ${player.penaltyInheritedFrom} is not starting.` : "Expected first-choice penalty taker in this XI." : "No first-choice penalty duty assigned."}</div></div><div><div className="ip-metrics">{[["Model fair", decimal(metrics.fair)], ["Bet365", decimal(player.bookmakerOdds)], ["Gap · pp", metrics.gap === null ? "—" : signed(metrics.gap)]].map(([label, value]) => <div key={label}><div className="ip-label">{label}</div><div className="ip-number">{value}</div></div>)}</div><p className="ip-sub">{finite(player.modelProbability) ? `Model ${(100 * player.modelProbability).toFixed(1)}%` : player.pricingStatus === "goalkeeper_unpriced" ? "Goalkeeper pricing unavailable" : "Awaiting a complete model forecast"}{finite(player.expectedMinutes) ? ` · Expected minutes ${player.expectedMinutes.toFixed(0)}` : ""}{metrics.ev !== null ? ` · Model EV ${signed(metrics.ev)}%` : ""}</p><p className="ip-sub">Quote {stamp(player.priceCapturedAt)} · Model {stamp(player.modelGeneratedAt)}{!metrics.fresh ? " · Fresh comparison pending" : ""}</p>{f.lineupStatus === "expected" && <p className="ip-sub">Provisional estimate assuming this player starts.</p>}</div></section>}
  </article>;
}

export function DailyPitchBoard({ initial, boardUrl, asOf, preview = false }: { initial: DailyBoard; boardUrl: string; asOf: number; preview?: boolean }) {
  const [board, setBoard] = useState(initial);
  const [now, setNow] = useState(asOf);
  const [date, setDate] = useState(day(asOf));
  const [league, setLeague] = useState("all");
  const [view, setView] = useState("pitch");
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
  const dates = [...new Set([day(now), ...board.fixtures.map(f => f.date)])].sort();
  const fixtures = board.fixtures.filter(f => f.date === date && (league === "all" || f.league === league));
  const old = !board.generatedAt || now - Date.parse(board.generatedAt) > 90 * 60_000;
  return <div id="im-pitch-lab"><div className="ip-main"><div className="ip-head"><div><h1>Fair Odds Lab</h1><p className="ip-sub">Every starter. Model fair odds. Bet365 comparison.</p></div><span className="ip-beta">Free beta</span></div>
    {preview && <p role="status" className="ip-pennews">Design preview · illustrative prices, not current markets</p>}
    <div className="ip-controls"><label>Date <select value={date} onChange={e => setDate(e.target.value)}>{dates.map(d => <option key={d} value={d}>{d === day(now) ? "Today" : d}</option>)}</select></label><label>Competition <select value={league} onChange={e => setLeague(e.target.value)}><option value="all">All supported leagues</option>{[...new Map(board.fixtures.map(f => [f.league, f.competition])).entries()].map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><div className="ip-switch" aria-label="Comparison view">{["pitch", "list"].map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>{v === "pitch" ? "Pitch" : "List"}</button>)}</div></div>
    <div className="ip-legend"><span>Prices: Fair / Bet365</span><span>Δ pp = model chance − bookmaker implied chance</span><span>PEN = expected active taker</span><span>All times UK · Snapshot {stamp(board.generatedAt)}</span></div>
    {(old || refreshFailed) && <p className="ip-pennews" role="status">{old ? "Awaiting a current snapshot. Old quotes are not treated as fresh comparisons." : "Latest refresh failed. Showing the last received snapshot."}</p>}
    {fixtures.length ? fixtures.map(f => <MatchPitch key={f.id} fixture={f} now={now} snapshot={board.generatedAt} view={view} />) : <section className="ip-empty"><h2>No match lineups available for this date</h2><p>Expected and official XIs appear as the feed supplies them. An empty board does not mean that every scheduled match has been checked.</p><p className="ip-sub">Coverage: Premier League, Serie A, La Liga, Bundesliga and Ligue 1.</p></section>}
    <p className="ip-footnote">Fair odds are model estimates. Expected lineups and penalty duties may change. A player scoring and a qualifying replacement scoring are different outcomes; promotion coverage is not included in the named-player probability.</p>
  </div></div>;
}
