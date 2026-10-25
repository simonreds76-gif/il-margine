"use client";

import { useId, useState, type ReactNode } from "react";
import Image from "next/image";
import SampleSizeBadge from "@/components/SampleSizeBadge";
import styles from "./TipsCompetitionPicker.module.css";

type Competition = { id: string; name: string; logoPath: string; logoClassName?: string };

export default function TipsCompetitionPicker({ options, value, onChange, stats, label, children }: {
  options: readonly Competition[];
  value: string;
  onChange: (value: string) => void;
  stats: { total_bets: number; roi: number };
  label: string;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  const selected = options.find(option => option.id === value) ?? options[0];
  return <>
    <div className={styles.mobile}>
      <div className={styles.selector}>
        {selected ? <span className={styles.logo}><Image src={selected.logoPath} alt="" width={36} height={36} className={`h-9 w-9 object-contain ${selected.logoClassName ?? ""}`} /></span> : null}
        <div className={styles.field}>
          <label htmlFor={`${id}-select`}>{label}</label>
          <select id={`${id}-select`} value={value} onChange={event => onChange(event.target.value)} aria-controls="picks competition-record recent-results">
            {options.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
          </select>
        </div>
      </div>
      <div className={styles.summary}>
        <span>{stats.total_bets.toLocaleString("en-GB")} bets</span>
        <span className={stats.total_bets < 50 || stats.roi === 0 ? "text-slate-400" : stats.roi > 0 ? "text-emerald-300" : "text-rose-300"}>
          {stats.total_bets > 0 ? `${stats.roi > 0 ? "+" : ""}${stats.roi.toFixed(1)}% ROI` : "ROI —"}
        </span>
        <SampleSizeBadge settled={stats.total_bets} compact />
      </div>
      <button type="button" className={styles.toggle} aria-expanded={expanded} aria-controls={`${id}-records`} onClick={() => setExpanded(open => !open)}>
        {expanded ? "Hide competition records" : "Compare all competition records"}
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true" style={{ transform: expanded ? "rotate(180deg)" : undefined }}><path d="m4 6 4 4 4-4" /></svg>
      </button>
    </div>
    <div id={`${id}-records`} className={`${styles.records} ${expanded ? styles.expanded : ""}`}>{children}</div>
  </>;
}
