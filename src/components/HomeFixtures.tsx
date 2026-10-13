'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import ToolEmblem from './ToolEmblem';
import { londonDay, upcomingHomeFixtures, type HomeFixture, type HomeHistory, type HomeFixturesData } from '@/lib/home-fixtures';
import './home-fixtures.css';

function Portrait({ src, person = false }: { src: string | null; person?: boolean }) {
  const [failed, setFailed] = useState(false);
  return <span className={`hf-portrait ${person ? 'hf-person' : ''}`}>{src && !failed ? <Image src={src} width={48} height={48} alt="" unoptimized onError={() => setFailed(true)} /> : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={person ? 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8M4 22v-4c0-6 16-6 16 0v4' : 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6z'} /></svg>}</span>;
}
function Record({ history, names }: { history: HomeHistory; names: string[] }) {
  if (history.meetings === null || !history.results) return <span className="hf-no-history">History not yet matched</span>;
  if (history.meetings === 0) return <span className="hf-no-history">No meetings in our archive</span>;
  const label = history.results.length === 3 ? `${names[0]} ${history.results[0]} wins, ${history.results[1]} draws, ${names[1]} ${history.results[2]} wins` : `${names[0]} ${history.results[0]} wins, ${names[1]} ${history.results[1]} wins`;
  return <span className="hf-record"><span className="hf-score" aria-label={label}>{history.results.map((n, i) => <span key={i}>{i > 0 && <i aria-hidden="true">:</i>}{n}</span>)}</span><span>{history.meetings} recorded meetings{history.results.length === 3 ? ' · wins / draws / wins' : ''}</span></span>;
}
function Fixture({ fixture: f, tennis, now }: { fixture: HomeFixture; tennis: boolean; now: number }) {
  const date = new Date(f.start);
  const day = londonDay(f.start) === londonDay(now) ? 'Today' : new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'short', day: 'numeric', month: 'short' }).format(date);
  const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit' }).format(date);
  return <article className={`hf-card ${tennis ? "hf-tennis" : ""}`}>
    <div className="hf-meta"><span>{f.competition}</span><time dateTime={f.start}>{day} · {time}</time></div>
    <div className="hf-opponents">{f.sides.map((s, i) => <div className="hf-side" key={`${f.id}-${i}`}><Portrait key={s.image} src={s.image} person={tennis} /><h4>{s.name}</h4></div>)}<span className="hf-versus" aria-hidden="true">vs</span></div>
    <div className="hf-history"><span className="hf-kicker">{tennis ? 'Player' : 'Club'} head to head</span><Record history={f.history} names={f.sides.map(s => s.name)} /></div>
    {f.managers && <div className="hf-managers"><span className="hf-kicker">Manager head to head</span><div className="hf-manager-names">{f.managers.sides.map((s, i) => <span key={i}><Portrait key={s.image} src={s.image} person /><span>{s.name}</span></span>)}</div><Record history={f.managers.history} names={f.managers.sides.map(s => s.name)} /></div>}
    <div className="hf-actions"><Link prefetch={false} href={f.href ?? '/tennis-matchday'} aria-label={`${tennis ? 'Compare' : 'Club history for'} ${f.sides.map(s => s.name).join(' and ')}`}><ToolEmblem name={tennis ? 'matchup' : 'football'} />{tennis ? f.href ? 'Compare players' : 'View tennis fixtures' : 'Club history'}<span aria-hidden="true">↗</span></Link>{f.managers && <Link prefetch={false} href={f.managers.href} aria-label={`Manager history for ${f.sides.map(s => s.name).join(' and ')}`}><ToolEmblem name="managers" />Manager history<span aria-hidden="true">↗</span></Link>}</div>
  </article>;
}
export default function HomeFixtures() {
  const [data, setData] = useState<HomeFixturesData | null>(null);
  const [failed, setFailed] = useState(false);
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const initial = setTimeout(() => setNow(Date.now()), 0);
    const clock = setInterval(() => setNow(Date.now()), 60000);
    fetch('/api/home-fixtures', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json(); }).then(setData).catch(e => { if (e.name !== 'AbortError') setFailed(true); });
    return () => { controller.abort(); clearTimeout(initial); clearInterval(clock); };
  }, []);
  return <section className="hf-section" id="matchups" aria-labelledby="hf-title"><div className="hf-container">
    <div className="hf-heading"><div><p className="hf-eyebrow">Your next match starts here</p><h2 id="hf-title">Who has the history?</h2><p>Open a matchup to explore previous meetings, player profiles and historical betting returns.</p></div><Link prefetch={false} href="/tools">All tools <span aria-hidden="true">↗</span></Link></div>
    <nav className="hf-jump" aria-label="Choose a sport"><a href="#home-football">Football ↓</a><a href="#home-tennis">Tennis ↓</a></nav>
    <div className="hf-sports">{(['football', 'tennis'] as const).map(sport => {
      const feed = data?.[sport];
      const fixtures = feed && now ? upcomingHomeFixtures(sport === 'tennis' ? { ...feed, fixtures: feed.fixtures.filter(f => f.tour === 'ATP') } : feed, now) : [];
      const loading = !failed && (!data || !now);
      const stale = feed?.expiresAt && now && Date.parse(feed.expiresAt) <= now;
      const title = fixtures.length && now && londonDay(fixtures[0].start) === londonDay(now) ? `Today's ${sport}` : sport === 'football' ? 'Next league fixtures' : 'Next tennis matches';
      const href = sport === 'football' ? '/football-atlas/fixtures' : '/tennis-matchday';
      return <div className="hf-sport" id={`home-${sport}`} key={sport}><div className="hf-sport-heading"><ToolEmblem name={sport === 'football' ? 'matchday' : 'tennis-matchday'} /><div><h3>{title}</h3><span>{sport === 'football' ? 'Five major domestic leagues' : 'ATP player meetings'}</span></div><Link prefetch={false} href={href} aria-label={`All ${sport} fixtures`}>View all ↗</Link></div>

        <div className="hf-cards" aria-busy={loading}>{loading ? <><div className="hf-empty hf-skeleton" role="status">Loading upcoming fixtures…</div><div className="hf-empty hf-skeleton" aria-hidden="true" /></> : fixtures.length ? fixtures.map(f => <Fixture key={f.id} fixture={f} tennis={sport === 'tennis'} now={now!} />) : <div className="hf-empty"><ToolEmblem name={sport} /><h4>{failed || stale || !feed?.checkedAt ? 'The schedule needs a refresh' : 'No upcoming matches in this snapshot'}</h4><p>Previous meetings are still available in Return Atlas.</p><Link prefetch={false} href={sport === 'football' ? '/football-atlas' : '/return-atlas'}>Explore historical returns ↗</Link></div>}</div>
        {feed?.checkedAt && <p className="hf-freshness">Updated {new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(feed.checkedAt))} · UK times</p>}
      </div>;
    })}</div><p className="hf-coverage">Records cover meetings in our archive, across all venues. Open the matchup for dates, price coverage and returns.</p>
  </div></section>;
}
