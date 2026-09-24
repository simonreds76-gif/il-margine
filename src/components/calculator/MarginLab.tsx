"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { MarginBar } from "./Charts";
import {
  DevigMethod,
  bookSum,
  decimalToAmerican,
  decimalToFractional,
  devig,
  expectedValue,
  marginOnTurnoverPct,
  overroundPct,
  parseNumber,
} from "@/lib/calculator/math";

const METHODS: Array<{ key: DevigMethod; label: string; blurb: string }> = [
  {
    key: "proportional",
    label: "Proportional",
    blurb:
      "Divides every implied probability by the book total. Quick, and it charges the outsider the same share of margin as the favourite, a transparent starting assumption.",
  },
  {
    key: "shin",
    label: "Shin",
    blurb:
      "Treats margin as cover against better-informed money. It loads more of the margin onto the longer price, under the assumptions of the Shin model. For two outcomes it matches additive removal.",
  },
  {
    key: "oddsRatio",
    label: "Odds ratio",
    blurb:
      "Holds the odds ratio between offered and fair price constant across outcomes. It can produce a different estimate from both other methods.",
  },
];

const OUTCOME_COLOURS = ["#3f87ab", "#2e947e", "#7a6fb0"];

const PRESETS = [
  { label: "Even two-way", prices: ["1.90", "1.90"] },
  { label: "Tennis favourite", prices: ["1.28", "3.75"] },
  { label: "Shots line", prices: ["1.83", "1.95"] },
  { label: "Three-way match odds", prices: ["2.30", "3.40", "3.10"] },
];

