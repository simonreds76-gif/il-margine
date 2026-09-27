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
                <p>Which players returned a profit when backed or opposed? Compare seasons, surfaces, favourites, underdogs and exact odds ranges using a constant one-unit stake.</p>
                <ul><li>Search player records</li><li>Compare price ranges</li><li>Inspect profit curves and results</li></ul>
                <nav className="home-atlas-routes" aria-label="Tennis research tools">
                    <Link className="home-atlas-route" href="/return-atlas" prefetch={false}>
                        <span className="home-atlas-route-icon"><SportIcon sport="tennis" emblem /></span>
                        <span className="home-atlas-route-copy"><small>Player records</small><strong>Explore player returns</strong><span>Backing or opposing · filter the odds</span></span>
                        <span className="home-atlas-route-arrow" aria-hidden="true">↗</span>
                    </Link>
                    <Link className="home-atlas-route home-atlas-route-matchup" href="/tennis-matchup" prefetch={false}>
                        <span className="home-atlas-route-icon"><Image src="/tennis-matchup/court-v1.webp" width={44} height={44} alt="" unoptimized /></span>
                        <span className="home-atlas-route-copy"><small>Tennis Matchup Lab</small><strong>Compare two players</strong><span>Head-to-head, serve and return statistics</span></span>
                        <span className="home-atlas-route-arrow" aria-hidden="true">↗</span>
                    </Link>
                </nav>
                <p className="home-atlas-scope">ATP main-draw archive · 2022 onward · coverage varies by match</p>
            </article>
            <article className="home-atlas-edition"><div className="home-atlas-status"><h3><Link href="/football-atlas" prefetch={false}><SportIcon sport="football" emblem className="home-atlas-sport-icon"/><span>Football club betting history</span><span aria-hidden="true">↗</span></Link></h3><span>Explore now</span></div>
                <div className="home-atlas-logo home-atlas-football-logo"><Image src="/football-atlas/wordmark-football-v1.png" width={2172} height={724} alt="Return Atlas Football" unoptimized /></div>
                <p>See the results behind the odds across Europe’s top five domestic leagues. Explore a club’s record, or compare the managers facing each other.</p>
                <ul><li>Team, draw or opponent win</li><li>Recent seasons combined</li><li>Club records and match breakdowns</li></ul>
                <nav className="home-atlas-routes" aria-label="Football Return Atlas tools">
                    <Link className="home-atlas-route home-atlas-route-clubs" href="/football-atlas" prefetch={false}>
                        <span className="home-atlas-route-icon"><SportIcon sport="football" emblem /></span>
                        <span className="home-atlas-route-copy"><small>Club records</small><strong>Explore club returns</strong><span>Team, draw and opponent · every result</span></span>
                        <span className="home-atlas-route-arrow" aria-hidden="true">↗</span>
                    </Link>
                    <Link className="home-atlas-route home-atlas-route-managers" href="/manager-atlas" prefetch={false}>
                        <span className="home-atlas-route-icon"><Image src="/manager-atlas/mark-v2.svg" width={44} height={44} alt="" unoptimized /></span>
                        <span className="home-atlas-route-copy"><small>Manager head-to-head</small><strong>Compare two managers</strong><span>Their meetings, match odds and returns</span></span>
                        <span className="home-atlas-route-arrow" aria-hidden="true">↗</span>
                    </Link>
                </nav>
                <p className="home-atlas-scope">Domestic leagues only · cups and European competitions excluded</p>
            </article>
        </div>
        <footer><p>Historical research, separate from our published selections. Past returns do not establish a future edge.</p><Link href="/faq#return-atlas" prefetch={false}>How Return Atlas works →</Link></footer>
    </div></section>;
}
