export type SignalRow = Record<string, unknown>;
export type MonitorModel = {id:string;name:string;group:'current'|'research';note:string;views:Array<[string,string]>};
export const monitorModels:MonitorModel[] = [
 {id:'tennis',name:'Tennis match odds',group:'current',note:'Strict and Volume selections. Each strategy keeps its own record.',views:[['tennis-strict-live','Strict latest'],['tennis-volume200-live','Volume latest'],['tennis-strict-archive','Strict results'],['tennis-volume200-archive','Volume results']]},
 {id:'handicaps',name:'Tennis handicaps',group:'current',note:'Selected player and game handicap, with the recorded price.',views:[['tennis-spreadv1-live','Latest'],['tennis-spreadv1-archive','Results']]},
 {id:'props',name:'Aces & double faults',group:'current',note:'Paper selections for aces and double faults. Match forecasts are separate.',views:[['props-record','Tracked selections'],['aces-v3','ATP aces v3'],['props-board','Match forecasts']]},
 {id:'saves',name:'Goalkeeper saves',group:'current',note:'Tracked paper selections. The price ladder also includes alternatives that were not selected.',views:[['gk-record','Tracked selections'],['gk-candidates','Price ladder'],['gk-report','Performance']]},
 {id:'shots',name:'Team shots v4',group:'current',note:'Current Telegram selection model. Paper tracking; calibration comparisons remain separate research.',views:[['team-shots-v4-shadow-clv.csv','Tracked selections'],['football-candidates','Price scan']]},
 {id:'corners',name:'Corners v3',group:'current',note:'Current corners paper record. Different historical cohorts remain labelled.',views:[['corners-v3-shadow-clv.csv','Tracked selections'],['football-candidates','Price scan']]},
 {id:'goalscorer',name:'Goalscorers',group:'current',note:'Published selection records by league.',views:[['goalscorer-public','Serie A'],['epl-public','Premier League'],['la-liga-public','La Liga'],['bundesliga-public','Bundesliga'],['ligue-1-public','Ligue 1']]},
 {id:'scout',name:'Hardcourt Scout',group:'research',note:'Forward paper trial. Historical replay is not included in its forward record.',views:[['hardcourt-scout-v1','Performance & selections']]},
 {id:'astrissimo',name:'Astrissimo',group:'research',note:'Forward paper trial, separate from the live tennis model.',views:[['astrissimo-v1','Performance & selections']]},
 {id:'astra',name:'Astra Volume',group:'research',note:'Frozen forward paper trial. Current corrected inputs are shown separately from earlier inputs.',views:[['context-forward-v1','Performance']]},
 {id:'aces4',name:'Aces v4 calibration',group:'research',note:'Calibration observations are not bets. Only rows explicitly flagged as v4 signals appear as selections.',views:[['v4-report','Progress'],['aces-v4','Flagged selections']]},
 {id:'mostaces',name:'Most aces',group:'research',note:'Active paper research using verified browser prices. A forecast alone is not a value selection.',views:[['most-aces','Match forecasts'],['most-aces-record','Research observations']]},
 {id:'calibration',name:'Shots calibration',group:'research',note:'Comparison research, not the current Telegram selection model.',views:[['shots-calibration','Progress']]}
];
const tennisModel=monitorModels.find(m=>m.id==='tennis')!;
for(const [key,name] of [['volume200u','Volume expansion'],['challenger-ml-v2','Challenger ML v2'],['clay_bo3','Clay BO3'],['grass_bo3','Grass BO3'],['slam-bo5','Grand Slam BO5']]){
 tennisModel.views.push([`tennis-${key}-live`,`${name} latest`],[`tennis-${key}-archive`,`${name} results`]);
}
export const pick=(r:SignalRow,keys:string[])=>keys.map(k=>r[k]).find(v=>v!==undefined&&v!==null&&v!=='');
export const numeric=(v:unknown):number|null=>v===null||v===undefined||v===''||!Number.isFinite(Number(v))?null:Number(v);
export const text=(v:unknown)=>v===undefined||v===null||v===''?'':String(v);
const truth=(v:unknown)=>['true','1','yes'].includes(String(v).toLowerCase());
export function rowDate(r:SignalRow){return text(pick(r,['scheduled_start_utc','match_start_utc','kickoff_at','kickoff_utc','kickoff','match_date','scheduled_date','date']));}
export function selectionOutcome(r:SignalRow){
 const result=text(pick(r,['bet_outcome','result'])).toLowerCase();
 if(['won','win','lost','loss','void','push','half_win','half_loss','half_won','half_lost'].includes(result))return ({won:'Won',win:'Won',lost:'Lost',loss:'Lost',void:'Void',push:'Push',half_win:'Half win',half_won:'Half win',half_loss:'Half loss',half_lost:'Half loss'} as Record<string,string>)[result];
 const status=text(pick(r,['settlement_status','status'])).toLowerCase();
 if(status==='settled'&&r.won!==undefined&&r.won!==null)return truth(r.won)?'Won':'Lost';
 if(status==='settled'&&['0','1'].includes(String(r.won_bet)))return truth(r.won_bet)?'Won':'Lost';
 if(['won','win','lost','loss','void','push'].includes(status))return selectionOutcome({result:status});
 if(['pending','open','unsettled'].includes(status))return 'Pending';
 if(status==='settled')return 'Settled';
 if(r.quarantine_reason||r.duplicate_of_signal_id||r.duplicate_of)return 'Excluded';
 if(['blocked','quarantined','duplicate'].includes(status))return 'Excluded';
 return text(pick(r,['candidate_status','signal_status']))==='blocked'?'Blocked':'Not settled';
}
export function matchesOutcomeFilter(outcome:string,filter:string){
 if(filter==='pending')return ['Pending','Not settled'].includes(outcome);
 if(filter==='settled')return ['Won','Lost','Void','Push','Half win','Half loss','Settled'].includes(outcome);
 if(filter==='excluded')return ['Excluded','Blocked'].includes(outcome);
 return true;
}
export function selectionCard(r:SignalRow,view:string){
 const side=text(pick(r,['selected_side','side','recommended_side'])).toUpperCase();
 const mostAces=view==='most-aces-record';
 const paired=Boolean(r.player1&&r.player2),selectedIndex=side==='P1'?1:side==='P2'?2:null;
 const spread=text(r.bet_type).toLowerCase()==='spread';
 const selected=paired?(selectedIndex?text(r[`player${selectedIndex}`]):'Selection not specified'):text(pick(r,['player','goalkeeper','team']));
 const opponent=paired?(selectedIndex?text(r[`player${3-selectedIndex}`]):`${text(r.player1)} vs ${text(r.player2)}`):text(r.opponent);
 const market=text(r.market).replaceAll('_',' ');
 const ou=['OVER','UNDER'].includes(side)?`${side==='OVER'?'Over':'Under'} ${text(r.line)} ${market|| (view.startsWith('gk-')?'saves':'')}`.trim():'';
 const line=numeric(r.spread_line);
 const suppliedSelection=text(r.selection);
 const selection=mostAces?(side==='DRAW'||side==='TIE'||side==='X'?'Tie for most aces':`${selected} · Most aces`):paired?(spread?`${selected} ${line===null?'handicap':`${line>0?'+':''}${line} games`}`:`${selected}${selectedIndex?' to win':''}`):suppliedSelection||[selected,ou||(view.includes('public')?'to score':'')].filter(Boolean).join(' · ');
 let odds=numeric(pick(r,['selected_odds','odds_decimal','odds','book_price_at_publication','book_odds','best_bookmaker_odds']));
 let fair=numeric(pick(r,['fair_odds','model_fair_odds']));
 let ev=numeric(pick(r,['ev_pct','value_pct','edge_v4_pct']));
 if(paired&&selectedIndex){
   odds=numeric(spread?r.spread_odds:pick(r,['selected_odds',`pin_odds${selectedIndex}`]));
   fair=spread?numeric(pick(r,['spread_fair_odds','fair_odds'])):numeric(pick(r,['fair_odds',`our_odds${selectedIndex}`]));
   if(ev===null&&!spread)ev=numeric(r[`value_p${selectedIndex}`]);
 }
 if(fair===null&&!spread&&['OVER','UNDER'].includes(side))fair=numeric(r[side==='OVER'?'fair_over_odds':'fair_under_odds']);
 if(fair===null&&view==='hardcourt-scout-v1'){const p=numeric(r.probability);if(p!==null&&p>0&&p<1)fair=1/p;}
 if(ev===null){const fraction=numeric(pick(r,['edge','ev']));if(fraction!==null)ev=fraction*100;}
 if(mostAces){const outcomeKey=selectedIndex?`player${selectedIndex}`:['DRAW','TIE','X'].includes(side)?'draw':null;odds=outcomeKey?numeric(pick(r,['selected_odds',`open_${outcomeKey}_odds`])):null;fair=outcomeKey?numeric(r[`fair_${outcomeKey}`]):null;ev=outcomeKey?numeric(r[`value_${outcomeKey}_pct`]):null;}
 const outcome=selectionOutcome(r);
 const excluded=Boolean(r.quarantine_reason||r.duplicate_of_signal_id||r.duplicate_of||['quarantined','duplicate','excluded'].includes(text(r.status).toLowerCase()));
 const stake=numeric(pick(r,['stake_units','paper_stake','recommended_stake_units']));
 let profit=numeric(pick(r,['pnl_units','pnl'])),calculatedProfit=false;
 // Display arithmetic only for an explicit settled outcome, recorded stake and price.
 // Never assume 1u, grade a fixture, or write this value back to the ledger.
 if(profit===null&&!excluded&&stake!==null&&stake>=0&&odds!==null&&odds>1&&['Won','Lost','Void','Push'].includes(outcome)){
   profit=outcome==='Won'?stake*(odds-1):outcome==='Lost'?-stake:0;calculatedProfit=true;
 }
 return {selection:selection||text(r.match)||'Unnamed selection',opponent,fixture:paired?'':text(r.match)||[text(r.home_team),text(r.away_team)].filter(Boolean).join(' vs '),date:rowDate(r),odds,fair,ev,bookmaker:text(pick(r,['bookmaker','best_bookmaker']))||(paired&&selectedIndex&&!r.selected_odds&&numeric(r[`pin_odds${selectedIndex}`])!==null&&!spread?'Pinnacle':''),outcome:excluded?'Excluded':outcome,profit,stake,calculatedProfit,context:text(pick(r,['tournament','league','competition','series'])),version:text(pick(r,['model_version','history_version','cohort','signal_status'])),raw:r};
}
export function forecastGroups(rows:SignalRow[]){
 const groups=new Map<string,{title:string;date:string;context:string;rows:SignalRow[]}>();
 rows.forEach((r,index)=>{
   const players=[text(r.player||r.player1),text(r.opponent||r.player2)];
   // Pair reciprocal player forecasts only within the same dated tournament/context.
   const key=players.every(Boolean)?JSON.stringify([rowDate(r),r.tour||'',r.tournament||'',r.surface||'',r.round||'',r.event_id||'',players.map(p=>p.toLowerCase()).sort()]):`unmatched-${index}`;
   const group=groups.get(key)||{title:players.filter(Boolean).join(' vs ')||'Match not identified',date:rowDate(r),context:text(r.tournament),rows:[]};
   group.rows.push(r);groups.set(key,group);
 });
 return [...groups.values()];
}
export function visibleRows(rows:SignalRow[],view:string,model:string){
 if(model==='reference')return rows;
 if(view==='props-record')return rows.filter(r=>['aces','double_faults'].includes(text(r.market).trim().toLowerCase())&&r.decision_mode!=='breaks_calibration_unfiltered');
 if(view==='aces-v4')return rows.filter(r=>truth(r.v4_signal));
 if(view==='football-candidates'&&['shots','corners'].includes(model))return rows.filter(r=>r.model===(model==='shots'?'team_shots_v4':'corners_v3'));
 return rows;
}
