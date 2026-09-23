import Image from 'next/image';
import Link from 'next/link';
import SportIcon from './SportIcon';
import './return-atlas-feature.css';

/** Lightweight, server-rendered promotion: no archive download or chart runtime. */
export default function ReturnAtlasFeature() {
    return <section id="return-atlas" className="home-atlas" aria-labelledby="home-atlas-title"><div className="home-atlas-inner">
        <header><div><p className="home-atlas-eyebrow">Research beyond the picks</p><h2 id="home-atlas-title">Return <span>Atlas</span></h2></div><p>Explore historical betting returns at the recorded odds. Compare ROI, profit and sample size, then open the matches behind the numbers.</p></header>
        <div className="home-atlas-editions">
            <article className="home-atlas-edition"><div className="home-atlas-status"><h3><Link href="/return-atlas" prefetch={false}><SportIcon sport="tennis" emblem className="home-atlas-sport-icon"/><span>ATP tennis betting history</span><span aria-hidden="true">↗</span></Link></h3><span>Explore now</span></div>
                <div className="home-atlas-logo home-atlas-tennis-logo"><Image src="/return-atlas/assets/wordmark-tennis-v2.png" width={2172} height={724} alt="Return Atlas Tennis" unoptimized /></div>
                <p>Which players returned a profit when backed—or opposed? Compare seasons, surfaces, favourites, underdogs and exact odds ranges using a constant one-unit stake.</p>
                <ul><li>Search player records</li><li>Compare price ranges</li><li>Inspect profit curves and results</li></ul>
                <Link className="home-atlas-cta" href="/return-atlas" prefetch={false}><SportIcon sport="tennis" className="home-atlas-cta-icon"/>Explore tennis player returns <span aria-hidden="true">↗</span></Link>
            </article>
            <article className="home-atlas-edition"><div className="home-atlas-status"><h3><Link href="/football-atlas" prefetch={false}><SportIcon sport="football" emblem className="home-atlas-sport-icon"/><span>Football club betting history</span><span aria-hidden="true">↗</span></Link></h3><span>Explore now</span></div>
                <div className="home-atlas-logo home-atlas-football-logo"><Image src="/football-atlas/wordmark-football-v1.png" width={2172} height={724} alt="Return Atlas Football" unoptimized /></div>
                <p>Explore Europe’s top five domestic leagues: club returns by season, home and away, market role and odds range. League matches only; cups and European competitions are excluded.</p>
                <ul><li>Team, draw or opponent win</li><li>Recent seasons combined</li><li>Club records and match breakdowns</li></ul>
                <Link className="home-atlas-cta" href="/football-atlas" prefetch={false}><SportIcon sport="football" className="home-atlas-cta-icon"/>Explore football club returns <span aria-hidden="true">↗</span></Link>
            </article>
        </div>
        <footer><p>Historical research, separate from our published selections. Past returns do not establish a future edge.</p><Link href="/faq#return-atlas" prefetch={false}>How Return Atlas works →</Link></footer>
    </div></section>;
}
