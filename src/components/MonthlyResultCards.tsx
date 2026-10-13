'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { MonthRow } from './MonthlyBreakdown';
import { BASELINE_STATS } from '@/lib/baseline';
import { summarizeMonthlyRecord } from '@/lib/monthly-record';
import PerformanceFilterIcon from './PerformanceFilterIcon';
import './home-fixtures.css';
import './monthly-performance.css';

const signed = (n: number, digits = 2) => `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n).toFixed(digits)}`;
const tone = (n: number | null) => n !== null && n > 0 ? 'mp-positive' : n !== null && n < 0 ? 'mp-negative' : '';
const monthLabel = (month: string, short = false) => new Intl.DateTimeFormat('en-GB', { month: 'short', ...(short ? {} : { year: 'numeric' }), timeZone: 'UTC' }).format(new Date(`${month.slice(0, 7)}-01T12:00:00Z`));
type Scope = 'combined' | 'props' | 'tennis';
const scopes: { key: Scope; label: string }[] = [{ key: 'combined', label: 'All picks' }, { key: 'props', label: 'Football props' }, { key: 'tennis', label: 'Tennis' }];

export default function MonthlyResultCards({ rows, bySport }: { rows: MonthRow[]; bySport?: Partial<Record<'props' | 'tennis', { show: boolean; rows: MonthRow[] }>> }) {
  const [scope, setScope] = useState<Scope>('combined');
  const [metric, setMetric] = useState<'profit' | 'roi'>('profit');
  const [range, setRange] = useState<'all' | 'six'>('all');
  const [selected, setSelected] = useState('');
  const [currentMonth, setCurrentMonth] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { const id = setTimeout(() => setCurrentMonth(new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit' }).format(new Date())), 0); return () => clearTimeout(id); }, []);
  const source = scope === 'combined' ? rows : bySport?.[scope]?.rows ?? [];
  const sorted = [...source].sort((a, b) => a.month.localeCompare(b.month));
  const visible = range === 'six' ? sorted.slice(-6) : sorted;
  const active = visible.find(row => row.month === selected) ?? visible.at(-1);
  useEffect(() => {
    const container = scrollRef.current;
    const button = container?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
    if (container && button) container.scrollLeft = button.offsetLeft - (container.clientWidth - button.offsetWidth) / 2;
  }, [active?.month, scope, range]);
  const earlier = BASELINE_STATS[scope === 'combined' ? 'overall' : scope];
  const totals = summarizeMonthlyRecord(visible, range === 'all' ? earlier : undefined);
  const periodROI = totals.roi;
  const value = (row: MonthRow) => metric === 'profit' ? row.total_profit : row.roi;
  const values = visible.map(value);
  const extent = Math.max(1, ...values.map(Math.abs));
  const step = 10 ** Math.floor(Math.log10(extent));
  const upper = Math.max(step, Math.ceil(Math.max(0, ...values) / step) * step);
  const lower = Math.floor(Math.min(0, ...values) / step) * step;
  const position = (n: number) => (upper - n) / (upper - lower) * 100;
  const zero = position(0);
  const unit = metric === 'profit' ? 'u' : '%';
  const coverage = visible.length ? `${monthLabel(visible[0].month)} to ${monthLabel(visible.at(-1)!.month)}` : '';

  return <div className="hm-results mp-results">
    <div className="hf-heading"><div><p className="hf-eyebrow">The public record</p><h2>Explore the monthly record.</h2><p>Explore the returns from our football and tennis selections.</p></div><Link className="hf-outline-link" prefetch={false} href="/track-record">Full record <span aria-hidden="true">↗</span></Link></div>
    <div className="mp-terminal">
      <div className="mp-toolbar">
        <div className="mp-sports" role="group" aria-label="Record sport">{scopes.filter(item => item.key === 'combined' || bySport?.[item.key]?.show).map(item => <button key={item.key} aria-pressed={scope === item.key} onClick={() => { setScope(item.key); setSelected(''); }}><PerformanceFilterIcon name={item.key === 'combined' ? 'all' : item.key === 'props' ? 'football' : 'tennis'} />{item.label}</button>)}</div>
        <div className="mp-range" role="group" aria-label="Chart period"><button aria-pressed={range === 'six'} onClick={() => { setRange('six'); setSelected(''); }}>Recent 6 months</button><button aria-pressed={range === 'all'} onClick={() => { setRange('all'); setSelected(''); }}>Full record</button></div>
      </div>
      {active ? <>
        <div className="mp-period"><div><span className="mp-label">{range === 'all' ? 'Full record profit' : 'Profit in this period'}</span><strong className={tone(totals.profit)}>{signed(totals.profit)}<small>u</small></strong><span className="mp-coverage">{range === 'all' ? 'Earlier results + monthly results' : coverage}</span></div><dl><div><dt>ROI</dt><dd className={tone(periodROI)}>{periodROI === null ? 'N/A' : `${signed(periodROI, 1)}%`}</dd></div><div><dt>Settled bets</dt><dd>{totals.bets.toLocaleString()}</dd></div><div><dt>Units staked</dt><dd>{totals.stake.toLocaleString('en-GB', { maximumFractionDigits: 2 })}u</dd></div></dl></div>
        <p className="mp-period-note">{range === 'all' ? 'Full record totals include the earlier summary and the monthly results below.' : 'This view includes only the selected six months.'} Monthly bars cover {coverage}.</p>
        {range === 'all' && <div className="mp-earlier"><div><span className="mp-label">Earlier results</span><p>Combined summary, not a single month</p></div><strong className={tone(earlier.total_profit)}>{signed(earlier.total_profit)}<small>u</small></strong><span>{earlier.total_bets.toLocaleString('en-GB')} bets · {earlier.total_stake.toLocaleString('en-GB')}u staked</span><Link href="/track-record#record-method" prefetch={false}>Calculation details ↗</Link></div>}
        <div className="mp-visual">
          <div className="mp-chart-side">
            <div className="mp-chart-top"><h3>Monthly {metric === 'profit' ? 'profit' : 'ROI'}</h3><div className="mp-metric" role="group" aria-label="Chart measure"><button aria-pressed={metric === 'profit'} onClick={() => setMetric('profit')}>Profit · u</button><button aria-pressed={metric === 'roi'} onClick={() => setMetric('roi')}>ROI · %</button></div></div>
            <div className="mp-plot-wrap"><div className="mp-axis" aria-hidden="true"><span style={{ top: 0 }}>{upper}{unit}</span><span style={{ top: `${zero}%` }}>0</span>{lower < 0 && <span style={{ top: '100%' }}>{lower}{unit}</span>}</div><div className="mp-scroll" ref={scrollRef}><div className="mp-plot" style={{ minWidth: Math.max(visible.length * 48, 240) }}>
              <div className="mp-grid" aria-hidden="true"><i style={{ top: 0 }} /><i style={{ top: '50%' }} /><i className="mp-zero" style={{ top: `${zero}%` }} />{lower < 0 && <i style={{ top: '100%' }} />}</div>
              <div className="mp-bars">{visible.map(row => { const n = value(row); return <button key={row.month} className="mp-month-button" aria-pressed={active.month === row.month} aria-label={`${monthLabel(row.month)}, profit ${signed(row.total_profit)} units, ROI ${signed(row.roi, 1)} percent, ${row.total_bets} settled bets`} onClick={() => setSelected(row.month)} onFocus={() => setSelected(row.month)}><span className={`mp-bar ${n < 0 ? 'mp-bar-negative' : ''}`} style={{ top: `${Math.min(zero, position(n))}%`, height: `${Math.abs(position(n) - zero)}%` }} /><span className="mp-month-label">{monthLabel(row.month, true)}<small>{row.month.slice(0, 4)}</small></span></button>; })}</div>
            </div></div></div>
            <p className="mp-hint">Tap a month to inspect its results. Scroll sideways for more months.</p>
          </div>
          <div className="mp-inspector mp-inspector-v2" aria-live="polite" aria-atomic="true">
            <div className="mp-inspector-title"><span className="mp-label">Month in focus</span><div className="mp-month-heading"><h3>{monthLabel(active.month)}</h3><span className={active.month.slice(0, 7) === currentMonth ? 'mp-status mp-status-open' : 'mp-status'}>{currentMonth ? active.month.slice(0, 7) === currentMonth ? 'In progress' : 'Completed' : 'Monthly result'}</span></div></div>
            <div className="mp-profit-focus"><span className="mp-label">Net profit</span><strong className={`mp-month-profit ${tone(active.total_profit)}`}>{signed(active.total_profit)}<small>u</small></strong></div>
            <dl className="mp-detail-grid"><div><dt>Return on stake</dt><dd className={tone(active.roi)}>{signed(active.roi, 1)}<small>%</small></dd></div><div><dt>Units staked</dt><dd>{active.total_stake.toFixed(2)}<small>u</small></dd></div><div><dt>Settled bets</dt><dd>{active.total_bets}</dd></div><div><dt>Wins / losses</dt><dd>{active.wins}<span className="mp-stat-divider">/</span>{active.losses}</dd></div></dl>
            <div className="mp-outcomes"><div><span>{active.wins} wins</span><span>{active.losses} losses</span></div><div className="mp-outcome-track" aria-hidden="true"><span style={{ width: `${active.wins + active.losses > 0 ? active.wins / (active.wins + active.losses) * 100 : 0}%` }} /></div><p>Win and loss counts. Profit uses recorded odds and stakes.</p></div>
          </div>
        </div>
        <div className="mp-footnote"><p>1u is one standard stake. ROI is profit divided by stakes, using the stakes recorded for each pick.</p><p>Monthly detail covers {coverage}. Earlier figures are stored as a combined summary with a one-unit-per-bet stake basis. Monthly figures use individual recorded stakes and exclude void bets. Past performance is not a forecast.</p></div>
        <details className="mp-table"><summary>View the monthly figures <span aria-hidden="true">+</span></summary><div className="mp-table-scroll"><table><caption className="sr-only">{scopes.find(item => item.key === scope)?.label} monthly results, {coverage}</caption><thead><tr><th scope="col">Month</th><th scope="col">Profit</th><th scope="col">ROI</th><th scope="col">Bets</th><th scope="col">Staked</th></tr></thead><tbody>{[...visible].reverse().map(row => <tr key={row.month}><th scope="row">{monthLabel(row.month)}</th><td className={tone(row.total_profit)}>{signed(row.total_profit)}u</td><td className={tone(row.roi)}>{signed(row.roi, 1)}%</td><td>{row.total_bets}</td><td>{row.total_stake.toFixed(2)}u</td></tr>)}{range === 'all' && <tr className="mp-earlier-row"><th scope="row">Earlier results<small>Combined summary</small></th><td className={tone(earlier.total_profit)}>{signed(earlier.total_profit)}u</td><td className={tone(earlier.total_profit)}>{signed(earlier.total_profit / earlier.total_stake * 100, 1)}%</td><td>{earlier.total_bets}</td><td>{earlier.total_stake.toFixed(2)}u</td></tr>}</tbody></table></div></details>
      </> : <p className="mp-empty">No monthly results are available for this sport.</p>}
    </div>
  </div>;
}
