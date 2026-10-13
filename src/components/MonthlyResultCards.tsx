'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { MonthRow } from './MonthlyBreakdown';
import RecordIcon from './RecordIcon';
import './home-fixtures.css';

const signed = (n: number, digits = 2) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}`;
export default function MonthlyResultCards({ rows }: { rows: MonthRow[] }) {
  const [all, setAll] = useState(false);
  const [month, setMonth] = useState('');
  useEffect(() => { const id = setTimeout(() => setMonth(new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit' }).format(new Date())), 0); return () => clearTimeout(id); }, []);
  const sorted = [...rows].sort((a, b) => b.month.localeCompare(a.month));
  return <div className="hm-results"><div className="hf-heading"><div><p className="hf-eyebrow">Our published selections</p><h2>Month by month.</h2><p>Profit, ROI and the stakes behind every month. Football player props and tennis combined.</p></div><Link prefetch={false} href="/track-record">Full record ↗</Link></div>
    <div className="hm-grid">{(all ? sorted : sorted.slice(0, 6)).map(row => <article key={row.month} className={`hm-card ${row.total_profit < 0 ? 'hm-negative' : row.total_profit > 0 ? 'hm-positive' : ''}`}><div className="hm-top"><h3>{new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${row.month.slice(0, 7)}-01T12:00:00Z`))}</h3>{row.month.slice(0, 7) === month ? <span className="hm-ongoing">In progress</span> : <RecordIcon name="calendar" className="h-5 w-5" />}</div><p className="hm-profit">{signed(row.total_profit)}<span>u</span></p><span className="hm-profit-label">Net profit</span><dl><div><dt>ROI</dt><dd>{signed(row.roi, 1)}%</dd></div><div><dt>Bets</dt><dd>{row.total_bets}</dd></div><div><dt>Staked</dt><dd>{row.total_stake.toFixed(1)}u</dd></div></dl><details><summary>Month details <span aria-hidden="true">+</span></summary><p>{row.wins} wins · {row.losses} losses.</p><Link prefetch={false} href="/track-record">Explore the full record ↗</Link></details></article>)}</div>
    <div className="hm-bottom"><p>1u is one standard stake. ROI is profit divided by the amount staked. The current month can still change.</p>{sorted.length > 6 && <button aria-expanded={all} onClick={() => setAll(!all)}>{all ? 'Show recent months' : `Show all ${sorted.length} months`} <span aria-hidden="true">{all ? '↑' : '↓'}</span></button>}</div>
  </div>;
}
