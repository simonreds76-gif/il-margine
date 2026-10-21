"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { newsDate, newsLeagues, outcomeLabel, type PenaltyArticle } from "@/lib/penalty-news";
import styles from "./PenaltyNews.module.css";

export function NewsPicture({ src, name, crest = false }: { src: string; name: string; crest?: boolean }) {
  const [failed, setFailed] = useState(false);
  return <span className={crest ? styles.crest : styles.portrait}>
    {failed ? <span aria-label={name}>{name.split(" ").map(n => n[0]).slice(0, 2).join("")}</span>
      : <Image src={src} alt={name} width={crest ? 36 : 80} height={crest ? 36 : 80} unoptimized onError={() => setFailed(true)} />}
  </span>;
}

export function PenaltyNewsCard({ article, detail = false }: { article: PenaltyArticle; detail?: boolean }) {
  const a = article;
  return <article className={`${styles.card} ${detail ? styles.detailCard : ""}`}>
    <div className={styles.cardMeta}><span className={styles.leagueLabel}><Image src={`/league-logos/${a.league}.png`} alt="" width={22} height={22} unoptimized />{a.leagueLabel}</span><time dateTime={a.date}>{newsDate(a.date)}</time></div>
    <div className={styles.playerRow}><NewsPicture src={a.portrait} name={a.player} /><div className={styles.playerCopy}>
      <span className={styles.clubLine}><NewsPicture src={a.crest} name={a.club} crest /><span>{a.club}</span></span>
      <h2>{detail ? a.player : <Link href={`/penalty-news/${a.slug}`} prefetch={false}>{a.player}</Link>}</h2>
      <span className={`${styles.badge} ${a.outcome === "scored" ? styles.scored : styles.notScored}`}><svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7"><circle cx="10" cy="10" r="7.5" />{a.outcome === "scored" ? <path d="m6 10 2.5 2.5L14 7" /> : <path d="m7 7 6 6m0-6-6 6" />}</svg>{outcomeLabel[a.outcome]}<span className={styles.badgeMinute}>{a.minute}′</span></span>
    </div></div>
    <div className={styles.scoreline}><span>{a.home}</span><strong>{a.homeScore}<span>:</span>{a.awayScore}</strong><span>{a.away}</span><small>FT</small></div>
    <p className={styles.summary}>{a.sentences.join(" ")}</p>
    <div className={styles.cardActions}><Link className={styles.clubLink} href={a.clubUrl} prefetch={false}><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M5 20V4h14v16M5 12h14M9 4v4h6V4" /><circle cx="12" cy="15.5" r="1.5" /></svg><span>{a.club} penalty takers</span><span aria-hidden="true">↗</span></Link>
      {!detail && <Link className={styles.readLink} href={`/penalty-news/${a.slug}`} prefetch={false} aria-label={`Open ${a.player} penalty report`}>Report <span aria-hidden="true">→</span></Link>}
    </div>
    {detail && <div className={styles.source}><a href={a.sourceUrl} target="_blank" rel="noreferrer">Match evidence on FotMob ↗</a><span>Published {newsDate(a.publishedAt)} · Match played {newsDate(a.date)}</span>{a.updatedAt !== a.publishedAt && <span>Updated {newsDate(a.updatedAt)}</span>}</div>}
  </article>;
}

export default function PenaltyNewsFeed({ articles }: { articles: PenaltyArticle[] }) {
  const [league, setLeague] = useState("all");
  const [club, setClub] = useState("all");
  const [outcome, setOutcome] = useState("all");
  const [visible, setVisible] = useState(12);
  const clubs = useMemo(() => [...new Set(articles.filter(a => league === "all" || a.league === league).map(a => a.club))].sort(), [articles, league]);
  const filtered = articles.filter(a => (league === "all" || a.league === league) && (club === "all" || a.club === club) && (outcome === "all" || (outcome === "scored" ? a.outcome === "scored" : a.outcome !== "scored")));
  const reset = () => { setLeague("all"); setClub("all"); setOutcome("all"); setVisible(12); };
  return <section aria-label="Penalty reports" id="reports">
    <div className={styles.filters}>
      <div className={styles.leagueFilters} role="group" aria-label="Filter by league"><button type="button" aria-pressed={league === "all"} onClick={() => {setLeague("all"); setClub("all"); setVisible(12);}}>All leagues</button>{newsLeagues.map(l => <button type="button" key={l.key} aria-pressed={league === l.key} onClick={() => { setLeague(l.key); setClub("all"); setVisible(12); }}><Image src={`/league-logos/${l.key}.png`} alt="" width={22} height={22} unoptimized />{l.label}</button>)}</div>
      <div className={styles.selects}><label>Club<select value={club} onChange={e => {setClub(e.target.value); setVisible(12);}}><option value="all">All clubs</option>{clubs.map(c => <option key={c}>{c}</option>)}</select></label><label>Outcome<select value={outcome} onChange={e => {setOutcome(e.target.value); setVisible(12);}}><option value="all">All penalties</option><option value="scored">Scored</option><option value="not-scored">Not scored</option></select></label>{(league !== "all" || club !== "all" || outcome !== "all") && <button type="button" className={styles.reset} onClick={reset}>Clear filters</button>}</div>
    </div>
    <div className={styles.feedHeading}><h2>The latest from the spot</h2><span role="status">{filtered.length} {filtered.length === 1 ? "report" : "reports"}</span></div>
    {filtered.length ? <div className={styles.grid}>{filtered.slice(0, visible).map(a => <PenaltyNewsCard key={a.id} article={a} />)}</div> : <div className={styles.empty}><h3>No reports match these filters</h3><p>Try another club or view all penalties in this collection.</p><button type="button" onClick={reset}>View all reports</button></div>}
    {filtered.length > visible && <button type="button" className={styles.more} onClick={() => setVisible(v => v + 12)}>Show more reports <span aria-hidden="true">↓</span></button>}
  </section>;
}
