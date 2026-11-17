'use client';

import Link from 'next/link';
import { useId, useRef, useState, type KeyboardEvent } from 'react';
import ResearchIcon from './ResearchIcon';
import styles from './AirControlNav.module.css';

import { researchTools, type ResearchTool } from './research-tools';

/**
 * Compact discovery for Air Control: the matching fixtures link and the same grouped "All tools" disclosure
 * the Return Atlas pages use. Air Control is its own football tool, so there is no edition switcher.
 * AtlasEditionNav is deliberately not touched or shared; this is a separate component with the same behaviour.
 */

// Labels, descriptions and URLs always come from research-tools.ts; nothing is restated here.
const tool = (id: ResearchTool) => researchTools.find(item => item.id === id)!;

const current: ResearchTool = 'aerial';
const sports: { title: string; ids: ResearchTool[] }[] = [
  { title: 'Football', ids: ['matchday', 'football', 'managers', 'aerial'] },
  { title: 'Tennis', ids: ['tennis-matchday', 'tennis', 'matchup'] },
];
// A tool added to research-tools.ts later still appears, under "More", until it is given a sport.
const placed = new Set<ResearchTool>(sports.flatMap(sport => sport.ids));
const unplaced = researchTools.filter(item => !placed.has(item.id)).map(item => item.id);
const groups = unplaced.length ? [...sports, { title: 'More', ids: unplaced }] : sports;

export default function AirControlNav() {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const matchday = tool('matchday');

  // Escape closes the panel from anywhere in this navigation. Focus returns to the button only when
  // it would otherwise be lost inside the panel that is closing.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape' || !open) return;
    event.stopPropagation();
    const focusInPanel = panel.current?.contains(document.activeElement) ?? false;
    setOpen(false);
    if (focusInPanel) toggle.current?.focus();
  };

  // The wrapper has display: contents, so the two children below lay out as items of the header's title row:
  // the links beside the title (or under it on a phone) and the panel on its own full-width line.
  return <div className={styles.shell} onKeyDown={onKeyDown}>
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
