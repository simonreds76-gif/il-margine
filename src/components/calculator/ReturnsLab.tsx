"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import EditorialIcon from "@/components/EditorialIcon";
import { FanChart, formatMoney } from "./Charts";
import { parseNumber, simulateFlatStake } from "@/lib/calculator/math";

const STAKE_PRESETS = [10, 25, 50, 100, 250] as const;

const CAPTURE_PRESETS = [
  { value: 1, label: "Full", note: "You got every recorded price" },
  { value: 0.7, label: "70%", note: "Some prices gone by the time you bet" },
  { value: 0.5, label: "50%", note: "Half the edge lost to price and limits" },
  { value: 0.25, label: "25%", note: "Late, restricted, or shopping one book" },
] as const;

export interface RecordSummary {
  totalBets: number;
  wins: number;
  losses: number;
  roi: number;
  totalProfit: number;
  totalStake: number;
  source: "live" | "fallback" | "stale";
}

export default function ReturnsLab({ record }: { record: RecordSummary }) {
  const [stakeInput, setStakeInput] = useState("50");
  const [bankrollInput, setBankrollInput] = useState("2500");
  const [capture, setCapture] = useState<number>(1);
  const [selectedBetCount, setBetCount] = useState<number | null>(null);

  const betCount = Math.min(selectedBetCount ?? record.totalBets, record.totalBets);
  const stake = Math.max(0, parseNumber(stakeInput));
  const bankroll = Math.max(0, parseNumber(bankrollInput));
  const winRate = record.wins + record.losses > 0 ? record.wins / (record.wins + record.losses) : 0;
  const recordedRoi = record.roi / 100;
  const appliedRoi = recordedRoi > 0 ? recordedRoi * capture : recordedRoi;

  const totalStaked = stake * betCount;
  const headlineProfit = totalStaked * appliedRoi;

  const simulation = useMemo(
    () =>
      simulateFlatStake({
        bets: betCount,
        stake,
        winRate,
        roi: appliedRoi,
        startBankroll: bankroll,
        paths: 400,
        seed: 20260921,
      }),
    [betCount, stake, winRate, appliedRoi, bankroll]
  );

  const start = bankroll;
  const stakePctOfBank = start > 0 ? (stake / start) * 100 : 0;
  const drawdownPct = start > 0 ? (simulation.severeDrawdown / start) * 100 : 0;

  return (
    <div className="calc-panel">
      <header className="calc-panel-head">
        <div>
          <p className="site-eyebrow">Flat stake, published record</p>
          <h2>Explore returns and bankroll risk</h2>
          <p className="calc-lede">
            Pick a stake and the tool applies our settled strike rate and return on turnover to that
            many bets. The curve is a simulation, not a replay: it re-runs the same edge four hundred
            times so you can see the range of results one edge produces, rather than the single
            ordering that happened to occur. This simplified model assumes independent bets at one
            representative winning price. It combines stake-weighted ROI with win rate; it is not a
            reconstruction of flat-stake historical returns or proof of a future edge.
          </p>
        </div>
        <Link href="/track-record" className="calc-link">
          Inspect the settled record
        </Link>
      </header>

      <div className="calc-controls">
        <fieldset className="calc-field calc-field-span">
          <legend>Stake per bet</legend>
          <div className="calc-chip-row">
            {STAKE_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                aria-pressed={stake === preset}
                className={`calc-chip calc-stake-preset${stake === preset ? " is-active" : ""}`}
                onClick={() => setStakeInput(String(preset))}
              >
                <EditorialIcon name="bankroll" className="h-5 w-5" /><span>£{preset}</span><span className="calc-preset-check" aria-hidden="true">{stake === preset ? "✓" : ""}</span>
              </button>
            ))}
            <label className="calc-inline-input">
              <span className="sr-only">Custom stake in pounds</span>
              <input
                type="number"
                inputMode="decimal"
                min={0}
                value={stakeInput}
                onChange={(event) => setStakeInput(event.target.value)}
                onFocus={(event) => event.target.select()}
                aria-label="Custom stake in pounds"
              />
            </label>
          </div>
        </fieldset>

        <label className="calc-field">
          <span className="calc-field-label">
            Starting bankroll <strong>{formatMoney(bankroll)}</strong>
          </span>
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={bankrollInput}
            onChange={(event) => setBankrollInput(event.target.value)}
            onFocus={(event) => event.target.select()}
            className="calc-text-input"
          />
          <small>
            At {formatMoney(stake)} a bet that is {stakePctOfBank.toFixed(1)}% of the bank per
            selection.
          </small>
        </label>

        <label className="calc-field">
          <span className="calc-field-label">
            Bets placed <strong>{betCount.toLocaleString("en-GB")}</strong>
          </span>
          <input
            type="range"
            min={1}
            max={record.totalBets}
            step={1}
            value={betCount}
            onChange={(event) => setBetCount(Number(event.target.value))}
          />
          <small>Full settled sample is {record.totalBets.toLocaleString("en-GB")} bets.</small>
        </label>

        <fieldset className="calc-field calc-field-span">
          <legend>How much of the edge you actually capture</legend>
          <div className="calc-chip-row">
            {CAPTURE_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className={`calc-chip${capture === preset.value ? " is-active" : ""}`}
                onClick={() => setCapture(preset.value)}
                title={preset.note}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <small>
            Published prices move. Taking a shorter price, or betting after the market has corrected,
            removes part of the edge before the bet even settles. This is an illustrative reduction in positive ROI, not a measured price-decay model.
          </small>
        </fieldset>
      </div>

      <div className="calc-metrics" aria-live="polite">
        <div className="calc-metric">
          <span>Planned turnover</span>
          <strong>{formatMoney(totalStaked)}</strong>
          <small>{betCount.toLocaleString("en-GB")} bets at {formatMoney(stake)}</small>
        </div>
        <div className="calc-metric is-accent">
          <span>Profit at assumed ROI</span>
          <strong className={headlineProfit >= 0 ? "gain" : "loss"}>
            {headlineProfit >= 0 ? "+" : ""}
            {formatMoney(headlineProfit)}
          </strong>
          <small>
            {(appliedRoi * 100).toFixed(1)}% of turnover
            {capture < 1 ? ` (${record.roi.toFixed(1)}% recorded, ${Math.round(capture * 100)}% captured)` : ""}
          </small>
        </div>
        <div className="calc-metric">
          <span>Strike rate</span>
          <strong>{(winRate * 100).toFixed(1)}%</strong>
          <small>
            {record.wins.toLocaleString("en-GB")}W / {record.losses.toLocaleString("en-GB")}L
          </small>
        </div>
        <div className="calc-metric">
          <span>Modelled winning price</span>
          <strong>{simulation.avgWinOdds.toFixed(2)}</strong>
          <small>representative odds, not observed average odds</small>
        </div>
      </div>

      <div className="calc-chart-frame">
        <div className="calc-chart-head">
          <div>
            <p className="site-eyebrow">Range of outcomes</p>
            <h3>Four hundred runs of the same edge</h3>
          </div>
          <ul className="calc-legend">
            <li><i className="key-line" /> typical run</li>
            <li><i className="key-band" /> middle half</li>
            <li><i className="key-band-outer" /> 5th to 95th</li>
            <li><i className="key-dash" /> straight-line average</li>
          </ul>
        </div>
        <FanChart
          x={simulation.band.x}
          p05={simulation.band.p05}
          p25={simulation.band.p25}
          p50={simulation.band.p50}
          p75={simulation.band.p75}
          p95={simulation.band.p95}
          expected={simulation.band.expected}
          startValue={start}
          ariaLabel={`Simulated bankroll range over ${betCount} flat stakes. Typical finish ${formatMoney(simulation.terminal.p50)}, with a fifth to ninety fifth percentile range of ${formatMoney(simulation.terminal.p05)} to ${formatMoney(simulation.terminal.p95)}.`}
        />
        <p className="calc-note">
          Move the pointer across the chart to read any point. The dashed line is the arithmetic
          average, which is the only thing a single flat projection ever shows you. The bands show simulated outcomes, not confidence intervals for the true edge.
          Paths stop when the remaining bankroll cannot fund the next full stake; the dashed reference assumes unlimited funding.
        </p>
      </div>

      <div className="calc-metrics calc-metrics-risk">
        <div className="calc-metric">
          <span>Typical finish</span>
          <strong className={simulation.terminal.p50 < start ? "loss" : "gain"}>{formatMoney(simulation.terminal.p50)}</strong>
          <small>half of runs land above this</small>
        </div>
        <div className="calc-metric">
          <span>Unlucky run (5th)</span>
          <strong className={simulation.terminal.p05 < start ? "loss" : ""}>
            {formatMoney(simulation.terminal.p05)}
          </strong>
          <small>one run in twenty is worse</small>
        </div>
        <div className="calc-metric">
          <span>Severe drawdown (95th)</span>
          <strong className="loss">{formatMoney(simulation.severeDrawdown)}</strong>
          <small>
            {drawdownPct.toFixed(0)}% of the bank in the worst one in twenty runs, typically{" "}
            {formatMoney(simulation.medianDrawdown)}
          </small>
        </div>
        <div className="calc-metric">
          <span>Runs finishing down</span>
          <strong className={simulation.lossProbability > 0.2 ? "loss" : ""}>
            {simulation.lossProbability === 0 ? "0 of 400" : `${(simulation.lossProbability * 100).toFixed(1)}%`}
          </strong>
          <small>
            {simulation.bustProbability > 0
              ? `${(simulation.bustProbability * 100).toFixed(1)}% of runs could not fund another full stake`
              : "No losses in this simulation does not mean zero risk."}
          </small>
        </div>
      </div>

      {simulation.bustProbability > 0.005 ? (
        <p className="calc-alert is-danger">
          At {formatMoney(stake)} per bet against a {formatMoney(start)} bank, {(simulation.bustProbability * 100).toFixed(1)}%
          of simulated runs could not fund another full stake before the sample finished. A positive expectation does not
          survive a stake that large. Reduce the stake or raise the bank.
        </p>
      ) : null}

      {record.source === "stale" && <p className="calc-alert">Showing the last available settled record. The latest refresh could not be loaded.</p>}
      {record.source === "fallback" ? (
        <p className="calc-alert">
          Live results are unavailable right now, so these figures use the last recorded baseline.
        </p>
      ) : null}
    </div>
  );
}
