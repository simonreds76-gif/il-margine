import type { Metadata } from 'next';
import Link from 'next/link';
import Footer from '@/components/Footer';
import Explorer from './Explorer';
import styles from './conditions.module.css';
export const dynamic='force-static';
export const metadata:Metadata={title:'Court Conditions | Il Margine Research Preview',robots:{index:false,follow:false}};
export default function Page(){return <><main className={styles.page}><header className={styles.header}><Link href="/tennis-matchup">← Tennis Matchup Lab</Link><div className={styles.titleRow}><svg width="64" height="64" viewBox="0 0 64 64" fill="none" aria-hidden="true"><rect x="9" y="7" width="46" height="50" rx="9" stroke="currentColor" strokeWidth="2"/><path d="M19 8v48m26-48v48M9 32h46M19 20h26M19 44h26M32 20v24" stroke="currentColor" strokeOpacity=".55"/><path d="m3 47 13-8 13 3 15-18 17-8" stroke="#f4c776" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg><div><p>IL MARGINE · TENNIS RESEARCH</p><h1>Same surface.<br/><span>Different conditions.</span></h1></div></div><p className={styles.intro}>Explore how players have served, returned and won in slower and faster conditions. Keep the match count, opposition and missing data in view.</p></header><Explorer/></main><Footer/></>}
