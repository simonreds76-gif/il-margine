'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { MonthRow } from './MonthlyBreakdown';
import './home-fixtures.css';

const signed = (n: number, digits = 2) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}`;
export default function MonthlyResultCards({ rows }: { rows: MonthRow[] }) {
  const [all, setAll] = useState(false);
  const [month, setMonth] = useState('');
  useEffect(() => { const id = setTimeout(() => setMonth(new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit' }).format(new Date())), 0); return () => clearTimeout(id); }, []);
  const sorted = [...rows].sort((a, b) => b.month.localeCompare(a.month));
  const max = Math.max(1, ...rows.map(row => Math.abs(row.total_profit)));
  return <div className="hm-results">
    <div className="hf-heading"><div><p className="hf-eyebrow">Our published selections</p><h2>The monthly record.</h2><p>Football player props and tennis, at the prices and stakes we published.</p></div><Link className="hf-outline-link" prefetch={false} href="/track-record">Full record <span aria-hidden="true">↗</span></Link></div>
    <div className="hm-ledger">
      <div className="hm-columns" aria-hidden="true"><span>Month</span><span>Profit</span><span>ROI</span><span>Bets</span><span className="hm-bar-heading">Profit in units</span><span /></div>
      {(all ? sorted : sorted.slice(0, 6)).map(row => <details className="hm-month" key={row.month}>
        <summary>
          <span className="hm-date">{new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${row.month.slice(0, 7)}-01T12:00:00Z`))}{row.month.slice(0, 7) === month && <small>In progress</small>}</span>
          <strong className={row.total_profit < 0 ? 'hm-loss' : row.total_profit > 0 ? 'hm-gain' : ''}><span className="sr-only">Profit </span>{signed(row.total_profit)}u</strong>
          <span><span className="sr-only">ROI </span>{signed(row.roi, 1)}%</span>
          <span><span className="sr-only">Bets </span>{row.total_bets}</span>
          <span className="hm-bar" aria-hidden="true"><i style={{ width: `${Math.abs(row.total_profit) / max * 50}%`, left: row.total_profit < 0 ? `${50 - Math.abs(row.total_profit) / max * 50}%` : '50%', background: row.total_profit < 0 ? '#e89caa' : '#8cdbc0' }} /></span>
          <span className="hm-expand" aria-hidden="true" />
        </summary>
        <div className="hm-detail">{row.wins} wins · {row.losses} losses · {row.total_stake.toFixed(1)}u staked</div>
      </details>)}
    </div>
    <div className="hm-bottom"><p>1u is one standard stake. ROI is profit divided by the amount staked. Tap a month for its stakes and results.</p>{sorted.length > 6 && <button aria-expanded={all} onClick={() => setAll(!all)}>{all ? 'Show recent months' : `Show all ${sorted.length} months`} <span aria-hidden="true">{all ? '↑' : '↓'}</span></button>}</div>
  </div>;
}
