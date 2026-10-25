import styles from './FootballArchiveCoverage.module.css';

export const FOOTBALL_ARCHIVE_SCOPE = 'Top-five leagues only · since 2012/13';
export const FOOTBALL_ARCHIVE_DETAIL = 'Premier League, Serie A, La Liga, Bundesliga and Ligue 1. Lower divisions, domestic cups and European competitions are not included.';

export default function FootballArchiveCoverage({ managers = false }: { managers?: boolean }) {
  return <aside className={styles.coverage} aria-label="Historical record coverage">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/></svg>
    <div><strong>{FOOTBALL_ARCHIVE_SCOPE}</strong><p>{FOOTBALL_ARCHIVE_DETAIL}</p><p>{managers ? 'Manager records cover verified matches in these leagues, not their full careers.' : 'H2H counts cover this archive, not every meeting between the teams.'} Results without recorded odds count as meetings but are excluded from ROI.</p></div>
  </aside>;
}
