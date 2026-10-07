"use client";

import { useState } from "react";
import BookmakerMark from "./bookmakers/BookmakerMark";
import { RETIREMENT_FAMILIES, TENNIS_RETIREMENT_RULES, type RetirementRuleFamily } from "@/lib/tennis-retirement-rules";

export default function TennisRetirementComparison() {
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState<RetirementRuleFamily | "all">("all");
  const rules = TENNIS_RETIREMENT_RULES.filter(rule => rule.name.toLowerCase().includes(query.trim().toLowerCase()) && (family === "all" || rule.family === family));
  return <div className="retirement-comparison">
    <div className="retirement-filters">
      <label>Find your bookmaker<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search bookmaker" autoComplete="off" /></label>
      <label>Settlement rule<select value={family} onChange={event => setFamily(event.target.value as RetirementRuleFamily | "all")}><option value="all">All rules</option>{Object.entries(RETIREMENT_FAMILIES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    </div>
    <p className="retirement-count" role="status">{rules.length} of {TENNIS_RETIREMENT_RULES.length} bookmakers shown · UK online Match Winner</p>
    <div className="retirement-cards">{rules.map(rule => <section key={rule.name} className={`retirement-card retirement-card--${rule.family}`} aria-label={`${rule.name} retirement rule`}>
      <header><div className="retirement-brand"><BookmakerMark name={rule.name} /><h3>{rule.name}</h3></div><span className="retirement-badge">{RETIREMENT_FAMILIES[rule.family]}</span></header>
      <p className="retirement-threshold">{rule.threshold}</p>
      <dl className="retirement-outcomes">
        <div><dt>Before the first set finishes</dt><dd>{rule.early}</dd></div>
        <div><dt>After one set: your player retires</dt><dd className={rule.own === "Loses" ? "retirement-loss" : ""}>{rule.own}</dd></div>
        <div><dt>After one set: opponent retires</dt><dd>{rule.opponent}</dd></div>
      </dl>
      <p className="retirement-rule-note">{rule.note}</p>
      <details><summary>Exceptions and official source <span aria-hidden="true">+</span></summary><p>{rule.detail}</p><div className="retirement-sources"><a href={rule.source} target="_blank" rel="noopener noreferrer">{rule.sourceLabel ?? "Official tennis rules"} ↗</a>{rule.extraSource && <a href={rule.extraSource} target="_blank" rel="noopener noreferrer">{rule.name === "bet365" ? "Retirement promotion" : "UK terms linking this rulebook"} ↗</a>}</div></details>
    </section>)}</div>
    {rules.length === 0 && <p className="retirement-empty">No matching bookmaker in this guide. <button type="button" onClick={() => { setQuery(""); setFamily("all"); }}>Show all bookmakers</button></p>}
  </div>;
}
