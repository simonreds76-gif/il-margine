"use client";

import { useState } from "react";
import RetirementRuleIcon from "./RetirementRuleIcon";
import BookmakerMark from "./bookmakers/BookmakerMark";
import { RETIREMENT_FAMILIES, TENNIS_RETIREMENT_RULES, type RetirementRuleFamily } from "@/lib/tennis-retirement-rules";

export default function TennisRetirementComparison() {
  const [stage, setStage] = useState<"early" | "set">("set");
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState<RetirementRuleFamily | "all">("all");
  const rules = TENNIS_RETIREMENT_RULES.filter(rule => rule.name.toLowerCase().includes(query.trim().toLowerCase()) && (family === "all" || rule.family === family));
  return <div className="retirement-comparison">
    <div className="retirement-filters">
      <label>Find your bookmaker<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search bookmaker" autoComplete="off" /></label>
      <label>Settlement rule<select value={family} onChange={event => setFamily(event.target.value as RetirementRuleFamily | "all")}><option value="all">All rules</option>{Object.entries(RETIREMENT_FAMILIES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </div>
    <p className="retirement-count" role="status">{rules.length} of {TENNIS_RETIREMENT_RULES.length} bookmakers shown · UK online Match Winner</p>
    <div className="retirement-stage" aria-label="Stage of retirement"><span>When does the player retire?</span><div>{(["early", "set"] as const).map(value => <button type="button" key={value} aria-pressed={stage === value} onClick={() => setStage(value)}>{value === "early" ? "During the first set" : "After a completed set"}</button>)}</div></div>
    <p className="retirement-scope">Ordinary cash Match Winner bets in eligible ATP and WTA events. At least one point has been scored. Open a bookmaker for competition exceptions and promotions.</p>
    <div className="retirement-table-head" aria-hidden="true"><span>Bookmaker & rule</span><span>Your player retires</span><span>Opponent retires</span><span /></div>
    <div className="retirement-cards">{rules.map(rule => {
      const own = stage === "set" || rule.family === "point" ? rule.own : "Refund";
      const opponent = stage === "set" || rule.family === "point" ? rule.opponent : "Refund";
      return <details key={rule.name} className={`retirement-row retirement-card--${rule.family}`}>
        <summary><span className="retirement-row-brand"><BookmakerMark name={rule.name} /><span><strong>{rule.name}</strong><span className="retirement-row-rule"><RetirementRuleIcon family={rule.family} />{RETIREMENT_FAMILIES[rule.family]}</span></span></span><span className={`retirement-result ${own === "Loses" ? "retirement-loss" : ""}`}><span className="retirement-mobile-label">Your player retires</span>{own}</span><span className="retirement-result"><span className="retirement-mobile-label">Opponent retires</span>{opponent}</span><span className="retirement-expand" aria-hidden="true">+</span></summary>
        <div className="retirement-expanded"><strong>{rule.threshold}</strong><p>{rule.note}</p><p>{rule.detail}</p><div className="retirement-sources"><a href={rule.source} target="_blank" rel="noopener noreferrer">{rule.sourceLabel ?? "Official tennis rules"} ↗</a>{rule.extraSource && <a href={rule.extraSource} target="_blank" rel="noopener noreferrer">{rule.name === "bet365" ? "Retirement promotion" : "UK terms linking this rulebook"} ↗</a>}</div></div>
      </details>;
    })}</div>
    <p className="retirement-scope">bet365’s standard cash settlement is a refund. Its separate qualifying promotion can award Bet Credits. Sky Bet, Paddy Power and Betfair Sportsbook have competition exceptions. Open their rows before comparing.</p>
    {rules.length === 0 && <p className="retirement-empty">No matching bookmaker in this guide. <button type="button" onClick={() => { setQuery(""); setFamily("all"); }}>Show all bookmakers</button></p>}
  </div>;
}
