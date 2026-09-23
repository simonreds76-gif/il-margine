'use client';
import { useId, useMemo, useState, type PointerEvent } from 'react';
import { summary, type Observation } from './football-core';
import { underwater, unitScale } from './chart-math';

const units = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(1)}u`;
const date = (value: string) => new Date(`${value}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const price = (value: number) => value.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 6 });
const width = 1000, height = 240;

export default function FootballProfitChart({ rows }: { rows: Observation[] }) {
    const id = `fa-profit-${useId().replaceAll(':', '')}`;
    const [inspection, setInspection] = useState<{ rows: Observation[]; index: number } | null>(null);
    const [showDrawdown, setShowDrawdown] = useState(true);
    const model = useMemo(() => {
        const stats = summary(rows), scale = unitScale(stats.curve), dips = underwater(stats.curve);
        const x = (i: number) => width * i / Math.max(1, rows.length);
        const y = (v: number) => height * (scale.max - v) / (scale.max - scale.min);
        const path = stats.curve.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(v).toFixed(2)}`).join(' ');
        const drawdownPath = dips.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${(-v / Math.max(1, stats.drawdown) * 65).toFixed(2)}`).join(' ');
        return { stats, scale, dips, x, y, path, area: `${path} L${width},${y(0)} L0,${y(0)} Z`, drawdownPath };
    }, [rows]);
    const { stats, scale, dips, x, y } = model;
    const index = inspection?.rows === rows ? Math.min(inspection.index, rows.length) : rows.length;
    const active = rows[index - 1], value = stats.curve[index];
    const inspect = (event: PointerEvent<SVGSVGElement>) => {
        const rect = event.currentTarget.getBoundingClientRect();
        setInspection({ rows, index: Math.max(0, Math.min(rows.length, Math.round((event.clientX - rect.left) / rect.width * rows.length))) });
    };
    const pointerDown = (event: PointerEvent<SVGSVGElement>) => { event.currentTarget.setPointerCapture(event.pointerId); inspect(event); };
    if (!rows.length) return <p className="fa-empty">No priced matches meet these filters.</p>;

    return <section className="fa-chart fa-profit-chart" aria-label="Historical profit and drawdown">
        <div className="fa-chart-heading"><div><p className="fa-eyebrow">The journey, bet by bet</p><h3>Cumulative profit</h3><p className="fa-chart-subtitle">{rows.length.toLocaleString('en-GB')} bets · 1u each · domestic league only</p></div>
            <div className="fa-chart-value"><small>After {index.toLocaleString('en-GB')} bets</small><strong className={value < 0 ? 'fa-negative' : 'fa-positive'}>{units(value)}</strong></div></div>
        <div className="fa-chart-toolbar"><div className="fa-chart-key"><span><i className="fa-key-gain" />Above break-even</span><span><i className="fa-key-loss" />Below break-even</span></div><button type="button" aria-pressed={showDrawdown} aria-controls={`${id}-drawdown`} onClick={() => setShowDrawdown(!showDrawdown)}>Drawdown {showDrawdown ? '−' : '+'}</button></div>
        <div className="fa-plot-frame"><div className="fa-unit-axis" aria-hidden="true">{scale.ticks.map(tick => <span key={tick} style={{ top: `${y(tick) / height * 100}%` }}>{tick}u</span>)}</div>
            <svg className="fa-profit-plot" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Cumulative profit after ${rows.length} bets: ${units(stats.profit)}. Maximum drawdown: ${stats.drawdown.toFixed(1)} units. Use the Inspect match slider to explore every result.`} onPointerMove={inspect} onPointerDown={pointerDown}>
                <defs><linearGradient id={`${id}-gain`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#74e5b5" stopOpacity=".3"/><stop offset="1" stopColor="#74e5b5" stopOpacity=".035"/></linearGradient><linearGradient id={`${id}-loss`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#f3a395" stopOpacity=".06"/><stop offset="1" stopColor="#f3a395" stopOpacity=".28"/></linearGradient><clipPath id={`${id}-above`}><rect width={width} height={Math.max(0, y(0))}/></clipPath><clipPath id={`${id}-below`}><rect y={y(0)} width={width} height={Math.max(0, height - y(0))}/></clipPath></defs>
                {scale.ticks.filter(tick => tick !== 0).map(tick => <line key={tick} x1="0" x2={width} y1={y(tick)} y2={y(tick)} className="fa-plot-grid"/>)}
                <path d={model.area} fill={`url(#${id}-gain)`} clipPath={`url(#${id}-above)`}/><path d={model.area} fill={`url(#${id}-loss)`} clipPath={`url(#${id}-below)`}/>
                <line x1="0" x2={width} y1={y(0)} y2={y(0)} className="fa-plot-zero"/>
                <path d={model.path} fill="none" stroke="#e0f5ed" strokeWidth="1.8" vectorEffect="non-scaling-stroke"/>
                <line x1={x(index)} x2={x(index)} y1="0" y2={height} className="fa-plot-crosshair"/>
            </svg><span aria-hidden="true" className="fa-plot-point" style={{ left: `${index / rows.length * 100}%`, top: `${y(value) / height * 100}%` }}/>
        </div>
        <div id={`${id}-drawdown`} className="fa-underwater" hidden={!showDrawdown}><div className="fa-underwater-heading"><span>Below previous peak</span><strong>{units(dips[index])}</strong><small>Deepest fall: {stats.drawdown.toFixed(1)}u</small></div>
            <div className="fa-plot-frame fa-drawdown-frame"><div className="fa-unit-axis" aria-hidden="true"><span style={{ top: 0 }}>0u</span>{stats.drawdown > 0 && <span style={{ top: '100%' }}>−{stats.drawdown.toFixed(1)}u</span>}</div><svg viewBox={`0 0 ${width} 65`} preserveAspectRatio="none" role="img" aria-label={`Drawdown below the previous profit peak. Deepest fall ${stats.drawdown.toFixed(1)} units. Horizontal spacing is by bet, not elapsed time.`} onPointerMove={inspect} onPointerDown={pointerDown}><path d={`${model.drawdownPath} L${width},0 L0,0 Z`} fill="#ee988722"/><path d={model.drawdownPath} fill="none" stroke="#e7a598" strokeWidth="1" vectorEffect="non-scaling-stroke"/><line x1="0" x2={width} y1="0" y2="0" className="fa-plot-grid"/><line x1={x(index)} x2={x(index)} y1="0" y2="65" className="fa-plot-crosshair"/></svg></div></div>
        <div className="fa-date-axis"><span>{date(rows[0].date)}</span><span>{date(rows.at(-1)!.date)}</span></div>
        <div className="fa-chart-readout" aria-live="polite" aria-atomic="true">{active ? <><div><span>Bet {index} · {date(active.date)}</span><strong>{active.home} {active.hg}–{active.ag} {active.away}</strong></div><div><span>Recorded bet price</span><strong>{price(active.price)}</strong></div><div><span>{active.won ? 'Winning bet' : 'Losing bet'}</span><strong className={active.won ? 'fa-positive' : 'fa-negative'}>{units(active.profit)}</strong></div></> : <div><span>Before the first bet</span><strong>Starting profit: 0u</strong></div>}</div>
        <label className="fa-chart-scrub">Inspect match<input aria-label="Inspect match on profit chart" aria-valuetext={active ? `Bet ${index}, ${active.home} against ${active.away}, cumulative profit ${units(value)}` : 'Before first bet, zero profit'} type="range" min="0" max={rows.length} value={index} onChange={e => setInspection({ rows, index: Number(e.target.value) })}/></label>
        <p className="fa-chart-footnote">One point per bet, in match order. Dashed line = break-even. Profit in units, not a bankroll or forecast.</p>
    </section>;
}
