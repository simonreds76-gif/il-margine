import Icon from './FootballAtlasIcon';
import EditorialIcon from '@/components/EditorialIcon';
export function FootballAtlasGuide() {
 return <section className="fa-guide" aria-labelledby="fa-guide-title">
  <div className="fa-guide-copy"><p className="fa-eyebrow">A betting record, built around your question</p><h2 id="fa-guide-title">Same club. Same stake. What happened?</h2>
   <p>Imagine placing a <strong>1-unit bet in every included league match</strong> involving a club. Choose the team, the draw or its opponent, then see the profit and return that those bets would have produced at the recorded prices.</p>
   <details className="fa-how"><summary>How to use Return Atlas <span aria-hidden="true">＋</span></summary><ol>
    <li><strong>Choose your bet.</strong> Back team and Back opponent need that side to win. Only Back draw wins when the score is level. Results use 90 minutes plus stoppage time.</li>
    <li><strong>Narrow the circumstances.</strong> Pick a league, favourite or underdog, then home or away, a season or combined season range, and odds range. Role, venue and odds always describe the club named in the record.</li>
    <li><strong>Compare, then investigate.</strong> Sort by ROI or profit and open a club for its curve, season breakdown and every included bet. Use the minimum-match filter to remove tiny samples.</li></ol>
    <p>A favourite has a shorter win price than its opponent; it can still be above 2.00. Back opponent is a win bet: a draw loses it. It is neither a lay nor a double-chance bet.</p><a href="#football-method">Price coverage & full methodology →</a>
   </details>
  </div>
  <aside className="fa-example" aria-label="Illustrative return calculation"><div className="fa-example-title"><Icon name="all"/><span>One simple example<small>Illustration · not a club result</small></span></div>
   <dl><div><dt>10 bets × 1u</dt><dd>10u staked</dd></div><div><dt>Total returned, including stakes</dt><dd>12u</dd></div></dl>
   <div className="fa-example-result"><span>Net profit<strong>+2u</strong></span><span>Return on stakes<strong>+20%</strong></span></div>
   <p>ROI = 2u profit ÷ 10u staked. The unit size stays constant; returns are not compounded.</p>
  </aside>
 </section>;
}
export function FootballAtlasLegend() {
 return <details className="fa-legend"><summary><EditorialIcon name="guide" className="fa-legend-summary-icon"/> Read the numbers <small>ROI · units · records · coverage</small><span className="fa-legend-open" aria-hidden="true">＋</span></summary>
  <dl><div><dt><EditorialIcon name="analysis" className="fa-legend-icon"/>ROI</dt><dd>Net profit ÷ total stakes, as a percentage. +10% means +0.10u per unit staked.</dd></div>
   <div><dt><EditorialIcon name="bankroll" className="fa-legend-icon"/>Net profit · u</dt><dd>Winnings less stakes. Each bet risks 1u: win at 2.50 → +1.50u; lose → −1u.</dd></div>
   <div><dt><EditorialIcon name="markets" className="fa-legend-icon"/>Bets won / lost</dt><dd>The result of your chosen bet. Backing the draw can win even though the club did not.</dd></div>
   <div><dt><EditorialIcon name="compare" className="fa-legend-icon"/>Team W / D / L</dt><dd>The named club’s match wins, draws and losses within the selected priced sample.</dd></div>
   <div><dt><EditorialIcon name="guide" className="fa-legend-icon"/>Price coverage</dt><dd>Priced / eligible archived matches, before role and odds filters. Missing prices are excluded from returns.</dd></div>
   <div><dt><EditorialIcon name="method" className="fa-legend-icon"/>Largest drawdown</dt><dd>The biggest fall in cumulative profit from an earlier peak to a later low, in units.</dd></div></dl>
  <p>Green + figures show profit; coral − figures show a loss. Historical returns do not establish a future edge.</p>
 </details>;
}
