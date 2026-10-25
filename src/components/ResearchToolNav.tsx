'use client';

import Link from 'next/link';
import { useEffect, useRef } from 'react';
import ResearchIcon from './ResearchIcon';
import styles from './ResearchToolNav.module.css';

import { researchTools, type ResearchTool } from './research-tools';

export default function ResearchToolNav({ current }: { current: ResearchTool }) {
  const nav = useRef<HTMLElement>(null);
  useEffect(() => {
    const container = nav.current;
    const active = container?.querySelector<HTMLElement>('[aria-current="page"]');
    if (container && active) container.scrollLeft = Math.max(0, active.offsetLeft - container.offsetLeft - 8);
  }, [current]);
  return <div className={styles.shell}>
    <div className={styles.label}><span>Research tools</span><small>Explore the record. Compare the matchup.</small></div>
    <nav ref={nav} className={styles.nav} aria-label="Research tools">
      {researchTools.map(tool => <Link key={tool.id} href={tool.href} prefetch={false} aria-current={current === tool.id ? 'page' : undefined}>
        <span className={styles.icon}><ResearchIcon name={tool.id}/></span>
        <span><strong>{tool.label}</strong><small>{tool.description}</small></span>
      </Link>)}
    </nav>
  </div>;
}
