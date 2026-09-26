import Image from "next/image";
import Link from "next/link";
import "./tennis-matchup-feature.css";

export default function TennisMatchupFeature(){
  return <section className="home-matchup" aria-labelledby="home-matchup-title"><div className="home-matchup-art"><Image src="/tennis-matchup/court-v1.webp" width={320} height={320} alt="" unoptimized/></div><div><p className="site-eyebrow">Explore the matchup</p><h2 id="home-matchup-title">Tennis Matchup <span>Lab</span></h2><p>Who holds the edge on serve? What happened when they met? Compare two players’ records, then narrow the view by court, country or region.</p><ul><li>Head-to-head results</li><li>Aces & double faults</li><li>Serve & return profiles</li></ul><div className="home-matchup-links"><Link href="/tennis-matchup" prefetch={false}>Compare tennis players <span aria-hidden="true">↗</span></Link><Link href="/tennis-matchup#faq" prefetch={false}>How it works →</Link></div><small>ATP main-draw archive from 2022. Historical context, not a prediction.</small></div></section>;
}
