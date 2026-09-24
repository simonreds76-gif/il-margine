"use client";

import { useState } from "react";
import Link from "next/link";
import EditorialIcon from "@/components/EditorialIcon";
import type { DevigMethod } from "@/lib/calculator/math";
import { footballExpectedValue, footballFairPrices, type FootballMarket } from "@/lib/calculator/football";

const METHODS: { key: DevigMethod; label: string }[] = [
  { key: "proportional", label: "Proportional" }, { key: "shin", label: "Shin" }, { key: "oddsRatio", label: "Odds ratio" },
];
const MARKETS: { key: FootballMarket; label: string; short: string; detail: string }[] = [
  { key: "homeDraw", label: "Home or draw · 1X", short: "1X", detail: "Wins on home win or draw" },
  { key: "homeAway", label: "Either team wins · 12", short: "12", detail: "Loses if the match is drawn" },
  { key: "drawAway", label: "Draw or away · X2", short: "X2", detail: "Wins on draw or away win" },
  { key: "homeDnb", label: "Home · draw no bet", short: "Home DNB", detail: "Draw returns your stake" },
  { key: "awayDnb", label: "Away · draw no bet", short: "Away DNB", detail: "Draw returns your stake" },
];

export default function FootballPrices() {
  const [prices, setPrices] = useState(["2.00", "3.60", "4.50"]);
  const [method, setMethod] = useState<DevigMethod>("proportional");
  const [selection, setSelection] = useState<FootballMarket>("homeDnb");
  const [offered, setOffered] = useState("1.50");
  const result = footballFairPrices(prices.map(Number), method);
  const chosen = result?.markets[selection];
  const offeredNumber = Number(offered);
  const ev = chosen && Number.isFinite(offeredNumber) && offeredNumber > 1 && offeredNumber <= 1000 ? footballExpectedValue(chosen, offeredNumber) * 100 : null;
  return <div className="calc-panel football-price-tool">
    <header className="calc-panel-head"><div><p className="site-eyebrow">From three outcomes to one fair price</p><h2>What is the draw worth?</h2><p className="calc-lede">Enter home, draw and away prices from the same full-time market. The tool removes its margin before calculating double chance and draw no bet.</p></div><EditorialIcon name="football" className="h-14 w-14" /></header>
    <div className="football-price-layout">
      <div>
        <fieldset className="football-inputs"><legend>1. Enter the complete 1X2 market</legend>{["Home win", "Draw", "Away win"].map((label, i) => <label key={label} className="calc-field"><span className="calc-field-label">{label} odds</span><input className="calc-text-input" type="number" inputMode="decimal" min="1.001" max="1000" step="any" value={prices[i]} onChange={event => setPrices(prices.map((price, j) => j === i ? event.target.value : price))} /><small>{Number(prices[i]) > 1 && Number(prices[i]) <= 1000 ? `${(100 / Number(prices[i])).toFixed(2)}% implied before margin removal` : "Enter decimal odds above 1.00, up to 1,000"}</small></label>)}</fieldset>
        <fieldset className="football-methods"><legend>2. Choose a margin-removal method</legend><div className="calc-chip-row">{METHODS.map(entry => <button key={entry.key} type="button" className={`calc-chip${method === entry.key ? " is-active" : ""}`} aria-pressed={method === entry.key} onClick={() => setMethod(entry.key)}>{entry.label}</button>)}</div><p className="calc-note">Each method estimates probabilities differently. None reveals a certain true price. <Link href="/calculator?tool=margin" className="calc-link">Compare the methods</Link></p></fieldset>
      </div>
      <section className="football-price-results" aria-labelledby="football-prices-title" aria-live="polite">
        <div className="tools-section-head"><div><p className="site-eyebrow">Estimated fair decimal odds</p><h3 id="football-prices-title">The draw, accounted for.</h3></div></div>
        {result ? <>
          <div className="football-probabilities">{["Home", "Draw", "Away"].map((label, i) => <div key={label}><span>{label}</span><strong>{(result.probabilities[i] * 100).toFixed(1)}%</strong></div>)}</div>
          <p className="calc-note">Input book overround: {result.overround.toFixed(2)}% · {METHODS.find(entry => entry.key === method)?.label} removal</p>
          {result.overround < -0.001 && <p className="calc-alert">These prices total less than 100%. Check that they belong to the same market. Normalised estimates are shown; this is not a standard positive-margin book.</p>}
          <dl className="football-fair-list">{MARKETS.map(market => <div key={market.key}><dt>{market.label}<small>{market.detail}</small></dt><dd>{result.markets[market.key].fairOdds.toFixed(3)}</dd></div>)}</dl>
        </> : <p className="calc-alert" role="status">Enter all three valid decimal prices to see fair odds. No result is calculated from an incomplete market.</p>}
      </section>
    </div>
    <section className="calc-subcard football-value" aria-labelledby="football-value-title"><p className="site-eyebrow">3. Check the price you can take</p><h3 id="football-value-title">Is the offered price above your reference?</h3><div className="football-value-inputs"><label className="calc-field"><span className="calc-field-label">Market to compare</span><select className="calc-text-input" value={selection} onChange={event => setSelection(event.target.value as FootballMarket)}>{MARKETS.map(market => <option key={market.key} value={market.key}>{market.label}</option>)}</select></label><label className="calc-field"><span className="calc-field-label">Available bookmaker odds</span><input className="calc-text-input" type="number" min="1.001" max="1000" step="any" inputMode="decimal" value={offered} onChange={event => setOffered(event.target.value)} /></label></div>
      <div className="football-value-output" aria-live="polite"><div><span>Estimated fair price</span><strong>{chosen ? chosen.fairOdds.toFixed(3) : "—"}</strong></div><div><span>Expected net return per £10 staked</span><strong>{ev === null ? "—" : `${ev >= 0 ? "+" : "−"}£${Math.abs(ev / 10).toFixed(2)}`}</strong></div><div><span>Expected value</span><strong className={ev !== null && ev > 0 ? "gain" : ev !== null && ev < 0 ? "loss" : ""}>{ev === null ? "—" : `${ev > 0 ? "+" : ""}${ev.toFixed(2)}%`}</strong></div></div>
      <p className="calc-note">{chosen?.refund ? `A draw is a refund: its ${(chosen.refund * 100).toFixed(1)}% estimated probability contributes zero profit or loss. ` : ""}These are expectations against the selected reference, not a promised return. Match the selection and 90-minute settlement rules. The reference itself can be wrong.</p>
    </section>
  </div>;
}
