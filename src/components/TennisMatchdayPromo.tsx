import Link from 'next/link';
import Image from 'next/image';
import styles from './TennisMatchdayPromo.module.css';

export default function TennisMatchdayPromo() {
  return <Link href="/tennis-matchday" prefetch={false} className={styles.card}>
    <Image src="/tennis-matchday/mark.svg" width={44} height={44} alt="" unoptimized />
    <span><small>TENNIS MATCHDAY</small><strong>Start with an upcoming match</strong><span>See the pairing, its previous meetings and both players’ records.</span></span>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>
  </Link>;
}
