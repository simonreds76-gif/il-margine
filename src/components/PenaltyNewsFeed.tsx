"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { newsDate, newsLeagues, outcomeLabel, newsPagePath, NEWS_PAGE_SIZE, type PenaltyArticle } from "@/lib/penalty-news";
import styles from "./PenaltyNews.module.css";

export function NewsPicture({ src, name, crest = false }: { src: string; name: string; crest?: boolean }) {
  const [failed, setFailed] = useState(false);
  return <span className={crest ? styles.crest : styles.portrait}>
    {failed ? <span aria-label={name}>{name.split(" ").map(n => n[0]).slice(0, 2).join("")}</span>
      : <Image src={src} alt={name} width={crest ? 36 : 80} height={crest ? 36 : 80} unoptimized onError={() => setFailed(true)} />}
  </span>;
}

function NewsIcon({ kind }: { kind: "clock" | "goal" | "shots" }) {
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">{kind === "clock" ? <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></> : kind === "goal" ? <><path d="M3 19V6h18v13M7 6v13M17 6v13M3 10h18M3 14h18" /><circle cx="12" cy="18" r="3" fill="currentColor" stroke="none" /></> : <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><path d="m16 8 5-5m-4 0h4v4" /></>}</svg>;
}

export function PenaltyNewsCard({ article, detail = false }: { article: PenaltyArticle; detail?: boolean }) {
  const a = article;
  const statisticItems = [
    { label: "Match goals", value: a.stats.goals, kind: "goal" as const },
    { label: "Shots on target", value: a.stats.onTarget, kind: "shots" as const },
    { label: "Minutes", value: a.stats.minutes, kind: "clock" as const },
  ].filter(s => s.value !== null);
  return <article className={`${styles.card} ${detail ? styles.detailCard : ""}`}>
    <div className={styles.cardMeta}><span className={styles.leagueLabel}><Image src={`/league-logos/${a.league}.png`} alt="" width={22} height={22} unoptimized />{a.leagueLabel}</span><time dateTime={a.date}>{newsDate(a.date)}</time></div>
    <div className={styles.storyHeader}>
      <div className={styles.playerVisual}><NewsPicture src={a.portrait} name={a.player} /><span className={styles.visualCrest}><NewsPicture src={a.crest} name={a.club} crest /></span></div>
      <div className={styles.playerCopy}><span className={styles.clubLine}>{a.club} <span className={styles.minute}>{a.minute}′</span></span>
        {!detail && <h2><Link href={`/penalty-news/${a.slug}`} prefetch={false}>{a.title}</Link></h2>}
        {detail && <h2>{a.player}</h2>}
        <span className={`${styles.badge} ${a.outcome === "scored" ? styles.scored : styles.notScored}`}><svg viewBox="0 0 20 20" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7"><circle cx="10" cy="10" r="7.5" />{a.outcome === "scored" ? <path d="m6 10 2.5 2.5L14 7" /> : <path d="m7 7 6 6m0-6-6 6" />}</svg>{outcomeLabel[a.outcome]}</span>
      </div>
    </div>
    <div className={styles.scoreline}><span>{a.home}</span><strong>{a.homeScore}<span>:</span>{a.awayScore}</strong><span>{a.away}</span><small>FT</small></div>
    <div className={styles.storyBody}>{a.paragraphs.map((paragraph, i) => <p className={i === 0 ? styles.lead : styles.summary} key={i}>{paragraph}</p>)}</div>
    {statisticItems.length > 0 && <dl className={styles.statStrip}>{statisticItems.map(s => <div key={s.label}><dt><NewsIcon kind={s.kind} />{s.label}</dt><dd>{s.value}</dd></div>)}</dl>}
    <div className={styles.cardActions}><Link className={styles.clubLink} href={a.clubUrl} prefetch={false}><NewsPicture src={a.crest} name={a.club} crest /><span>{a.club} penalty takers</span><span aria-hidden="true">↗</span></Link>
      {!detail && <Link className={styles.readLink} href={`/penalty-news/${a.slug}`} prefetch={false} aria-label={`Open ${a.player} penalty report`}>Full report <span aria-hidden="true">→</span></Link>}
    </div>
    {detail && <div className={styles.source}><span>Published {newsDate(a.publishedAt)} · Match played {newsDate(a.date)}</span>{a.updatedAt !== a.publishedAt && <span>Updated {newsDate(a.updatedAt)}</span>}</div>}
  </article>;
}

