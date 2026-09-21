"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatMoney } from "./Charts";
import {
  DevigMethod,
  closingLineValue,
  decimalToImplied,
  parseNumber,
} from "@/lib/calculator/math";

const METHOD_LABEL: Record<DevigMethod, string> = {
  proportional: "Proportional",
  shin: "Shin",
  oddsRatio: "Odds ratio",
};

export default function ClvLab() {
  const [taken, setTaken] = useState("2.10");
  const [closing, setClosing] = useState("1.95");
  const [closingOpposite, setClosingOpposite] = useState("1.95");
  const [method, setMethod] = useState<DevigMethod>("shin");
  const [stake, setStake] = useState("50");
  const [bets, setBets] = useState(200);

  const takenOdds = parseNumber(taken);
  const closingOdds = parseNumber(closing);
  const oppositeOdds = parseNumber(closingOpposite);
  const stakeValue = Math.max(0, parseNumber(stake));

  const result = useMemo(
    () => closingLineValue(takenOdds, closingOdds, oppositeOdds, method),
    [takenOdds, closingOdds, oppositeOdds, method]
  );

  const usable = takenOdds > 1 && closingOdds > 1 && oppositeOdds > 1;
  const projectedProfit = stakeValue * bets * (result.expectedValuePct / 100);
  const takenImplied = decimalToImplied(takenOdds) * 100;
  const closingImplied = decimalToImplied(closingOdds) * 100;
  const fairImplied = result.fairClosingProbability * 100;

  const scale = Math.max(takenImplied, closingImplied, fairImplied, 1) * 1.15;

  return (
    <div className="calc-panel">
      <header className="calc-panel-head">
        <div>
          <p className="site-eyebrow">Closing line value</p>
          <h2>Did the market move your way</h2>
          <p className="calc-lede">
            Results take hundreds of bets to say anything. The price you took against the price the
            market closed at says something after one. This tool removes the margin from the closing
            market first, so you are measured against a fair closing number rather than against a
            price that still has the book&apos;s cut inside it.
          </p>
        </div>
        <Link href="/resources/closing-line-value" className="calc-link">
          Read the CLV guide
        </Link>
      </header>

      <div className="calc-controls calc-controls-three">
        <label className="calc-field">
          <span className="calc-field-label">Price you took</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            min={1.01}
            value={taken}
            onChange={(event) => setTaken(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>{takenImplied.toFixed(2)}% implied</small>
        </label>
        <label className="calc-field">
          <span className="calc-field-label">Closing price, same selection</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            min={1.01}
            value={closing}
            onChange={(event) => setClosing(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>{closingImplied.toFixed(2)}% implied</small>
        </label>
        <label className="calc-field">
          <span className="calc-field-label">Closing price, other side</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            min={1.01}
            value={closingOpposite}
            onChange={(event) => setClosingOpposite(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>used to remove the closing margin</small>
        </label>
      </div>

      {!usable && <p role="alert" className="calc-alert">Enter all three decimal prices above 1 to calculate a fair closing comparison.</p>}
      <div hidden={!usable}>
      <div className="calc-chip-row">
        {(Object.keys(METHOD_LABEL) as DevigMethod[]).map((key) => (
          <button
            key={key}
            type="button"
            className={`calc-chip${method === key ? " is-active" : ""}`}
            onClick={() => setMethod(key)}
          >
            {METHOD_LABEL[key]}
          </button>
        ))}
      </div>

      <div className="calc-clv-visual">
        <div className="calc-clv-row">
          <span>Your price</span>
          <div className="calc-clv-track">
            <i style={{ width: `${(takenImplied / scale) * 100}%`, background: "linear-gradient(90deg,#2e947e,#7df4c9)" }} />
          </div>
          <strong>{takenImplied.toFixed(2)}%</strong>
        </div>
        <div className="calc-clv-row">
          <span>Fair close</span>
          <div className="calc-clv-track">
            <i style={{ width: `${(fairImplied / scale) * 100}%`, background: "linear-gradient(90deg,#33566b,#6fb6d8)" }} />
          </div>
          <strong>{fairImplied.toFixed(2)}%</strong>
        </div>
        <div className="calc-clv-row">
          <span>Closing price</span>
          <div className="calc-clv-track">
            <i style={{ width: `${(closingImplied / scale) * 100}%`, background: "linear-gradient(90deg,#4a4030,#eac77b)" }} />
          </div>
          <strong>{closingImplied.toFixed(2)}%</strong>
        </div>
        <p className="calc-note">
          Shorter bar is a better price. If your bar is shorter than the fair close, you bought the
          selection below what the market finished up thinking it was worth.
        </p>
      </div>

      <div className="calc-metrics" aria-live="polite">
        <div className="calc-metric is-accent">
          <span>Closing line value</span>
          <strong className={result.probabilityClvPct >= 0 ? "gain" : "loss"}>
            {result.probabilityClvPct >= 0 ? "+" : ""}
            {result.probabilityClvPct.toFixed(2)}%
          </strong>
          <small>against the de-vigged closing market</small>
        </div>
        <div className="calc-metric">
          <span>Price movement</span>
          <strong className={result.priceClvPct >= 0 ? "gain" : "loss"}>
            {result.priceClvPct >= 0 ? "+" : ""}
            {result.priceClvPct.toFixed(2)}%
          </strong>
          <small>{result.beatTheClose ? "you beat the close" : "the close beat you"}</small>
        </div>
        <div className="calc-metric">
          <span>Expected value</span>
          <strong className={result.expectedValuePct >= 0 ? "gain" : "loss"}>
            {result.expectedValuePct >= 0 ? "+" : ""}
            {result.expectedValuePct.toFixed(2)}%
          </strong>
          <small>if the fair close is the true probability</small>
        </div>
        <div className="calc-metric">
          <span>Over {bets} bets at {formatMoney(stakeValue)}</span>
          <strong className={projectedProfit >= 0 ? "gain" : "loss"}>
            {projectedProfit >= 0 ? "+" : ""}
            {formatMoney(projectedProfit)}
          </strong>
          <small>before variance, before limits</small>
        </div>
      </div>

      <div className="calc-controls">
        <label className="calc-field">
          <span className="calc-field-label">Stake per bet</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={stake}
            onChange={(event) => setStake(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
        </label>
        <label className="calc-field">
          <span className="calc-field-label">
            Bets at this CLV <strong>{bets}</strong>
          </span>
          <input
            type="range"
            min={20}
            max={1000}
            step={20}
            value={bets}
            onChange={(event) => setBets(Number(event.target.value))}
          />
        </label>
      </div>

      </div>
      <p className="calc-note calc-note-block">
        Two cautions. Closing line value only means something against a market that is genuinely
        sharp at the off, which for player props is often a single reference book rather than the
        whole market. And a consistent positive number against a soft closing line tells you the book
        was slow, not that your model was right.
      </p>
    </div>
  );
}
