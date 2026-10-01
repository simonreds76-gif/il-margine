import Image from 'next/image';
import Link from 'next/link';
import './matchday-promo.css';

/** Static cross-link. No fixture data or client runtime required. */
export default function MatchdayPromo({ compact = false }: { compact?: boolean }) {
  return <Link href="/football-atlas/fixtures" prefetch={false} className={`matchday-promo${compact ? ' matchday-promo-compact' : ''}`}>
    <Image className="matchday-promo-mark" src="/football-atlas/matchday/mark-v1.svg" width={76} height={76} alt="" unoptimized />
    <span className="matchday-promo-copy">
      <small>Return Atlas · Upcoming football</small>
      <strong>Matchday<span>.</span></strong>
      <span>See the next fixtures through their manager and club history. Compare what backing a win or draw returned in previous meetings.</span>
    </span>
    <span className="matchday-promo-action">
      {!compact && <span className="matchday-promo-outcomes" aria-hidden="true"><span><b>1</b>Home</span><span><b>×</b>Draw</span><span><b>2</b>Away</span></span>}
      <span className="matchday-promo-cta">Explore Matchday <span aria-hidden="true">↗</span></span>
    </span>
  </Link>;
}
