import type { ReactNode } from 'react';
import styles from './H2HRecord.module.css';

type Props = {
  results: number[] | null;
  meetings: number | null;
  names: string[];
  details?: ReactNode[];
  showCoverage?: boolean;
  compact?: boolean;
  coverageLabel?: string;
};

// Counts include every verified meeting; optional returns use priced meetings only.
export default function H2HRecord({ results, meetings, names, details, showCoverage = true, compact = false, coverageLabel }: Props) {
  if (meetings === null || !results) return <p className={styles.empty}>History not yet matched</p>;
  if (meetings === 0) return <p className={styles.empty}>{coverageLabel ? 'No meetings in the covered leagues' : 'No meetings in our archive'}</p>;
  const hasDraws = results.length === 3;
  return <div className={`${styles.record} ${compact ? styles.compact : ""}`}>
    <dl className={`${styles.columns} ${hasDraws ? styles.three : styles.two}`}>
      {results.map((count, i) => {
        const draw = hasDraws && i === 1;
        return <div className={`${styles.result} ${draw ? styles.draw : i === 0 ? styles.first : styles.second}`} key={i}>
          <dt>{draw ? 'Draws' : <><span>{names[i === 0 ? 0 : 1]}</span><span className={styles.kind}>wins</span></>}</dt>
          <dd className={styles.count}>{count}</dd>
          {details?.[i] && <dd className={styles.detail}>{details[i]}</dd>}
        </div>;
      })}
    </dl>
    {compact && <div className={styles.balance} aria-hidden="true">{results.map((count, i) => <span key={i} className={hasDraws && i === 1 ? styles.draw : i === 0 ? styles.first : styles.second} style={{ flexGrow: count, display: count ? undefined : 'none' }}/>)}</div>}
    {showCoverage && <p className={styles.coverage}>{meetings} {meetings === 1 ? 'meeting' : 'meetings'}{coverageLabel ? ` · ${coverageLabel}` : ' in our archive'}</p>}
  </div>;
}
