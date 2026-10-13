'use client';

import { useState } from 'react';
import Link from 'next/link';
import PerformanceFilterIcon from './PerformanceFilterIcon';
import './home-performance-record.css';

type RecordStats = { roi: number; total_profit: number; total_bets: number };
type Scope = 'overall' | 'props' | 'tennis';
const scopes = [
  { key: 'overall', label: 'All picks', icon: 'all' },
  { key: 'props', label: 'Football', icon: 'football' },
  { key: 'tennis', label: 'Tennis', icon: 'tennis' },
] as const;
const signed = (value: number, digits: number) => `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(digits)}`;
const tone = (value: number) => value > 0 ? 'hpr-positive' : value < 0 ? 'hpr-negative' : '';

export default function HomePerformanceRecord({ stats, status }: {
  stats: Record<Scope, RecordStats>;
  status: 'loaded' | 'historical' | 'unavailable';
}) {
  const [scope, setScope] = useState<Scope>('overall');
  const active = stats[scope];
  const floor = Math.min(0, stats.props.roi, stats.tennis.roi);
  const ceiling = Math.max(1, stats.props.roi, stats.tennis.roi);
  const position = (value: number) => (value - floor) / (ceiling - floor) * 100;
  const zero = position(0);

  return <section className="hpr-card" aria-labelledby="hpr-title">
    <div className="hpr-heading"><h2 id="hpr-title">Public performance record</h2><Link href="/track-record" prefetch={false} aria-label="Open the full performance record">↗</Link></div>
    <div className="hpr-switch" role="group" aria-label="Headline record sport">
      {scopes.map(item => <button key={item.key} type="button" aria-pressed={scope === item.key} onClick={() => setScope(item.key)}><PerformanceFilterIcon name={item.icon} />{item.label}</button>)}
    </div>
    <div className="hpr-readout" aria-live="polite" aria-atomic="true">
      <p className="hpr-scope">{scopes.find(item => item.key === scope)?.label} <span>ROI</span></p>
      <p className={`hpr-roi ${tone(active.roi)}`}>{signed(active.roi, 1)}<span>%</span></p>
      <dl className="hpr-stats"><div><dt>Profit</dt><dd className={tone(active.total_profit)}>{signed(active.total_profit, 2)}<small>u</small></dd></div><div><dt>Settled bets</dt><dd>{active.total_bets.toLocaleString('en-GB')}</dd></div></dl>
    </div>
    <div className="hpr-comparison">
      <p>Compare the sports <span>ROI</span></p>
      {scopes.slice(1).map(item => {
        const roi = stats[item.key].roi;
        return <button key={item.key} type="button" aria-label={`Inspect ${item.label} record, ROI ${signed(roi, 1)} percent`} aria-pressed={scope === item.key} onClick={() => setScope(item.key)}>
          <span>{item.label}<small>{stats[item.key].total_bets.toLocaleString('en-GB')} bets</small></span><span className="hpr-track" aria-hidden="true"><i className="hpr-zero" style={{ left: `${zero}%` }} /><i className={`hpr-bar ${roi < 0 ? 'hpr-bar-negative' : ''}`} style={{ left: `${Math.min(zero, position(roi))}%`, width: `${Math.abs(position(roi) - zero)}%` }} /></span><strong className={tone(roi)}>{signed(roi, 1)}%</strong>
        </button>;
      })}
      <span className="hpr-scale">Bars start at 0% and use the same scale.</span>
    </div>
    <a className="hpr-explore" href="#monthly"><span>Explore the monthly record<small>Choose a month. Inspect the results.</small></span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M4 19h16M6 15v-4m6 4V5m6 10V8" /></svg></a>
    <p className="hpr-basis">ROI is profit divided by stakes. Includes earlier aggregate results. <Link prefetch={false} href="/track-record#record-method">Record methodology ↗</Link></p>
    <p className="hpr-note">{status === 'unavailable' ? 'Latest refresh unavailable. These figures may exclude recent results.' : status === 'historical' ? 'Earlier results only. The latest results are unavailable.' : 'Past performance is not a forecast.'}</p>
  </section>;
}
