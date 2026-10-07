"use client";

import { useState } from "react";
import Link from "next/link";
import EditorialIcon from "@/components/EditorialIcon";
import { bookSum, devig, overroundPct, marginOnTurnoverPct, type DevigMethod } from "@/lib/calculator/math";

export default function MarginRemovalCalculator() {
  const [prices, setPrices] = useState(["1.90", "1.90"]);
  const [method, setMethod] = useState<DevigMethod>("proportional");
  const values = prices.map(Number);
  const valid = values.every(value => Number.isFinite(value) && value > 1);
  const total = valid ? bookSum(values) : 0;
  const result = valid && total >= 1 ? devig(values, method) : null;
  const labels = prices.length === 2 ? ["Player A", "Player B"] : ["Home", "Draw", "Away"];
  return <section id="remove-margin" className="bm-section bm-calculator" aria-labelledby="margin-calculator-title">
    <div className="bm-section-title"><EditorialIcon name="bankroll" className="h-11 w-11" /><div><p className="bm-kicker">See the price underneath</p><h2 id="margin-calculator-title">Remove the bookmaker margin</h2></div></div>
    <p className="bm-calculator-intro">Enter every outcome from the same bookmaker and market. We remove the built in margin to estimate the market’s fair odds. At 1.90 on both players, the fair price is 2.00 each.</p>
    <div className="bm-calculator-controls">
      <div className="bm-mode" aria-label="Market format">{[2, 3].map(count => <button key={count} type="button" aria-pressed={prices.length === count} onClick={() => setPrices(count === 2 ? ["1.90", "1.90"] : ["2.10", "3.40", "3.60"])}>{count === 2 ? "Tennis · 2 outcomes" : "Football · 3 outcomes"}</button>)}</div>
      <label>Removal method<select value={method} onChange={event => setMethod(event.target.value as DevigMethod)}><option value="proportional">Proportional</option><option value="shin">Shin</option><option value="oddsRatio">Odds ratio</option></select></label>
    </div>
    <div className="bm-odds-inputs">{prices.map((price, i) => <label key={i}>{labels[i]} odds<input type="number" inputMode="decimal" min="1.01" step="0.01" value={price} onChange={event => setPrices(prices.map((p, index) => index === i ? event.target.value : p))} /></label>)}</div>
    {result ? <div aria-live="polite">
      <div className="bm-margin-summary"><span>Book total <strong>{(total * 100).toFixed(2)}%</strong></span><span>Overround <strong>{overroundPct(values).toFixed(2)}%</strong></span><span>Normalised margin <strong>{marginOnTurnoverPct(values).toFixed(2)}%</strong></span></div>
      <div className="bm-fair-prices">{result.fairOdds.map((price, i) => <div key={i}><span>{labels[i]}</span><strong>{price.toFixed(3)}</strong><small>fair odds · {(result.probabilities[i] * 100).toFixed(1)}% probability</small></div>)}</div>
    </div> : <p className="bm-calculator-message" role="status">{!valid ? "Enter a decimal price greater than 1 for every outcome." : "These prices total less than 100%. Check that they come from one complete market before removing a margin."}</p>}
    <p className="bm-calculator-note">{method === "proportional" ? "Proportional removes the same share from every implied probability." : method === "shin" ? "Shin distributes the margin differently between the favourite and outsider." : "Odds ratio adjusts the prices using a shared odds ratio."} This is a market reference, not our prediction or proof of value. Different methods can give different answers.</p>
    <Link href="/calculator">Explore all calculators and methods ↗</Link>
  </section>;
}
