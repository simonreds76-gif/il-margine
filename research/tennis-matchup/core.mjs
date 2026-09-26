export const METRICS = {
  serve: ['Service points won', 'service points'],
  return: ['Return points won', 'return points'],
  first: ['First-serve points won', 'first-serve points'],
  second: ['Second-serve points won', 'second-serve points'],
  aces: ['Aces', 'An untouched serve that wins the point'],
  doubleFaults: ['Double faults', 'Two missed serves that lose the point'],
};
export const SURFACES = {'outdoor-hard':'Outdoor hard','indoor-hard':'Indoor hard',clay:'Clay',grass:'Grass'};

export function startDate(asOf, months) {
  if (months === 'archive') return '2022-01-01';
  const end = new Date(`${asOf}T00:00:00Z`);
  const first = new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-Number(months),1));
  const lastDay = new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate();
  first.setUTCDate(Math.min(end.getUTCDate(),lastDay));
  return [first.toISOString().slice(0,10),'2022-01-01'].sort().at(-1);
}

export function marketProbability(own, other) {
  if (!Number.isFinite(own) || !Number.isFinite(other) || own<=1 || other<=1) return null;
  return (1/own)/(1/own+1/other);
}

export function rowsFor(data, player, filters) {
  const start = startDate(filters.asOf, filters.months);
  return data.matches.filter(m => (m.p1===player || m.p2===player)
    && (filters.opponent===undefined || (m.p1===player?m.p2:m.p1)===filters.opponent)
    && m.date>=start && m.date<filters.asOf
    && (filters.surface==='all' || m.surface===filters.surface)
    && (filters.region==='all' || m.region===filters.region)
    && (filters.country==='all' || m.country===filters.country))
    .map(m=>{
      const first=m.p1===player;
      return {...m,won:m.winner===(first?0:1),opponent:first?m.p2:m.p1,odds:first?m.o1:m.o2,
        probability:marketProbability(first?m.o1:m.o2,first?m.o2:m.o1),
        stats:first?m.stats1:m.stats2};
    }).sort((a,b)=>a.date.localeCompare(b.date)||a.id.localeCompare(b.id));
}

export function wilson(wins, n) {
  if (!n) return null;
  const z=1.959964, p=wins/n, den=1+z*z/n;
  const middle=(p+z*z/(2*n))/den;
  const half=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;
  return [Math.max(0,middle-half),Math.min(1,middle+half)];
}

export function recordedCount(stats,key) {
  const pair=stats?.[key];
  return Array.isArray(pair)&&pair.length===2&&pair.every(Number.isFinite)&&pair[1]>0&&pair[0]>=0&&pair[0]<=pair[1]?pair[0]:null;
}

// Resample tournament editions as blocks, not supposedly independent tennis points.
// Descriptive range only: dependence between tournaments and model/price error remain.
export function residualRange(rows) {
  const groups=new Map();
  for(const r of rows) {
    if(r.probability===null || !r.eventKey) continue;
    const g=groups.get(r.eventKey)||[0,0];
    g[0]+=Number(r.won)-r.probability; g[1]++; groups.set(r.eventKey,g);
  }
  if(rows.length<30 || groups.size<8 || rows.some(r=>!r.eventKey || r.probability===null)) return null;
  const blocks=[...groups.entries()].sort(([a],[b])=>a.localeCompare(b)).map(([,v])=>v);
  let seed=73129;
  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  const values=[];
  for(let j=0;j<600;j++) {
    let sum=0,n=0;
    for(let i=0;i<blocks.length;i++) {const b=blocks[Math.floor(random()*blocks.length)];sum+=b[0];n+=b[1];}
    values.push(100*sum/n);
  }
  values.sort((a,b)=>a-b);
  return [values[Math.floor(.025*(values.length-1))],values[Math.ceil(.975*(values.length-1))]];
}

export function summary(rows) {
  const wins=rows.reduce((n,r)=>n+Number(r.won),0);
  const priced=rows.filter(r=>r.probability!==null);
  const expected=priced.reduce((n,r)=>n+r.probability,0);
  const actual=priced.reduce((n,r)=>n+Number(r.won),0);
  const metrics={};
  for(const key of Object.keys(METRICS)) {
    let numerator=0,denominator=0,matches=0;
    for(const row of rows) {
      const rate=row.stats?.[key];
      if(!Array.isArray(rate)||rate.length!==2||!rate.every(Number.isFinite)||rate[1]<=0||rate[0]<0||rate[0]>rate[1]) continue;
      numerator+=rate[0];denominator+=rate[1];matches++;
    }
    metrics[key]={numerator,denominator,matches,perMatch:matches?numerator/matches:null,rate:denominator?100*numerator/denominator:null};
  }
  return {n:rows.length,wins,losses:rows.length-wins,winRate:rows.length?100*wins/rows.length:null,
    winRange:wilson(wins,rows.length),priced:priced.length,expected,actual,
    residual:priced.length?actual-expected:null,
    residualPer100:priced.length?100*(actual-expected)/priced.length:null,
    range:residualRange(priced),events:new Set(rows.map(r=>r.eventKey).filter(Boolean)).size,
    first:rows[0]?.date,last:rows.at(-1)?.date,metrics};
}