export default function MarginLab() {
  const [prices, setPrices] = useState<string[]>(["1.90", "1.90"]);
  const [method, setMethod] = useState<DevigMethod>("shin");
  const [yourPrice, setYourPrice] = useState("1.90");
  const [outcome, setOutcome] = useState(0);
  const selectedOutcome = Math.min(outcome, prices.length - 1);

  const numeric = prices.map((price) => parseNumber(price));
  const usable = numeric.length >= 2 && numeric.every((price) => price > 1);

  const result = useMemo(
    () => (usable ? devig(numeric, method) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [prices, method]
  );

  const comparison = useMemo(() => {
    if (!usable) return null;
    return METHODS.map((entry) => ({
      key: entry.key,
      label: entry.label,
      fair: devig(numeric, entry.key).fairOdds,
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prices]);

  const total = usable ? bookSum(numeric) * 100 : 0;
  const margin = usable ? overroundPct(numeric) : 0;
  const turnoverMargin = usable ? marginOnTurnoverPct(numeric) : 0;

  const yourOdds = parseNumber(yourPrice);
  const fairFirst = result ? result.probabilities[selectedOutcome] : 0;
  const edgePct = result && yourOdds > 1 ? expectedValue(yourOdds, fairFirst) * 100 : 0;

  const applyPreset = (presetPrices: string[]) => {
    setPrices(presetPrices);
    setOutcome(0);
    setYourPrice(presetPrices[0]);
  };

  const updatePrice = (index: number, value: string) => {
    setPrices((current) => current.map((price, i) => (i === index ? value : price)));
  };

  return (
    <div className="calc-panel">
      <header className="calc-panel-head">
        <div>
          <p className="site-eyebrow">Mind the margin</p>
          <h2>Strip the margin out of a price</h2>
          <p className="calc-lede">
            A posted price includes the book&apos;s margin. Removing that margin gives
            an estimated market probability to compare with your own assessment. Three removal methods are shown because they disagree, and the disagreement is
            worth checking. Start with the prices, then choose the outcome and available odds to compare below.
          </p>
        </div>
        <Link href="/resources/odds-value-stakes#margin" className="calc-link">
          Work through a simple example
        </Link>
      </header>

      <div className="calc-chip-row calc-preset-row">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="calc-chip"
            onClick={() => applyPreset(preset.prices)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="calc-price-grid">
        {prices.map((price, index) => (
          <label key={`outcome-${index}`} className="calc-field">
            <span className="calc-field-label">Outcome {index + 1} price</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min={1.01}
              value={price}
              onChange={(event) => updatePrice(index, event.target.value)}
              onFocus={(event) => event.target.select()}
              className="calc-text-input"
            />
            <small>
              {parseNumber(price) > 1
                ? `${(100 / parseNumber(price)).toFixed(2)}% implied, ${decimalToFractional(parseNumber(price))}, ${decimalToAmerican(parseNumber(price)) > 0 ? "+" : ""}${decimalToAmerican(parseNumber(price))}`
                : "Enter a decimal price above 1.00"}
            </small>
          </label>
        ))}
        <div className="calc-price-actions">
          {prices.length < 3 ? (
            <button type="button" className="calc-chip" onClick={() => setPrices([...prices, "3.20"])}>
              Add outcome
            </button>
          ) : null}
          {prices.length > 2 ? (
            <button type="button" className="calc-chip" onClick={() => { setPrices(prices.slice(0, -1)); setOutcome(0); setYourPrice(prices[0]); }}>
              Remove outcome
            </button>
          ) : null}
        </div>
      </div>

      {usable && result ? (
        <>
          <div className="calc-metrics" aria-live="polite">
            <div className="calc-metric">
              <span>Book total</span>
              <strong>{total.toFixed(2)}%</strong>
              <small>sum of implied probabilities</small>
            </div>
            <div className="calc-metric is-accent">
              <span>Overround</span>
              <strong className="loss">{margin.toFixed(2)}%</strong>
              <small>above a fair 100% book</small>
            </div>
            <div className="calc-metric">
              <span>Margin on turnover</span>
              <strong>{turnoverMargin.toFixed(2)}%</strong>
              <small>theoretical balanced-book hold, not realised profit</small>
            </div>
            <div className="calc-metric">
              <span>{method === "shin" ? "Shin z" : method === "oddsRatio" ? "Odds ratio c" : "Book divisor"}</span>
              <strong>{result.parameter.toFixed(4)}</strong>
              <small>
                {method === "shin"
                  ? "fitted model parameter, not observed insider activity"
                  : method === "oddsRatio"
                    ? "constant applied across outcomes"
                    : "every probability divided by this"}
              </small>
            </div>
          </div>

          <MarginBar
            marginPct={margin}
            segments={result.probabilities.map((probability, index) => ({
              label: `Outcome ${index + 1}`,
              fairPct: probability * 100,
              marginPct: 0,
              colour: OUTCOME_COLOURS[index % OUTCOME_COLOURS.length],
            }))}
          />

          <div className="calc-method-row">
            {METHODS.map((entry) => (
              <button
                key={entry.key}
                type="button"
                className={`calc-method${method === entry.key ? " is-active" : ""}`}
                onClick={() => setMethod(entry.key)}
              >
                <strong>{entry.label}</strong>
                <span>{entry.blurb}</span>
              </button>
            ))}
          </div>

          <div className="calc-subcard">
            <p className="site-eyebrow">Fair price by method</p>
            <div className="calc-table-scroll" role="region" aria-label="Fair odds comparison by method" tabIndex={0}><table className="calc-table">
              <thead>
                <tr>
                  <th scope="col">Outcome</th>
                  <th scope="col">Offered</th>
                  {comparison?.map((entry) => (
                    <th key={entry.key} scope="col">
                      {entry.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {numeric.map((price, index) => (
                  <tr key={`row-${index}`}>
                    <th scope="row">Outcome {index + 1}</th>
                    <td>{price.toFixed(2)}</td>
                    {comparison?.map((entry) => (
                      <td key={`${entry.key}-${index}`} className={entry.key === method ? "is-active" : ""}>
                        {entry.fair[index].toFixed(3)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table></div>
            <p className="calc-note">
              On a balanced pair the methods agree closely. On an uneven market their differences can
              be large enough to change an apparent edge. Keep the method alongside the estimate.
            </p>
          </div>

          <label className="calc-field"><span className="calc-field-label">Outcome to compare</span><select className="calc-text-input" value={selectedOutcome} onChange={event => { const index = Number(event.target.value); setOutcome(index); setYourPrice(prices[index]); }}>{prices.map((_, index) => <option key={index} value={index}>Outcome {index + 1}</option>)}</select></label>
          <div className="calc-edge-check">
            <label className="calc-field">
              <span className="calc-field-label">Best price you can actually get on outcome {selectedOutcome + 1}</span>
              <input
                type="number"
                inputMode="decimal"
                step="0.01"
                min={1.01}
                value={yourPrice}
                onChange={(event) => setYourPrice(event.target.value)}
                onFocus={(event) => event.target.select()}
                className="calc-text-input"
              />
            </label>
            <div className="calc-edge-readout" aria-live="polite">
              <span>Fair price, {METHODS.find((entry) => entry.key === method)?.label.toLowerCase()}</span>
              <strong>{result.fairOdds[selectedOutcome].toFixed(3)}</strong>
              <span>Expected value at your price</span>
              <strong className={edgePct >= 0 ? "gain" : "loss"}>
                {edgePct >= 0 ? "+" : ""}
                {edgePct.toFixed(2)}%
              </strong>
              <p>
                {edgePct > 0
                  ? "Positive against this estimated reference. That is useful only if the probability estimate is credible and the offered odds are available under matching rules."
                  : "This price does not beat the selected fair reference. The estimate can still be wrong; a fair price is not a guaranteed outcome."}
              </p>
            </div>
          </div>
        </>
      ) : (
        <p className="calc-alert">Enter at least two decimal prices above 1.00 to remove the margin.</p>
      )}
    </div>
  );
}
