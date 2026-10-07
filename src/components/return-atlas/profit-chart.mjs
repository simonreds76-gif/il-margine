const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const units = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}u`;
const monthName = key => new Intl.DateTimeFormat('en-GB', {month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${key}-01T12:00:00Z`));
const dateName = key => new Intl.DateTimeFormat('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(`${key}T12:00:00Z`));

// Input is the exact chronological, filtered ledger used by the ROI summary.
// Empty months are explicit zero-bet intervals, never invented match results.
export function profitSeries(rows) {
  let running = 0;
  const cumulative = rows.map((row, index) => ({...row, value: running += row.profit, number:index + 1}));
  const grouped = new Map();
  for (const row of rows) {
    const key = row.date.slice(0,7);
    const month = grouped.get(key) ?? {key,value:0,bets:0,wins:0};
    month.value += row.profit;
    month.bets++;
    month.wins += Number(row.won);
    grouped.set(key, month);
  }
  const monthly = [];
  if (rows.length) {
    const cursor = new Date(`${rows[0].date.slice(0,7)}-01T12:00:00Z`);
    const end = rows.at(-1).date.slice(0,7);
    while (cursor.toISOString().slice(0,7) <= end) {
      const key = cursor.toISOString().slice(0,7);
      monthly.push(grouped.get(key) ?? {key,value:0,bets:0,wins:0});
      cursor.setUTCMonth(cursor.getUTCMonth()+1);
    }
  }
  return {cumulative,monthly};
}

export function mountProfitChart(host, rows, players, {side='player',drawdown=0}={}) {
  const series = profitSeries(rows);
  let mode = 'cumulative';
  let selected = rows.length - 1;
  if (!rows.length) {
    host.innerHTML = '<h3>Profit history</h3><p>No matches in this selection. Widen the filters to see a record.</p>';
    return;
  }
  const pointName = point => mode === 'monthly' ? monthName(point.key) : dateName(point.date);
  function render() {
    const points = series[mode];
    selected = Math.min(Math.max(0,selected),points.length-1);
    const monthly = mode === 'monthly';
    const width=600, height=220, pad=12;
    const min=Math.min(0,...points.map(p=>p.value)), max=Math.max(0,...points.map(p=>p.value));
    const range=max-min || 1;
    const y=value=>pad+(height-2*pad)*(max-value)/range;
    const x=i=>monthly ? width*(i+.5)/points.length : pad+(width-2*pad)*(i+1)/points.length;
    const zero=y(0);
    const path=[`${pad},${zero}`,...points.map((p,i)=>`${x(i)},${y(p.value)}`)].join(' ');
    const colour=points.at(-1).value>=0?'var(--accent)':'var(--negative)';
    const grid=[max,(max+min)/2,min];
    const bars=monthly?points.map((p,i)=>`<rect x="${x(i)-Math.max(1,width/points.length*.65)/2}" y="${Math.min(y(p.value),zero)}" width="${Math.max(1,width/points.length*.65)}" height="${Math.max(1,Math.abs(y(p.value)-zero))}" rx="2" fill="${p.value>=0?'var(--accent)':'var(--negative)'}" opacity=".8"/>`).join(''):'';
    host.innerHTML=`<div class="profit-chart-heading"><div><span class="profit-eyebrow">THE RECORD IN VIEW</span><h3>Profit history</h3></div><div class="profit-view" role="group" aria-label="Profit chart view"><button type="button" data-chart-view="cumulative" aria-pressed="${!monthly}">Cumulative</button><button type="button" data-chart-view="monthly" aria-pressed="${monthly}">Monthly</button></div></div>
      <p class="profit-context">${monthly?'Profit in each calendar month.':'Running profit after each bet, starting from 0u.'} A unit is the same stake on every match.</p>
      <div class="profit-plot"><div class="profit-scale" aria-hidden="true">${grid.map(v=>`<span>${v.toFixed(1)}u</span>`).join('')}</div><svg data-profit-plot viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${monthly?'Monthly profit':'Cumulative profit by bet number'}. Use the selector below for exact values.">${grid.map(v=>`<line x1="0" x2="${width}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-dasharray="3 5"/>`).join('')}<line x1="0" x2="${width}" y1="${zero}" y2="${zero}" stroke="var(--muted)" opacity=".5"/>${monthly?bars:`<defs><linearGradient id="atlas-profit-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${colour}" stop-opacity=".22"/><stop offset="100%" stop-color="${colour}" stop-opacity=".015"/></linearGradient></defs><polygon points="${path} ${x(points.length-1)},${zero}" fill="url(#atlas-profit-fill)"/><polyline points="${path}" fill="none" stroke="${colour}" stroke-width="2.5" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`}<line data-chart-cursor x1="0" x2="0" y1="${pad}" y2="${height-pad}" stroke="var(--text)" opacity=".45" stroke-dasharray="3 4"/><circle data-chart-point r="5" fill="var(--text)" stroke="var(--panel)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg></div>
      <div class="profit-axis"><span>${monthly?monthName(points[0].key):'Bet 1'}</span><span>${monthly?'Calendar month':'Bets in date order'}</span><span>${monthly?monthName(points.at(-1).key):`Bet ${points.length}`}</span></div>
      <div class="profit-scrubber"><button type="button" data-chart-step="-1" aria-label="Previous ${monthly?'month':'bet'}">←</button><label><span>${monthly?'Inspect a month':'Inspect a bet'}</span><input data-chart-position type="range" min="0" max="${points.length-1}" step="1" value="${selected}" aria-label="${monthly?'Month in profit history':'Bet in profit history'}"></label><button type="button" data-chart-step="1" aria-label="Next ${monthly?'month':'bet'}">→</button></div>
      <div class="profit-inspection" data-chart-inspection></div><p class="profit-hint">Tap the chart or use the selector. <span>Largest fall from a previous peak: <strong>${drawdown.toFixed(1)}u</strong>.</span></p><span class="sr-only" data-chart-announcement aria-live="polite"></span>`;
    const slider=host.querySelector('[data-chart-position]');
    const plot=host.querySelector('[data-profit-plot]');
    function select(index, announce=false) {
      selected=Math.max(0,Math.min(points.length-1,index));
      const p=points[selected];
      slider.value=String(selected);
      slider.setAttribute('aria-valuetext',`${pointName(p)}, ${units(p.value)}${monthly?' profit': ' running profit'}`);
      const marker=host.querySelector('[data-chart-cursor]');
      marker.setAttribute('x1',x(selected));marker.setAttribute('x2',x(selected));
      const dot=host.querySelector('[data-chart-point]');
      dot.setAttribute('cx',x(selected));dot.setAttribute('cy',y(p.value));
      host.querySelector('[data-chart-step="-1"]').disabled=selected===0;
      host.querySelector('[data-chart-step="1"]').disabled=selected===points.length-1;
      const backed=players[side==='opponent'?p.opponent:p.playerId]?.name??'Player';
      const detail=monthly?`${p.bets} ${p.bets===1?'bet':'bets'}${p.bets?` · ${p.wins} won · ${p.bets-p.wins} lost`:' · no matches in this selection'}`:`Bet ${p.number} · ${escape(backed)} at ${p.odds.toFixed(2)} · ${p.won?'Won':'Lost'} (${units(p.profit)})`;
      host.querySelector('[data-chart-inspection]').innerHTML=`<div><time>${pointName(p)}</time><strong>${monthly?'Monthly profit':`${escape(players[p.playerId]?.name??'Player')} vs ${escape(players[p.opponent]?.name??'Opponent')}`}</strong><small>${detail}</small></div><div class="profit-readout ${p.value>=0?'positive':'negative'}"><strong>${units(p.value)}</strong><span>${monthly?'this month':'running profit'}</span></div>`;
      if(announce)host.querySelector('[data-chart-announcement]').textContent=slider.getAttribute('aria-valuetext');
    }
    select(selected);
    slider.addEventListener('input',()=>select(Number(slider.value)));
    host.querySelectorAll('[data-chart-step]').forEach(button=>button.addEventListener('click',()=>select(selected+Number(button.dataset.chartStep),true)));
    const nearest=event=>{
      const rect=plot.getBoundingClientRect(), position=(event.clientX-rect.left)/rect.width*width;
      return monthly?Math.floor(position/width*points.length):Math.round((position-pad)/(width-2*pad)*points.length)-1;
    };
    plot.addEventListener('click',event=>select(nearest(event),true));
    plot.addEventListener('pointermove',event=>{if(event.pointerType==='mouse')select(nearest(event));});
    host.querySelectorAll('[data-chart-view]').forEach(button=>button.addEventListener('click',()=>{
      const next=button.dataset.chartView;if(next===mode)return;
      mode=next;selected=series[mode].length-1;render();host.querySelector(`[data-chart-view="${mode}"]`).focus({preventScroll:true});
    }));
  }
  render();
}
