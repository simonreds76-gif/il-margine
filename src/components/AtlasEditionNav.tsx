'use client';

import Link from 'next/link';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import ResearchIcon from './ResearchIcon';
import styles from './AtlasEditionNav.module.css';

import { researchTools, type ResearchTool } from './research-tools';

/** The three Return Atlas editions. Every other research page keeps ResearchToolNav. */
export type AtlasEdition = 'football' | 'managers' | 'tennis';

// Labels, descriptions and URLs always come from research-tools.ts; nothing is restated here.
const tool = (id: ResearchTool) => researchTools.find(item => item.id === id)!;

const editions: { id: AtlasEdition; label: string; extra?: string }[] = [
  { id: 'football', label: 'Clubs' },
  { id: 'managers', label: 'Managers' },
  { id: 'tennis', label: 'Tennis', extra: ' players' },
];
const matchdayFor: Record<AtlasEdition, ResearchTool> = { football: 'matchday', managers: 'matchday', tennis: 'tennis-matchday' };
const sports: { title: string; ids: ResearchTool[] }[] = [
  { title: 'Football', ids: ['matchday', 'football', 'managers', 'aerial'] },
  { title: 'Tennis', ids: ['tennis-matchday', 'tennis', 'matchup'] },
];
// A tool added to research-tools.ts later still appears, under "More", until it is given a sport.
const placed = new Set<ResearchTool>(sports.flatMap(sport => sport.ids));
const unplaced = researchTools.filter(item => !placed.has(item.id)).map(item => item.id);
const groups = unplaced.length ? [...sports, { title: 'More', ids: unplaced }] : sports;

export default function AtlasEditionNav({ current }: { current: AtlasEdition }) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const matchday = tool(matchdayFor[current]);

  // Escape closes the panel from anywhere in this navigation. Focus returns to the button only when
  // it would otherwise be lost inside the panel that is closing.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape' || !open) return;
    event.stopPropagation();
    const focusInPanel = panel.current?.contains(document.activeElement) ?? false;
    setOpen(false);
    if (focusInPanel) toggle.current?.focus();
  };

  return <div className={styles.shell} onKeyDown={onKeyDown}>
    <div className={styles.row}>
      <nav className={styles.editions} aria-label="Return Atlas editions">
        {editions.map(edition => <Link key={edition.id} href={tool(edition.id).href} prefetch={false} aria-current={current === edition.id ? 'page' : undefined}>
          <ResearchIcon name={edition.id} className={styles.editionIcon}/>
          <span>{edition.label}{edition.extra && <span className={styles.extra}>{edition.extra}</span>}</span>
        </Link>)}
      </nav>
      <div className={styles.aside}>
        <Link className={styles.matchday} href={matchday.href} prefetch={false}>
          <ResearchIcon name={matchday.id} className={styles.matchdayIcon}/>
          <span>{matchday.label}</span>
          <span className={styles.arrow} aria-hidden="true">→</span>
        </Link>
        <button ref={toggle} type="button" className={styles.toggle} aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(value => !value)}>
          <span>All {researchTools.length} tools</span>
          <svg className={styles.chevron} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
        </button>
      </div>
    </div>
    {/* In the HTML at all times; the hidden attribute keeps closed links out of the tab order and the accessibility tree. */}
    <div ref={panel} id={panelId} className={styles.panel} hidden={!open}>
      <nav className={styles.groups} aria-label="All research tools">
        {groups.map((group, index) => <div key={group.title} className={styles.group}>
          <p id={`${panelId}-group-${index}`} className={styles.groupTitle}>{group.title}</p>
          <ul aria-labelledby={`${panelId}-group-${index}`}>
            {group.ids.map(id => { const item = tool(id); return <li key={id}>
              <Link href={item.href} prefetch={false} aria-current={current === id ? 'page' : undefined} onClick={() => setOpen(false)}>
                <ResearchIcon name={id} className={styles.toolIcon}/>
                <span><strong>{item.label}</strong><small>{item.description}</small></span>
              </Link>
            </li>; })}
          </ul>
        </div>)}
      </nav>
    </div>
  </div>;
}
