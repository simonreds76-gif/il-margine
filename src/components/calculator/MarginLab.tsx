"use client";

import { type CSSProperties, useId, useState } from "react";
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

// One colour per outcome, shared by the ledger key and both chart tracks.
const TONES = ["var(--nv-accent)", "var(--nv-ink)", "var(--nv-third)"];
const tone = (index: number) => ({ "--nv-c": TONES[index] }) as CSSProperties;

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
// Keeps long fair prices inside the narrow ledger column.
const fairPrice = (value: number) =>
  !Number.isFinite(value) ? "—" : value >= 1000 ? value.toFixed(0) : value >= 100 ? value.toFixed(2) : value.toFixed(3);

export default function MarginLab({ standalone = false }: { standalone?: boolean }) {
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

  const unit = isBook ? "%" : "¢";
  const hold = ready && isBook ? marginOnTurnoverPct(odds) : 0;
  const lead = !active
    ? null
    : isBook
      ? { label: overSign > 0 ? "Overround" : overSign < 0 ? "Below par" : "Even book", value: `${signed(over)}%` }
      : { label: overSign > 0 ? "Above $1" : overSign < 0 ? "Below $1" : "At $1", value: `${signed(over)}¢` };
  const side: Array<[string, string]> = !active
    ? []
    : isBook
      ? [
          ["Book total", `${total.toFixed(2)}%`],
          ["Theoretical hold", `${signed(hold)}%`],
        ]
      : [
          ["Ask total", `${total.toFixed(2)}¢`],
          ["Yes midpoint", `${((values[0] + 100 - values[1]) / 2).toFixed(2)}¢`],
        ];

  // Chart geometry. Both tracks share one scale that always includes par (100).
  const span = Math.max(100, total);
  const par = active ? (100 / span) * 100 : 100;
  const quoted = !active ? [] : isBook ? odds.map((price) => 100 / price) : values;
  const parState = !active ? "none" : overSign > 0 ? "over" : overSign < 0 ? "under" : "even";
  const chartLabel = !active
    ? "Chart of the entered prices against par. It appears once every price is valid."
    : `${
        isBook
          ? `As priced, the outcomes add up to ${total.toFixed(2)}% against a 100% book.`
          : `The two asks add up to ${total.toFixed(2)}¢ against a $1 payout.`
      } ${isBook ? `Fair, by ${chosen.label}` : "Share of ask total"}: ${names
        .map((name, index) => `${name} ${(active.probabilities[index] * 100).toFixed(2)}%`)
        .join(", ")}.`;

  const reading = !active || !isBook
    ? null
    : overSign > 0
      ? `As priced, these outcomes add up to ${total.toFixed(2)}%. The ${over.toFixed(2)} points above 100% are the bookmaker’s margin. With money balanced across every outcome, the book would keep about ${hold.toFixed(2)}% of turnover.`
      : overSign < 0
        ? `As priced, these outcomes add up to ${total.toFixed(2)}%, which is ${Math.abs(over).toFixed(2)} points short of 100%. There is no margin in these prices, and the fair figures are adjusted up to 100%. Check that every price is current and comes from the same market.`
        : "As priced, these outcomes add up to 100.00%. There is no margin to remove.";

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
  const evSign = ev === null ? 0 : Math.sign(Number(ev.toFixed(2)));

  return (
    <section className="nv" aria-labelledby={`${id}-title`}>
      <div className="nv-modes" role="group" aria-label="Calculator mode">
        {(["book", "market"] as const).map((key) => (
          <button key={key} type="button" className="nv-mode" aria-pressed={mode === key} onClick={() => setMode(key)}>
            {key === "book" ? "Bookmaker odds" : "Prediction market"}
          </button>
        ))}
      </div>

      <header className="nv-head">
        <div>
          <h2 id={`${id}-title`} className={standalone ? "nv-sr" : "nv-title"}>
            {isBook ? "Bookmaker’s margin" : "Yes and No contract prices"}
          </h2>
          <p className="nv-lede">
            {isBook
              ? "Enter decimal odds for every possible outcome of the same market, taken at the same time."
              : "Enter what it costs to buy Yes and No at the same moment. These contracts cover both outcomes. Exactly one pays $1."}
          </p>
        </div>
        {standalone ? null : (
          <Link href="/resources/odds-value-stakes#margin" className="nv-link">Work through a simple example</Link>
        )}
      </header>

      <div className="nv-band" data-par={parState}>
        <div className="nv-readout" aria-live="polite">
          {lead ? (
            <>
              <p className="nv-lead"><span>{lead.label}</span><strong>{lead.value}</strong></p>
              <dl className="nv-side">
                {side.map(([label, value]) => (
                  <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
                ))}
              </dl>
            </>
          ) : (
            <p className="nv-alert">
              <b>Waiting for prices</b>
              {isBook ? "Results appear once every outcome has decimal odds above 1.00." : "Results appear once both asks are above 0 and below 100 cents."}
            </p>
          )}
        </div>

        <div className="nv-book" role="img" aria-label={chartLabel}>
          <span className="nv-book-k nv-r1">{isBook ? "Priced" : "Asks"}</span>
          <div className="nv-plot nv-r1">
            {active ? (
              <>
                <div className="nv-track is-priced" style={{ width: `${(total / span) * 100}%` }}>
                  {quoted.map((value, index) => (
                    <i key={index} className="nv-seg" style={{ ...tone(index), width: `${(value / total) * 100}%` }} />
                  ))}
                </div>
                {overSign < 0 ? <i className="nv-short" style={{ width: `${100 - total}%` }} /> : null}
              </>
            ) : null}
          </div>
          <span className="nv-book-v nv-r1">{active ? `${total.toFixed(2)}${unit}` : "—"}</span>

          <span className="nv-book-k nv-r2">{isBook ? "Fair" : "Share"}</span>
          <div className="nv-plot nv-r2">
            {active ? (
              <div className="nv-track" style={{ width: `${par}%` }}>
                {active.probabilities.map((probability, index) => (
                  <i key={index} className="nv-seg" style={{ ...tone(index), width: `${probability * 100}%` }} />
                ))}
              </div>
            ) : null}
          </div>
          <span className="nv-book-v nv-r2">{active ? "100.00%" : "—"}</span>

          <div className={par < 50 ? "nv-par is-low" : "nv-par"} style={{ "--nv-par": `${par}%` } as CSSProperties}>
            <i />
            <span>{isBook ? "100% book" : "$1 payout"}</span>
          </div>
        </div>
      </div>

      <div className="nv-ledger">
        <div className="nv-cols" aria-hidden="true">
          <span className="nv-c-wide">Outcome</span>
          <span>{isBook ? "Your odds" : "Buy price"}</span>
          <span className="nv-c-wide">As priced</span>
          <span className="nv-c-num">Fair odds</span>
          <span className="nv-c-num">{isBook ? "Fair chance" : "Share"}</span>
        </div>
        {inputs.map((raw, index) => (
          <div className="nv-row" key={`${mode}-${index}`} style={tone(index)}>
            <label className="nv-name" htmlFor={`${id}-in-${index}`}>
              <i aria-hidden="true" />
              {names[index]}
              <span className="nv-sr">{" "}{isBook ? "decimal odds" : "buy price (¢)"}</span>
            </label>
            <input
              id={`${id}-in-${index}`}
              className="nv-input"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              value={raw}
              aria-invalid={!valid[index]}
              aria-describedby={`${id}-hint-${index}`}
              onChange={(event) => update(index, event.target.value)}
            />
            <small className={valid[index] ? "nv-hint" : "nv-hint is-bad"} id={`${id}-hint-${index}`}>
              {!valid[index]
                ? isBook ? "Enter decimal odds above 1.00" : "Enter cents above 0 and below 100"
                : isBook ? priceHint(values[index]) : `Equivalent decimal odds ${odds[index].toFixed(3)}`}
            </small>
            <p className="nv-fo">
              <span className="nv-sr">Fair decimal odds </span>
              {active ? fairPrice(active.fairOdds[index]) : "—"}
            </p>
            <p className="nv-fp">
              <span className="nv-sr">{isBook ? "Fair probability " : "Share of ask total "}</span>
              {active ? `${(active.probabilities[index] * 100).toFixed(2)}%` : "—"}
            </p>
          </div>
        ))}
      </div>

      {isBook ? (
        <div className="nv-controls">
          <button
            type="button"
            className="nv-ghost"
            onClick={() => (prices.length < 3 ? setPrices([...prices, "3.20"]) : resize(prices.slice(0, 2)))}
          >
            <span aria-hidden="true">{prices.length < 3 ? "+" : "−"}</span>
            {prices.length < 3 ? "Add third outcome" : "Remove third outcome"}
          </button>

          <div className="nv-group">
            <span className="nv-kick" aria-hidden="true">Method</span>
            <div className="nv-segd" role="group" aria-label="Margin removal method">
              {METHODS.map((entry) => (
                <button key={entry.key} type="button" className="nv-opt" aria-pressed={method === entry.key} onClick={() => setMethod(entry.key)}>{entry.label}</button>
              ))}
            </div>
          </div>

          <div className="nv-group nv-presets" role="group" aria-label="Example prices">
            <span className="nv-kick" aria-hidden="true">Examples</span>
            {PRESETS.map((preset) => (
              <button key={preset.label} type="button" className="nv-try" onClick={() => resize(preset.prices)}>{preset.label}</button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="nv-notes">
        {isBook ? (
          <p className="nv-note">
            <span className="nv-kick">{chosen.label} method</span>
            {chosen.blurb}
            {shinFallback ? " This book is below 100%, where our engine falls back to proportional for Shin." : ""}
          </p>
        ) : null}
        {reading ? (
          <p className="nv-note">
            <span className="nv-kick">This book</span>
            {reading}
          </p>
        ) : null}
        {!isBook && active ? (
          <p className="nv-note">
            <span className="nv-kick">These prices</span>
            Buying both sides costs {total.toFixed(2)}¢ against the $1 payout, fees excluded. We divide each buy price by that combined cost to estimate probabilities. On a single Yes/No order book, the No price implies a Yes bid of {(100 - values[1]).toFixed(2)}¢, {spreadNote}. The Yes midpoint sits halfway between the YES ask and that implied bid, so it can differ from the normalised estimate.
          </p>
        ) : null}
      </div>

      {isBook ? (
        <>
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
            <div className="nv-ev">
              <div className="nv-ev-in">
                <div className="nv-segd" role="group" aria-label="Outcome to test">
                  {names.map((name, index) => (
                    <button key={name} type="button" className="nv-opt" aria-pressed={pick === index} onClick={() => choose(index)}>{name}</button>
                  ))}
                </div>
                <label className="nv-field">
                  <span className="nv-label">Offered decimal odds for {names[pick]}</span>
                  <input className="nv-input" type="text" inputMode="decimal" autoComplete="off" value={offer} aria-invalid={!isOdds(offered)} onChange={(event) => setOffer(event.target.value)} />
                  <small className={isOdds(offered) ? "nv-hint" : "nv-hint is-bad"}>{isOdds(offered) ? priceHint(offered) : "Enter decimal odds above 1.00"}</small>
                </label>
              </div>
              <div className="nv-ev-out" aria-live="polite">
                {active && ev !== null ? (
                  <>
                    <p className="nv-ev-fig" data-sign={evSign}>
                      <span>Expected value</span>
                      <strong>{signed(ev)}%</strong>
                      <small>of stake</small>
                    </p>
                    <p className="nv-note">
                      Taking {offered.toFixed(2)} when the {chosen.label} fair decimal is {active.fairOdds[pick].toFixed(3)}. It is only as reliable as the fair estimate, and assumes the price is available under matching rules.
                    </p>
                  </>
                ) : (
                  <p className="nv-note">
                    {!active ? "Expected value needs valid market prices above." : "Enter offered decimal odds above 1.00 to see expected value."}
                  </p>
                )}
              </div>
            </div>
          </details>
        </>
      ) : null}
    </section>
  );
}
