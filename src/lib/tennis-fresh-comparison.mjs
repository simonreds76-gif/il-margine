// Display-only comparison. Never creates selections or changes probabilities.
export function bestFreshComparison(row, now) {
 const finite=v=>v!==null&&v!==''&&Number.isFinite(Number(v))?Number(v):null;
 const generated=Date.parse(row.generated_at_utc||'');
 const forecastFresh=Number.isFinite(now)&&Number.isFinite(generated)&&generated<=now&&now-generated<=120*60000;
 const prices=Array.isArray(row.prices)?row.prices:[];
 const starts=new Set(prices.map(p=>Date.parse(p.start||'')).filter(Number.isFinite));
 const scheduleVerified=starts.size===1;
 return ['player1','draw','player2'].map(side=>{
   const probability=finite(row['p_'+side]);
   const quotes=prices.filter(p=>{
     const seen=Date.parse(p.captured_at||''), start=Date.parse(p.start||'');
     return scheduleVerified&&start>now&&seen<=now&&seen<start&&now-seen<=30*60000&&
       ['player1','draw','player2'].every(s=>{const o=finite(p[s+'_odds']);return o!==null&&o>1;})&&
       p.suspended!==true&&p.status!=='SUSPENDED';
   }).sort((a,b)=>Number(b[side+'_odds'])-Number(a[side+'_odds'])||Date.parse(b.captured_at)-Date.parse(a.captured_at));
   const best=quotes[0], odds=best?Number(best[side+'_odds']):null;
   const validProbability=probability!==null&&probability>0&&probability<1;
   const ready=forecastFresh&&validProbability&&odds!==null;
   return {side,probability,fair:validProbability?1/probability:null,odds,bookmaker:best?.bookmaker||null,
    observedAt:best?.captured_at||null,ageMinutes:best?Math.floor((now-Date.parse(best.captured_at))/60000):null,
    ev:ready?(probability*odds-1)*100:null,buffer:ready?(probability-1/odds)*100:null,
    reason:!scheduleVerified?'Start time unverified':!forecastFresh?'Forecast needs refresh':!best?'No fresh complete 1X2 quote':!validProbability?'Probability unavailable':'Fresh saved comparison'};
 });
}
