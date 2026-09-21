"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  FRACTION_COLOURS,
  GrowthCurve,
  MultiLineChart,
  RangeBars,
  formatMoney,
} from "./Charts";
import {
  decimalToImplied,
  expectedValue,
  growthRate,
  kellyFraction,
  parseNumber,
  simulateKelly,
} from "@/lib/calculator/math";

const FRACTIONS = [
  { value: 0.1, label: "0.1x", context: "Player props" },
  { value: 0.25, label: "0.25x", context: "Tennis" },
  { value: 0.5, label: "0.5x", context: "Aggressive" },
  { value: 1, label: "1x", context: "Full Kelly" },
] as const;

export default function KellyLab() {
  const [bankrollInput, setBankrollInput] = useState("2500");
  const [oddsInput, setOddsInput] = useState("2.10");
  const [probabilityInput, setProbabilityInput] = useState("54");
  const [fraction, setFraction] = useState<number>(0.25);
  const [estimateError, setEstimateError] = useState(0);
  const [bets, setBets] = useState(250);

  const bankroll = Math.max(0, parseNumber(bankrollInput));
  const odds = parseNumber(oddsInput);
  const estimated = Math.min(99, Math.max(1, parseNumber(probabilityInput))) / 100;
  const truth = Math.min(0.99, Math.max(0.01, estimated - estimateError / 100));

  const impliedProbability = decimalToImplied(odds);
  const fullKelly = kellyFraction(odds, estimated);
  const stakeShare = fullKelly * fraction;
  const stake = bankroll * stakeShare;
  const edgePoints = (estimated - impliedProbability) * 100;
  const evClaimed = expectedValue(odds, estimated) * 100;
  const evTrue = expectedValue(odds, truth) * 100;
  const hasEdge = fullKelly > 0;

  const runs = useMemo(
    () =>
      FRACTIONS.map((preset) =>
        simulateKelly({
          bankroll: bankroll,
          odds,
          estimatedProbability: estimated,
          trueProbability: truth,
          fraction: preset.value,
          bets,
          paths: 400,
          seed: 8675309,
        })
      ),
    [bankroll, odds, estimated, truth, bets]
  );

  const activeIndex = FRACTIONS.findIndex((preset) => preset.value === fraction);
  const active = runs[activeIndex];

  const growthPoints = useMemo(() => {
    const points: Array<{ f: number; g: number }> = [];
    for (let multiple = 0; multiple <= 2.2; multiple += 0.02) {
      const share = Math.min(fullKelly * multiple, 0.98);
      points.push({ f: multiple, g: share <= 0 ? 0 : growthRate(odds > 1 ? odds : 2.1, truth, share) });
    }
    return points;
  }, [fullKelly, odds, truth]);

  const growthMarkers = FRACTIONS.map((preset) => ({
    f: preset.value,
    g: growthRate(odds > 1 ? odds : 2.1, truth, Math.min(fullKelly * preset.value, 0.98)),
    label: preset.label,
    colour: FRACTION_COLOURS[preset.label],
    active: preset.value === fraction,
  }));

  return (
    <div className="calc-panel">
      <header className="calc-panel-head">
        <div>
          <p className="site-eyebrow">Stake sizing</p>
          <h2>Kelly, and the reason we cut it</h2>
          <p className="calc-lede">
            Kelly gives the stake that maximises long-run growth when your probability is right. The
            interesting question is what happens when it is not, so this tool sizes stakes from the
            number you believe and settles them at a number you can be wrong about.
          </p>
        </div>
        <Link href="/resources/kelly-criterion-sports-betting" className="calc-link">
          Read the full Kelly guide
        </Link>
      </header>

      <div className="calc-controls calc-controls-three">
        <label className="calc-field">
          <span className="calc-field-label">Bankroll (GBP)</span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={bankrollInput}
            onChange={(event) => setBankrollInput(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
        </label>
        <label className="calc-field">
          <span className="calc-field-label">Decimal odds</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.01"
            min={1.01}
            value={oddsInput}
            onChange={(event) => setOddsInput(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>Implied {(impliedProbability * 100).toFixed(1)}% before margin</small>
        </label>
        <label className="calc-field">
          <span className="calc-field-label">Your win probability (%)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.5"
            min={1}
            max={99}
            value={probabilityInput}
            onChange={(event) => setProbabilityInput(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>
            Edge {edgePoints >= 0 ? "+" : ""}
            {edgePoints.toFixed(1)} points, expected value {evClaimed >= 0 ? "+" : ""}
            {evClaimed.toFixed(1)}%
          </small>
        </label>
      </div>

      <fieldset className="calc-field calc-field-wide">
        <legend>Kelly fraction</legend>
        <div className="calc-fraction-row">
          {FRACTIONS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`calc-fraction${fraction === preset.value ? " is-active" : ""}`}
              onClick={() => setFraction(preset.value)}
              style={{ borderColor: fraction === preset.value ? FRACTION_COLOURS[preset.label] : undefined }}
            >
              <strong style={{ color: FRACTION_COLOURS[preset.label] }}>{preset.label}</strong>
              <span>{preset.context}</span>
            </button>
          ))}
        </div>
      </fieldset>

      <div className="calc-stake-row" aria-live="polite">
        <div className="calc-stake-primary">
          <span>Recommended stake</span>
          <strong className={hasEdge ? "gain" : ""}>{hasEdge ? formatMoney(stake) : "No bet"}</strong>
          <small>
            {hasEdge
              ? `${(stakeShare * 100).toFixed(2)}% of bankroll, ${fraction}x of a ${(fullKelly * 100).toFixed(1)}% full Kelly stake`
              : "At this price your probability does not clear the market. Kelly returns a stake of zero."}
          </small>
        </div>
        <div className="calc-stake-secondary">
          <div>
            <span>Full Kelly stake</span>
            <strong>{formatMoney(bankroll * fullKelly)}</strong>
            <small>{(fullKelly * 100).toFixed(1)}% of bankroll</small>
          </div>
          <div>
            <span>Growth per bet</span>
            <strong>{(active ? active.growthPerBet * 100 : 0).toFixed(3)}%</strong>
            <small>expected log growth at this fraction</small>
          </div>
        </div>
      </div>

      <div className="calc-error-dial">
        <label className="calc-field">
          <span className="calc-field-label">
            If your estimate is optimistic by{" "}
            <strong>
              {estimateError.toFixed(1)} point{estimateError === 1 ? "" : "s"}
            </strong>
          </span>
          <input
            type="range"
            min={0}
            max={8}
            step={0.5}
            value={estimateError}
            onChange={(event) => setEstimateError(Number(event.target.value))}
          />
        </label>
        <p>
          Stakes stay sized at {(estimated * 100).toFixed(1)}%, results settle at{" "}
          {(truth * 100).toFixed(1)}%. True expected value{" "}
          <strong className={evTrue >= 0 ? "gain" : "loss"}>
            {evTrue >= 0 ? "+" : ""}
            {evTrue.toFixed(1)}%
          </strong>
          . An optimistic estimate can make the calculated stake too large. The effect depends on
          the price, probability and fraction; a smaller fraction can still lose.
        </p>
      </div>

      <div className="calc-chart-frame">
        <div className="calc-chart-head">
          <div>
            <p className="site-eyebrow">Simulated bankrolls</p>
            <h3>Typical path at each fraction</h3>
          </div>
          <ul className="calc-legend">
            {FRACTIONS.map((preset) => (
              <li key={preset.label}>
                <i style={{ background: FRACTION_COLOURS[preset.label] }} className="key-line" />
                {preset.label}
              </li>
            ))}
          </ul>
        </div>
        <MultiLineChart
          x={runs[0].x}
          baseline={bankroll}
          logScale
          xLabel="bets placed"
          series={runs.map((run, index) => ({
            label: FRACTIONS[index].label,
            colour: FRACTION_COLOURS[FRACTIONS[index].label],
            values: run.median,
            active: FRACTIONS[index].value === fraction,
            band: { lo: run.lo, hi: run.hi },
          }))}
          ariaLabel={`Typical simulated bankroll over ${bets} bets at each Kelly fraction, on a logarithmic scale.`}
        />
        <p className="calc-note">
          Log scale, so a straight line is a constant growth rate. The shaded band is the 5th to 95th
          percentile for the fraction you selected.
        </p>
      </div>

      <div className="calc-split">
        <div className="calc-subcard">
          <p className="site-eyebrow">Where each fraction lands</p>
          <RangeBars
            baseline={bankroll}
            rows={runs.map((run, index) => ({
              label: FRACTIONS[index].label,
              colour: FRACTION_COLOURS[FRACTIONS[index].label],
              lo: run.terminal.p05,
              mid: run.terminal.p50,
              hi: run.terminal.p95,
              active: FRACTIONS[index].value === fraction,
            }))}
          />
        </div>

        <div className="calc-subcard">
          <p className="site-eyebrow">What it costs to get there</p>
          <table className="calc-table">
            <thead>
              <tr>
                <th scope="col">Fraction</th>
                <th scope="col">Typical drawdown</th>
                <th scope="col">Worst in twenty</th>
                <th scope="col">Finish below half</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run, index) => (
                <tr key={FRACTIONS[index].label} className={FRACTIONS[index].value === fraction ? "is-active" : ""}>
                  <th scope="row" style={{ color: FRACTION_COLOURS[FRACTIONS[index].label] }}>
                    {FRACTIONS[index].label}
                  </th>
                  <td>{(run.medianDrawdownPct * 100).toFixed(0)}%</td>
                  <td>{(run.severeDrawdownPct * 100).toFixed(0)}%</td>
                  <td>{(run.halvedProbability * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="calc-note">
            Drawdown is measured from the running peak, which is what you actually feel. Full Kelly
            maximises expected log growth only with correct probabilities. Optimistic estimates can make it overbet.
          </p>
        </div>
      </div>

      <div className="calc-chart-frame">
        <div className="calc-chart-head">
          <div>
            <p className="site-eyebrow">The arithmetic behind the choice</p>
            <h3>Growth rate against stake size</h3>
          </div>
        </div>
        <GrowthCurve
          points={growthPoints}
          markers={growthMarkers}
          ariaLabel="Expected log growth per bet plotted against stake as a multiple of full Kelly. The optimum moves when the assumed true probability changes."
        />
        <p className="calc-note">
          With correct probabilities, growth peaks at full Kelly. Smaller fractions trade growth for
          lower volatility. For small edges, half Kelly retains roughly 75% of optimal growth and
          quarter Kelly roughly 44%. These are approximations; the curve shows this particular case.
          Increase the estimate error to see how the optimum changes.
        </p>
      </div>

      <div className="calc-bet-slider">
        <label className="calc-field">
          <span className="calc-field-label">
            Bets simulated <strong>{bets}</strong>
          </span>
          <input
            type="range"
            min={50}
            max={1000}
            step={25}
            value={bets}
            onChange={(event) => setBets(Number(event.target.value))}
          />
        </label>
      </div>
    </div>
  );
}
