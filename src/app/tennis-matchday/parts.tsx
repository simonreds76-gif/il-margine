import { useState, type ReactNode } from 'react';
import Image from 'next/image';
import { surfaceNames } from '@/lib/tennis-matchday-browse.mjs';
import styles from './matchday.module.css';

// Small presentational pieces shared by the Upcoming and Results views.
// Imported only by client components.
export type Country = { code: string; name: string; flag: string } | null;
export type RailItem = { key: string; name: string; count: number; surface: string; country: Country };

export const surfaceLabel = (surface: string) => (surfaceNames as Record<string, string>)[surface] || surface;

export function Icon({ name }: { name: 'search' | 'chevron' | 'arrow' | 'person' | 'record' | 'tick' | 'filter' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'search' ? <><circle cx="10" cy="10" r="6" /><path d="m15 15 5 5" /></>
      : name === 'chevron' ? <path d="m6 9 6 6 6-6" />
      : name === 'arrow' ? <path d="M5 12h14m-6-6 6 6-6 6" />
      : name === 'person' ? <><circle cx="12" cy="8" r="3.5" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>
      : name === 'record' ? <path d="M4 19h16M6 15V9m6 6V5m6 10v-7" />
      : name === 'filter' ? <path d="M4 7h16M7 12h10M10 17h4" />
      : <path d="m5 12.5 4.5 4.5L19 7.5" />}
  </svg>;
}

// Geography: the verified venue country, or an honest empty slot. Never a guess.
export function Flag({ country }: { country: Country }) {
  if (!country) return <span className={styles.flagEmpty} title="Country not verified"><span className="sr-only">Country not verified</span></span>;
  return <Image className={styles.flag} src={country.flag} alt={country.name} title={country.name} width={24} height={16} unoptimized />;
}

// Court type: a coloured dot plus the words. Separate from the flag on purpose.
export function Surface({ surface }: { surface: string }) {
  return <span className={styles.surface} data-surface={surface}><i className={styles.dot} aria-hidden="true" />{surfaceLabel(surface)}</span>;
}

export function TournamentRail({ items, selected, total, onSelect, label }: {
  items: RailItem[]; selected: string; total: number; onSelect: (key: string) => void; label: string;
}) {
  return <div className={styles.rail} role="group" aria-label={label}>
    <button type="button" className={styles.chip} aria-pressed={selected === 'all'} onClick={() => onSelect('all')}>
      <span>All</span><span className={styles.chipCount}>{total}</span>
    </button>
    {items.map(item => <button key={item.key} type="button" className={styles.chip} data-surface={item.surface} data-empty={item.count === 0}
      aria-pressed={selected === item.key} onClick={() => onSelect(item.key)}>
      <Flag country={item.country} />
      <span>{item.name}</span>
      <i className={styles.dot} aria-hidden="true" title={surfaceLabel(item.surface)} />
      <span className={styles.chipCount}>{item.count}<span className="sr-only"> {item.count === 1 ? 'match' : 'matches'}, {surfaceLabel(item.surface)}</span></span>
    </button>)}
  </div>;
}

// Secondary filters. Always visible on wide screens; one "Filters" control on phones.
export function OptionsBar({ tally, active, children }: { tally: string; active: number; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className={styles.options} data-open={open}>
    <button type="button" className={styles.filterToggle} aria-expanded={open} onClick={() => setOpen(!open)}>
      <Icon name="filter" />Filters{active ? ` · ${active}` : ''}
    </button>
    <div className={styles.optionSet}>{children}</div>
    <span className={styles.tally} aria-live="polite">{tally}</span>
  </div>;
}
