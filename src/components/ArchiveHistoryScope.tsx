'use client';

import { useEffect, useState } from 'react';
import FootballArchiveCoverage from './FootballArchiveCoverage';
import styles from './ArchiveHistoryScope.module.css';
import release from '@/data/covered-leagues-release.json';

export function useArchiveScope(available: boolean) {
  const [covered, setCovered] = useState(false);
  useEffect(() => {
    const sync = () => setCovered(available && new URLSearchParams(window.location.search).get('scope') === 'covered');
    const timer = setTimeout(sync, 0);
    window.addEventListener('popstate', sync);
    return () => { clearTimeout(timer); window.removeEventListener('popstate', sync); };
  }, [available]);
  function choose(next: boolean) {
    const url = new URL(window.location.href);
    if (next) url.searchParams.set('scope', 'covered'); else url.searchParams.delete('scope');
    window.history.pushState(null, '', url);
    setCovered(next);
  }
  return { covered, choose };
}

export default function ArchiveHistoryScope({ covered, choose, available, managers = false }: {
  covered: boolean; choose: (next: boolean) => void; available: boolean; managers?: boolean;
}) {
  return <section className={styles.scope} aria-label="History coverage">
    <div className={styles.heading}><strong>Club history coverage</strong><span>Same fixtures. More past meetings.</span></div>
    <div className={styles.choices} role="group" aria-label="History scope">
      <button aria-pressed={!covered} onClick={() => choose(false)}><strong>Top-five leagues</strong><small>Original archive</small></button>
      <button aria-pressed={covered} disabled={!available} onClick={() => choose(true)}><strong>Include Championship</strong><small>Historical club meetings only</small></button>
    </div>
    {covered ? <div className={styles.detail} role="status">
      <strong>Top five + Championship · since 2012/13</strong>
      <p>Older Championship meetings are included in club H2H and returns. Upcoming fixtures and manager records stay top-five only.</p>
      <p>{release.matches.toLocaleString('en-GB')} Championship results · {release.priced.toLocaleString('en-GB')} with prices · through {release.through}.</p>
      <details><summary>What is included?</summary><p>Regular-season league matches only. Cups, playoffs, Europe and other divisions are excluded, so this is not an all-time H2H. Results without prices count as meetings but are excluded from ROI. The original archive remains available using the other button.</p><p>Historical source: <a href="https://football-data.co.uk/data.php" target="_blank" rel="noreferrer">Football-Data</a>. Recent additions use independently checked results and recorded pre-match prices. Prices retain their bookmaker and snapshot basis.</p></details>
    </div> : <FootballArchiveCoverage managers={managers} />}
    {!available && <p className={styles.detail}>The wider history is awaiting a matching archive refresh. The original record remains available.</p>}
  </section>;
}
