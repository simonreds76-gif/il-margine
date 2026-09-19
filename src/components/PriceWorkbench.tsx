"use client";

import { useState } from "react";

/** An illustrative price comparison, entirely in the browser. */
export default function PriceWorkbench() {
  const [chance, setChance] = useState(40);
  const [odds, setOdds] = useState(2.75);
  const fair = 100 / chance;
  const ev = chance / 100 * odds - 1;
  const breakEven = 100 / odds;
  const points = Array.from({ length: 51 }, (_, i) => {
    const price = 1.5 + i / 10;
    const value = chance / 100 * price - 1;
    return `${50 + i * 8.6},${200 - value * 40}`;
  }).join(" ");
  return <section className="price-workbench" aria-labelledby="price-workbench-title">
    <div className="workbench-controls">
      <p className="site-eyebrow">Try the price · illustrative example</p>
      <h2 id="price-workbench-title">Same player.<br /><span>Different value.</span></h2>
      <p>Move the sliders. See how the price changes the potential return, even when your view of the player stays the same.</p>
      <label htmlFor="model-chance">Estimated scoring chance <strong>{chance}%</strong></label>
      <input id="model-chance" type="range" min="15" max="70" step="1" value={chance} onChange={e => setChance(Number(e.target.value))} />
      <label htmlFor="offered-price">Bookmaker decimal odds <strong>{odds.toFixed(2)}</strong></label>
      <input id="offered-price" type="range" min="1.5" max="6.5" step="0.05" value={odds} onChange={e => setOdds(Number(e.target.value))} />
      <p className="workbench-footnote">An example, not a forecast or a bet recommendation. An inaccurate probability can turn apparent value into a loss.</p>
    </div>
    <div className="workbench-chart">
      <div className="workbench-metrics" aria-live="polite"><div><span>Model fair odds</span><strong>{fair.toFixed(2)}</strong></div><div><span>Estimated return / £1</span><strong className={ev >= 0 ? "gain" : "loss"}>{ev >= 0 ? "+" : "−"}{Math.abs(ev * 100).toFixed(1)}p</strong></div></div>
      <svg viewBox="0 0 530 260" role="img" aria-label={`Estimated return rises as odds rise. At ${odds.toFixed(2)}, estimated return is ${(ev * 100).toFixed(1)} percent. Break-even odds are ${fair.toFixed(2)}.`}>
        <defs><linearGradient id="price-line" x1="0" x2="1"><stop offset="0" stopColor="#f5bb82" /><stop offset="1" stopColor="#64e5b7" /></linearGradient></defs>
        {[70, 135, 200].map(y => <line key={y} x1="50" y1={y} x2="480" y2={y} stroke="#ffffff12" />)}
        <line x1="50" y1="200" x2="480" y2="200" stroke="#b3c4cd" strokeDasharray="4 6" />
        <text x="50" y="188" fill="#a8b9c5" fontSize="12">Break-even · 0%</text>
        <text x="50" y="30" fill="#a8b9c5" fontSize="12">Estimated return per £1 staked</text>
        <polyline points={points} fill="none" stroke="url(#price-line)" strokeWidth="3" />
        <line x1={50 + (odds - 1.5) * 86} y1={200 - ev * 40} x2={50 + (odds - 1.5) * 86} y2="232" stroke="#72dec0" strokeDasharray="3 5" />
        <circle cx={50 + (odds - 1.5) * 86} cy={200 - ev * 40} r="7" fill="#7df4c9" stroke="#122b29" strokeWidth="3" />
        <text x="50" y="251" fill="#a8b9c5" fontSize="12">1.50</text><text x="265" y="251" fill="#a8b9c5" fontSize="12" textAnchor="middle">Bookmaker decimal odds →</text><text x="480" y="251" fill="#a8b9c5" fontSize="12" textAnchor="end">6.50</text>
      </svg>
      <div className="workbench-equation"><span>{chance}% estimated chance</span><span>vs</span><span>{breakEven.toFixed(1)}% needed to break even</span></div>
      <p>Expected return = estimated chance × decimal odds − 1. This graph shows the arithmetic, not historical results.</p>
    </div>
  </section>;
}