export default function PenaltyNewsFeed({ articles, page = 1 }: { articles: PenaltyArticle[]; page?: number }) {
  const [league, setLeague] = useState("all");
  const [club, setClub] = useState("all");
  const [outcome, setOutcome] = useState("all");
  const [visible, setVisible] = useState(NEWS_PAGE_SIZE);
  const clubs = useMemo(() => [...new Set(articles.filter(a => league === "all" || a.league === league).map(a => a.club))].sort(), [articles, league]);
  const filtered = articles.filter(a => (league === "all" || a.league === league) && (club === "all" || a.club === club) && (outcome === "all" || (outcome === "scored" ? a.outcome === "scored" : a.outcome !== "scored")));
  const filtering = league !== "all" || club !== "all" || outcome !== "all";
  const pageCount = Math.ceil(articles.length / NEWS_PAGE_SIZE);
  const displayed = filtering ? filtered.slice(0, visible) : articles.slice((page - 1) * NEWS_PAGE_SIZE, page * NEWS_PAGE_SIZE);
  const pageNumbers = Array.from({ length: pageCount }, (_, i) => i + 1).filter(n => n === 1 || n === pageCount || Math.abs(n - page) <= 1);
  const reset = () => { setLeague("all"); setClub("all"); setOutcome("all"); setVisible(12); };
  return <section aria-label="Penalty reports" id="reports">
    <div className={styles.filters}>
      <div className={styles.leagueFilters} role="group" aria-label="Filter by league"><button type="button" aria-pressed={league === "all"} onClick={() => {setLeague("all"); setClub("all"); setVisible(12);}}>All leagues</button>{newsLeagues.map(l => <button type="button" key={l.key} aria-pressed={league === l.key} onClick={() => { setLeague(l.key); setClub("all"); setVisible(12); }}><Image src={`/league-logos/${l.key}.png`} alt="" width={22} height={22} unoptimized />{l.label}</button>)}</div>
      <div className={styles.selects}><label>Club<select aria-label="Club" value={club} onChange={e => {setClub(e.target.value); setVisible(12);}}><option value="all">All clubs</option>{clubs.map(c => <option key={c}>{c}</option>)}</select></label><label>Outcome<select aria-label="Outcome" value={outcome} onChange={e => {setOutcome(e.target.value); setVisible(12);}}><option value="all">All penalties</option><option value="scored">Scored</option><option value="not-scored">Not scored</option></select></label>{(league !== "all" || club !== "all" || outcome !== "all") && <button type="button" className={styles.reset} onClick={reset}>Clear filters</button>}</div>
    </div>
    <div className={styles.feedHeading}><h2>{filtering ? "Matching reports" : page === 1 ? "The latest from the spot" : "Earlier penalty reports"}</h2><span role="status">{filtered.length} {filtered.length === 1 ? "report" : "reports"}{!filtering && pageCount > 1 ? ` · Page ${page} of ${pageCount}` : ""}</span></div>
    {filtered.length ? <div className={styles.grid}>{displayed.map(a => <PenaltyNewsCard key={a.id} article={a} />)}</div> : <div className={styles.empty}><h3>No reports match these filters</h3><p>Try another club or view all penalties in this collection.</p><button type="button" onClick={reset}>View all reports</button></div>}
    {filtering && filtered.length > visible && <button type="button" className={styles.more} onClick={() => setVisible(v => v + NEWS_PAGE_SIZE)}>Show more matching reports <span aria-hidden="true">↓</span></button>}
    {!filtering && pageCount > 1 && <nav className={styles.pagination} aria-label="Penalty News archive pages">
      {page > 1 && <Link href={`${newsPagePath(page - 1)}#reports`} prefetch={false} rel="prev">← Newer</Link>}
      {pageNumbers.map((n, i) => <span key={n}>{i > 0 && n - pageNumbers[i - 1] > 1 && <span className={styles.pageGap}>…</span>}<Link href={`${newsPagePath(n)}#reports`} aria-label={`Reports page ${n}`} aria-current={n === page ? "page" : undefined} prefetch={false}>{n}</Link></span>)}
      {page < pageCount && <Link href={`${newsPagePath(page + 1)}#reports`} prefetch={false} rel="next">Older →</Link>}
    </nav>}
  </section>;
}
