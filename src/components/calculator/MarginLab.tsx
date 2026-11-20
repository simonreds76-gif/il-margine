"use client";

import { useId, useState } from "react";
import Link from "next/link";
import {
  type DevigMethod,
  bookSum,
  decimalToAmerican,
  decimalToFractional,
  devig,
  expectedValue,
  marginOnTurnoverPct,
  overroundPct,
  parseNumber,
} from "@/lib/calculator/math";
import "./no-vig.css";

type Mode = "book" | "market";

const METHODS: Array<{ key: DevigMethod; label: string; symbol: string; blurb: string }> = [
  { key: "proportional", label: "Proportional", symbol: "divisor", blurb: "Divides each implied probability by the book total. Every probability falls by the same proportion in an overround book." },
  { key: "shin", label: "Shin", symbol: "z", blurb: "Loads more margin onto longer prices under the Shin model. The fitted parameter z appears in the method comparison." },
  { key: "oddsRatio", label: "Odds ratio", symbol: "c", blurb: "Holds the odds ratio between offered and fair price at one constant c across outcomes." },
];

const PRESETS = [
  { label: "Even two-way", prices: ["1.90", "1.90"] },
  { label: "Tennis favourite", prices: ["1.28", "3.75"] },
  { label: "Shots line", prices: ["1.83", "1.95"] },
  { label: "Three-way match odds", prices: ["2.30", "3.40", "3.10"] },
];

const NUMERIC = /^\d+(?:[.,]\d+)?$/;
const read = (raw: string) => {
  const text = raw.trim();
  return NUMERIC.test(text) ? parseNumber(text.replace(",", ".")) : NaN;
};
const isOdds = (value: number) => Number.isFinite(value) && value > 1;
const isCents = (value: number) => Number.isFinite(value) && value > 0 && value < 100;
const signed = (value: number) => {
  const rounded = Number(value.toFixed(2));
  return `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(rounded).toFixed(2)}`;
};
const priceHint = (odds: number) => {
  const american = decimalToAmerican(odds);
  return `${(100 / odds).toFixed(2)}% implied · ${decimalToFractional(odds)} · ${american > 0 ? "+" : ""}${american}`;
};

