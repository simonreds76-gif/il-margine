import { DisclosureCue } from "./DisclosureCue";

const groups = [
  { title: "Is the price worth a look?", number: "01", items: [
    ["Better price", "positive", "Bet365 offers higher odds than our fair price. Potential value according to the model, not a guaranteed win."],
    ["Below fair", "neutral", "Bet365 offers lower odds than our fair price."],
    ["Matches fair", "neutral", "The bookmaker price matches our estimate."],
  ] },
  { title: "Are the numbers ready?", number: "02", items: [
    ["Odds need rechecking", "pending", "These odds need a fresh check. They may be old or from before a lineup change. Open the player to see the last check."],
    ["No odds", "pending", "Our feed has not supplied this player’s Bet365 odds yet. The bookmaker may still offer a market."],
    ["Estimate*", "pending", "Limited player history. We show an estimate but leave this player out of value comparisons."],
    ["Not compared", "neutral", "We need usable fair odds, recent bookmaker odds and a match that has not started to compare prices."],
    ["Unpriced / Data pending", "neutral", "A fair price is not available yet. Goalkeepers are currently unpriced."],
  ] },
  { title: "Who is playing?", number: "03", items: [
    ["Expected starter", "pending", "Predicted to start. Fair odds assume a start and may change with the official lineup."],
    ["Confirmed starter", "positive", "Named in the official starting XI supplied by our feed."],
    ["PEN", "positive", "Expected first-choice penalty taker in this lineup."],
    ["Match started", "neutral", "Kickoff has passed. The displayed prices are a pre-match snapshot, not live odds."],
  ] },
];

export function PlayerLabelGuide() {
  return <details id="lab-guide" className="ip-label-guide">
    <summary><span className="ip-guide-heading"><span className="ip-eyebrow">A QUICK GUIDE</span><strong>Read the prices with confidence</strong><small>What the two prices, colours and player labels mean</small></span><DisclosureCue /></summary>
    <div className="ip-guide-body">
      <div className="ip-guide-example">
        <div className="ip-guide-example-copy"><span className="ip-eyebrow">AN EXAMPLE · NOT A CURRENT PICK</span><h3>Same player. Two prices.</h3><p>Compare our estimate with the odds you can get at Bet365.</p></div>
        <div className="ip-guide-example-prices"><div><span>Our fair odds</span><strong>3.00</strong><small>Our model’s estimate</small></div><div><span>Bet365 odds</span><strong>3.50</strong><small>The bookmaker’s price</small></div></div>
        <p className="ip-guide-takeaway"><span className="ip-status-chip positive">Better price</span>Here, Bet365 pays more than our estimated fair price. Decimal odds of 3.50 return £3.50 per £1 if the bet wins, including your stake.</p>
      </div>
      <div className="ip-guide-groups">{groups.map(group => <section key={group.number}><header><span>{group.number}</span><h3>{group.title}</h3></header><dl>{group.items.map(([label, tone, description]) => <div key={label}><dt><span className={`ip-status-chip ${tone}`}>{label}</span></dt><dd>{description}</dd></div>)}</dl></section>)}</div>
      <div className="ip-margin-note"><strong>Our fair odds ≠ bookmaker odds with the margin removed</strong><p>Our price comes from a player scoring estimate. Removing bookmaker margin needs every outcome in the same market — for example, both “scores” and “does not score”. Different players can all score, so adding their anytime goalscorer prices together does not give a valid market margin.</p><a href="/the-edge">Explore fair odds &amp; bookmaker margin →</a></div><p className="ip-guide-tip">Tap any player to see their odds, penalty role and last update. All times are UK time.</p>
    </div>
  </details>;
}