export default function MarginLab() {
  const id = useId();
  const [mode, setMode] = useState<Mode>("book");
  const [prices, setPrices] = useState<string[]>(PRESETS[0].prices);
  const [asks, setAsks] = useState<string[]>(["62", "42"]);
  const [method, setMethod] = useState<DevigMethod>("shin");
  const [pick, setPick] = useState(0);
  const [offer, setOffer] = useState(PRESETS[0].prices[0]);

  const isBook = mode === "book";
  const inputs = isBook ? prices : asks;
  const names = isBook ? prices.map((_, index) => `Outcome ${index + 1}`) : ["YES", "NO"];
  const values = inputs.map(read);
  const valid = values.map(isBook ? isOdds : isCents);
  const ready = valid.every(Boolean);
  const odds = isBook ? values : values.map((cents) => 100 / cents);

  const chosen = METHODS.find((entry) => entry.key === (isBook ? method : "proportional")) ?? METHODS[0];
  const fits = (ready ? METHODS.filter((entry) => isBook || entry.key === "proportional") : []).map((entry) => ({
    ...entry,
    ...devig(odds, entry.key),
  }));
  const active = fits.find((fit) => fit.key === chosen.key);

  const total = !ready ? 0 : isBook ? bookSum(odds) * 100 : values[0] + values[1];
  const over = !ready ? 0 : isBook ? overroundPct(odds) : total - 100;
  const overSign = Math.sign(Number(over.toFixed(2)));
  const shinFallback = isBook && ready && total < 100 - 1e-7;
  const parameter = (fit: { key: DevigMethod; symbol: string; parameter: number }) =>
    shinFallback && fit.key === "shin" ? "proportional fallback" : `${fit.symbol} ${fit.parameter.toFixed(4)}`;

  const metrics: Array<[string, string, string]> = !active
    ? []
    : isBook
      ? [
          ["Book total", `${total.toFixed(2)}%`, "sum of implied probabilities"],
          [overSign > 0 ? "Overround" : overSign < 0 ? "Below par" : "Even book", `${signed(over)}%`, "against a 100% book"],
          ["Theoretical hold", `${signed(marginOnTurnoverPct(odds))}%`, "estimated share of balanced turnover"],

        ]
      : [
          ["Ask total", `${total.toFixed(2)}¢`, "combined cost to buy both sides"],
          [overSign > 0 ? "Above $1" : overSign < 0 ? "Below $1" : "At $1", `${signed(over)}¢`, "ask total against the $1 payout, fees excluded"],
          ["Yes midpoint", `${((values[0] + 100 - values[1]) / 2).toFixed(2)}¢`, "between the YES ask and 100 minus the NO ask"],
        ];

  const spreadNote =
    overSign > 0
      ? `so the ${over.toFixed(2)}¢ above $1 is the bid/ask spread seen across the two sides`
      : overSign < 0
        ? "so the two prices cross. Check the time, available size and settlement rules"
        : "so asks that total exactly $1 leave no spread between the two sides";

  const update = (index: number, value: string) =>
    (isBook ? setPrices : setAsks)((current) => current.map((entry, i) => (i === index ? value : entry)));
  const choose = (index: number, source: string[] = prices) => {
    setPick(index);
    setOffer(source[index]);
  };
  const resize = (next: string[]) => {
    setPrices(next);
    choose(0, next);
  };

  const offered = read(offer);
  const ev = isBook && active && isOdds(offered) ? expectedValue(offered, active.probabilities[pick]) * 100 : null;

  return (
    <section className="nv" aria-labelledby={`${id}-title`}>
      <header className="nv-head">
        <div>
          <h2 id={`${id}-title`}>{isBook ? "Bookmaker’s margin" : "Yes and No contract prices"}</h2>
          <p className="nv-lede">
            {isBook
              ? "Enter decimal odds for every possible outcome of the same market, taken at the same time."
              : "Enter what it costs to buy Yes and No at the same moment. These contracts cover both outcomes. Exactly one pays $1."}
          </p>
        </div>
        <Link href="/resources/odds-value-stakes#margin" className="nv-link">Work through a simple example</Link>
      </header>

      <div className="nv-seg" role="group" aria-label="Calculator mode">
        {(["book", "market"] as const).map((key) => (
          <button key={key} type="button" className="nv-btn" aria-pressed={mode === key} onClick={() => setMode(key)}>
            {key === "book" ? "Bookmaker odds" : "Prediction market"}
          </button>
        ))}
      </div>

      {isBook ? (
        <div className="nv-seg" role="group" aria-label="Example prices">
          {PRESETS.map((preset) => (
            <button key={preset.label} type="button" className="nv-btn" onClick={() => resize(preset.prices)}>{preset.label}</button>
          ))}
        </div>
      ) : null}

      <div className="nv-rows">
        {inputs.map((raw, index) => (
          <div className="nv-row" key={`${mode}-${index}`}>
            <label className="nv-field">
              <span className="nv-label">{names[index]} {isBook ? "decimal odds" : "buy price (¢)"}</span>
              <input
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={raw}
                aria-invalid={!valid[index]}
                aria-describedby={`${id}-hint-${index}`}
                onChange={(event) => update(index, event.target.value)}
              />
              <small id={`${id}-hint-${index}`}>
                {!valid[index]
                  ? isBook ? "Enter decimal odds above 1.00" : "Enter cents above 0 and below 100"
                  : isBook ? priceHint(values[index]) : `Equivalent decimal odds ${odds[index].toFixed(3)}`}
              </small>
            </label>
            {active ? (
              <div className="nv-fair">
                <p><span>{isBook ? "Fair probability" : "Share of ask total"}</span><strong>{(active.probabilities[index] * 100).toFixed(2)}%</strong></p>
                <p><span>Fair decimal odds</span><strong>{active.fairOdds[index].toFixed(3)}</strong></p>
                <span className="nv-bar" aria-hidden="true"><i style={{ width: `${active.probabilities[index] * 100}%` }} /></span>
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {isBook ? (
        <div className="nv-seg">
          <button type="button" className="nv-btn" onClick={() => (prices.length < 3 ? setPrices([...prices, "3.20"]) : resize(prices.slice(0, 2)))}>
            {prices.length < 3 ? "Add third outcome" : "Remove third outcome"}
          </button>
        </div>
      ) : null}

      <div className="nv-metrics" aria-live="polite">
        {metrics.map(([label, value, note]) => (
          <p className="nv-metric" key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></p>
        ))}
        {!ready ? (
          <p className="nv-alert">
            {isBook ? "Results appear once every outcome has decimal odds above 1.00." : "Results appear once both asks are above 0 and below 100 cents."}
          </p>
        ) : null}
      </div>

      {isBook ? (
        <>
          <div className="nv-seg" role="group" aria-label="Margin removal method">
            {METHODS.map((entry) => (
              <button key={entry.key} type="button" className="nv-btn" aria-pressed={method === entry.key} onClick={() => setMethod(entry.key)}>{entry.label}</button>
            ))}
          </div>
          <p className="nv-note">
            {chosen.blurb}
            {shinFallback ? " This book is below 100%, where our engine falls back to proportional for Shin." : ""}
          </p>

          {active ? (
            <details className="nv-adv">
              <summary>Compare the three methods</summary>
              <div className="nv-scroll" role="region" aria-label="Fair price by method" tabIndex={0}>
              <table className="nv-table">
                <caption>Fair probability and fair decimal by method</caption>
                <thead>
                  <tr>
                    <th scope="col">Outcome</th>
                    <th scope="col">Offered</th>
                    {fits.map((fit) => <th key={fit.key} scope="col" className={fit.key === method ? "is-on" : undefined}>{fit.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {odds.map((price, index) => (
                    <tr key={names[index]}>
                      <th scope="row">{names[index]}</th>
                      <td>{price.toFixed(2)}</td>
                      {fits.map((fit) => (
                        <td key={fit.key} className={fit.key === method ? "is-on" : undefined}>
                          {(fit.probabilities[index] * 100).toFixed(2)}%<span>{fit.fairOdds[index].toFixed(3)}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr>
                    <th scope="row">Parameter</th>
                    <td />
                    {fits.map((fit) => <td key={fit.key} className={fit.key === method ? "is-on" : undefined}>{parameter(fit)}</td>)}
                  </tr>
                </tbody>
              </table>
              </div>
            </details>
          ) : null}

          <details className="nv-adv">
            <summary>Test odds you can get</summary>
            <div className="nv-adv-grid">
              <div className="nv-seg" role="group" aria-label="Outcome to test">
                {names.map((name, index) => (
                  <button key={name} type="button" className="nv-btn" aria-pressed={pick === index} onClick={() => choose(index)}>{name}</button>
                ))}
              </div>
              <label className="nv-field">
                <span className="nv-label">Offered decimal odds for {names[pick]}</span>
                <input type="text" inputMode="decimal" autoComplete="off" value={offer} aria-invalid={!isOdds(offered)} onChange={(event) => setOffer(event.target.value)} />
                <small>{isOdds(offered) ? priceHint(offered) : "Enter decimal odds above 1.00"}</small>
              </label>
              <p className="nv-note" aria-live="polite">
                {!active
                  ? "Expected value needs valid market prices above."
                  : ev === null
                    ? "Enter offered decimal odds above 1.00 to see expected value."
                    : `At ${offered.toFixed(2)} against the ${chosen.label} fair decimal of ${active.fairOdds[pick].toFixed(3)}, expected value is ${signed(ev)}% of stake. It is only as reliable as the fair estimate, and assumes the price is available under matching rules.`}
              </p>
            </div>
          </details>
        </>
      ) : active ? (
        <p className="nv-note">
          We divide each buy price by their combined cost to estimate probabilities. On a single Yes/No order book, the No price implies a Yes bid of {(100 - values[1]).toFixed(2)}¢, {spreadNote}. Fees are excluded. The midpoint uses a different calculation and can differ from the normalised estimate.
        </p>
      ) : null}
    </section>
  );
}
