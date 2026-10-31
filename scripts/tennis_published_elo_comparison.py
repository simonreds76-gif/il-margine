"""Published-Elo arm of the existing Elo research comparison. Never live pricing.

No networking, message delivery, model fitting or source-table writes. Evidence
is available only from actual computation time; source editions are not vintages.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone,date,timedelta
from pathlib import Path
from types import SimpleNamespace
import copy,csv,hashlib,json,math,os
from tennis_elo_source import atomic,load,sha,digest,snapshot_current

VERSION='published-elo-full-input-v1'
FOLDER='published-source'
PROTOCOL={'version':VERSION,'arms':['current','published'],'real_stake':0,
 'primary':'paired match-winner log loss; Brier; edition uncertainty; ATP and Challenger separate',
 'coverage':'both players surface/overall and every 21-day opponent overall in BOTH tables; original activity must reproduce',
 'prices':'same verified first-capture Pinnacle quote <=2h; no extra download; fixed1u hypothetical',
 'selection':'available Strict gates primary; broad EV>=5% diagnostic; actual issued ledger separate',
 'handicap':'existing production H0 pair/fallback/calibration/guards; BO5 suppressed as in production; EV>=5% diagnostic only',
 'source_semantics':'TA surface fields already blended; incumbent writer semantics unverified; source replacement is confounded with semantics',
 'promotion':'never automatic; review at300 settled pairs and at least10 editions, separately by actual tier',
 'settlement':'unique exact native edition/playerIDs/round and saved kickoff date, complete score; explicit unresolved/void exclusions'}

def fixture(r):
 return ':'.join(map(str,[r['tour_id'],r['round_id'],*sorted([int(r['player1_id']),int(r['player2_id'])])]))
def joined(result):
 out,components,_=result;by={fixture(r):r for r in out}
 return {fixture(r):{**by.get(fixture(r),{}),**r} for r in components}
def clock(s):return datetime.fromisoformat(str(s).replace('Z','+00:00'))
def folder(output):return output/FOLDER
def model_hashes(root):
 from tennis_elo_shadow import MODEL_FILES,module
 files=list(MODEL_FILES)+['scripts/oncourt-compute-recent-activity.py','scripts/compute-handicap-values.py',
 'scripts/handicap_probs.py','scripts/spread_v1_model.py','scripts/tennis_published_elo_comparison.py',
 'data/backtest/spread-v1-calibration-params.json']
 result={p:sha(root/p) for p in files if (root/p).exists()}
 result['scripts/tennis_published_elo_comparison.py']=sha(__file__)
 import tennis_elo_shadow
 result['scripts/tennis_elo_shadow.py']=sha(tennis_elo_shadow.__file__)
 config=Path(os.environ.get('HANDICAP_CALIBRATION_FILE') or root/'data/backtest/spread-v1-calibration-params.json')
 result['active_handicap_calibration']=sha(config) if config.exists() else None
 result['pricing_environment']={k:os.environ.get(k) for k in ('HANDICAP_CALIBRATION_MODE','SPREAD_V1_ENABLE_CORRECTION_ONLY','SPREAD_V1_ALLOW_CORRECTION_SIGN_FLIP','SPREAD_V1_ALLOW_BO5')}
 return result

def compare_inputs(root,compute,baseline,ratings,activity,as_of):
 """Recompute dependent opponent averages and restore every mutable input."""
 from tennis_elo_shadow import module
 now=datetime.now(timezone.utc);frozen_hashes=model_hashes(root);original_ratings=dict(ratings);original_activity=copy.deepcopy(activity)
 try:
  snap=snapshot_current(root/'data/tennis-elo-source/atp',now,require_last_attempt_ok=True)
 except (ValueError,OSError) as e:return {'state':'unavailable','reason':str(e),'version':VERSION}
 fresh={}
 for p in snap['players']:
  pid=int(p['oncourt_id']);fresh[pid,'Overall']=float(p['overall'])
  for s,v in p['surface_blended'].items():
   if v is not None:fresh[pid,s]=float(v)
  if p['surface_blended'].get('Hard') is not None:fresh[pid,'I.hard']=float(p['surface_blended']['Hard'])
 rows=joined(baseline);ids={int(r[k]) for r in rows.values() for k in ('player1_id','player2_id')}
 act=module(root/'scripts/oncourt-compute-recent-activity.py');gamepath=root/'data/oncourt/games_atp.csv'
 gamehash=sha(gamepath);population,_=act.aggregate_activity([gamepath],ids,as_of)
 old_rows={r['player_id']:r for r in act.build_rows(population,{p:v for (p,s),v in ratings.items() if s=='Overall'})}
 fresh_rows={r['player_id']:r for r in act.build_rows(population,{p:v for (p,s),v in fresh.items() if s=='Overall'})}
 audit={};eligible=[]
 for key,r in rows.items():
  players=[int(r['player1_id']),int(r['player2_id'])];reasons=[];used=[]
  for pid in players:
   opponents=list(population.get(pid,{}).get('recent_opponents',[]))
   if pid not in population or pid not in old_rows or pid not in fresh_rows:
    reasons.append('recent_activity_population_missing');continue
   missing_old=[opp for opp in opponents if (opp,'Overall') not in ratings]
   missing_new=[opp for opp in opponents if (opp,'Overall') not in fresh]
   for arm,table in [('current',ratings),('published',fresh)]:
    if any((pid,s) not in table for s in ('Overall',r['surface'])):reasons.append(arm+'_player_rating_unavailable')
   if missing_old:reasons.append('current_opponent_rating_unavailable')
   if missing_new:reasons.append('published_opponent_rating_unavailable')
   saved=copy.deepcopy(original_activity.get(pid));rebuilt=old_rows[pid]
   mismatch=[f for f in rebuilt if f!='player_id' and (not saved or saved.get(f)!=rebuilt[f])]
   if mismatch:reasons.append('incumbent_activity_does_not_reproduce')
   used.append({'player_id':pid,'opponents':opponents,'missing_current_opponents':missing_old,'missing_published_opponents':missing_new,
    'current_ratings':{s:ratings.get((pid,s)) for s in ('Overall',r['surface'])},
    'published_ratings':{s:fresh.get((pid,s)) for s in ('Overall',r['surface'])},
    'saved_activity':saved,'rebuilt_current_activity':rebuilt,'rebuilt_published_activity':fresh_rows[pid],
    'activity_mismatch':mismatch,'opponent_ratings':[{'id':opp,'current':ratings.get((opp,'Overall')),'published':fresh.get((opp,'Overall'))} for opp in opponents]})
  audit[key]={'eligible':not reasons,'reasons':sorted(set(reasons)),'inputs':used}
  if not reasons:eligible.append(key)
 try:
  ratings.clear();ratings.update(fresh)
  for pid,rec in activity.items():
   if pid in fresh_rows:rec['avg_opponent_elo']=fresh_rows[pid]['avg_opponent_elo']
  changed=joined(compute('category_corrected',ml_only=False))
  if set(changed)!=set(rows):raise ValueError('published_fixture_universe_changed')
 finally:
  ratings.clear();ratings.update(original_ratings);activity.clear();activity.update(original_activity)
 assert ratings==original_ratings and activity==original_activity,'research_input_restore_failed'
 if sha(gamepath)!=gamehash:raise ValueError('activity_history_changed_during_capture')
 if model_hashes(root)!=frozen_hashes:raise ValueError('published_dependencies_changed_during_compute')
 return {'state':'compared','version':VERSION,'started_at':now.isoformat(),'completed_at':datetime.now(timezone.utc).isoformat(),
  'dependency_hashes':frozen_hashes,'snapshot_sha256':digest(snap),'snapshot_observed_at':snap['observed_at'],'snapshot_date':snap['publication_date'],
  'source_age_days':(now.date()-date.fromisoformat(snap['publication_date'])).days,'history_sha256':gamehash,
  'snapshot_observation_age_hours':(now-clock(snap['observed_at'])).total_seconds()/3600,
  'coverage':audit,'eligible_keys':eligible,'rows':{k:changed[k] for k in eligible},
  'counts':{'total':len(rows),'paired':len(eligible),'excluded':len(rows)-len(eligible)},
  'exclusions':dict(Counter(reason for v in audit.values() for reason in v['reasons']))}

def ml_selection(row,q,mode='gates'):
 p=round(float(row['p1_win_prob']),4);o=[float(q['odds1']),float(q['odds2'])];m=(1/o[0])/(1/o[0]+1/o[1])
 ev=[p*o[0]-1,(1-p)*o[1]-1];side=0 if ev[0]>=ev[1] else 1
 reasons=[]
 if ev[side]<.05-1e-12:reasons.append('ev_below5')
 if mode=='gates':
  if row['surface']!='Hard':reasons.append('not_outdoor_hard')
  if row['series']!='Masters 1000':reasons.append('not_masters')
  if row['confidence']!='high':reasons.append('not_high_confidence')
  if max(p,1-p)>.8:reasons.append('favourite_over80')
  if min(o)<1.25:reasons.append('odds_below1_25')
  if abs(max(p,1-p)-max(m,1-m))>.10:reasons.append('gap_over10pp')
  if side!=(0 if p>=.5 else 1) and max(p,1-p)>=.74:reasons.append('strong_favourite_dog')
 return {'side':side if not reasons else None,'odds':o[side],'ev':ev[side],'rejections':reasons}

def spread_quote(row,quotes,q):
 from tennis_category_shadow import full_name,tournament_tokens
 pair=[full_name(row['player1']),full_name(row['player2'])];found=[]
 for x in quotes:
  names=[full_name(x.get('player1_name','')),full_name(x.get('player2_name',''))]
  if set(pair)!=set(names) or x.get('kickoff_iso')!=q['kickoff_iso'] or x.get('captured_at')!=q['captured_at']:continue
  if not tournament_tokens(row.get('event_key') or row['tour_name'])<=tournament_tokens(x.get('league_name','')):continue
  if (row['official_category']=='Challenger')!=(x.get('league')=='Challenger'):continue
  try:
   line=float(x['spread_line']);odds=[float(x['spread_odds1']),float(x['spread_odds2'])]
   if not all(math.isfinite(v) for v in [line,*odds]) or min(odds)<=1:continue
   if abs(line*2-round(line*2))>1e-9:continue  # No quarter-line settlement implementation.
  except (ValueError,TypeError,KeyError):continue
  if names!=pair:line=-line;odds.reverse()
  found.append({'line':line,'odds':odds,'kickoff_iso':q['kickoff_iso'],'captured_at':q['captured_at'],'bookmaker':'Pinnacle','league':x.get('league')})
 unique={digest(x):x for x in found}
 return next(iter(unique.values())) if len(unique)==1 else None

def handicap(root,row,q,spread,centres):
 if not spread:return {'status':'no_verified_spread_quote'}
 from tennis_elo_shadow import module
 h=module(root/'scripts/compute-handicap-values.py')
 if int(row.get('best_of',3))==5:return {'status':'bo5_suppressed_by_live_policy'}
 p=float(row['p1_win_prob']);m=q['market_p1'];surface=row['surface'];bo='bo3'
 gap=abs(max(p,1-p)-max(m,1-m));flip=(p>=.5)!=(m>=.5) and abs(p-.5)>=h.MODEL_MARKET_FAV_SIDE_FLIP_BUFFER and abs(m-.5)>=h.MODEL_MARKET_FAV_SIDE_FLIP_BUFFER
 gates=gap>h.MODEL_MARKET_FAV_PROB_GAP_MAX or flip
 a,b=h._parse_point_prob(row.get('p_a')),h._parse_point_prob(row.get('p_b'));fallback=False
 if a is None or b is None or abs(h.match_win_probability(a,b,bo)-p)>h.POINT_PROB_MATCH_PROB_GAP_MAX:
  centre=centres.get((str(row['tour_id']),surface),centres.get(('',surface),h.SURFACE_LEAGUE_AVG.get(surface,h.SURFACE_LEAGUE_AVG['N/A'])))
  a,b=h._solve_spw_for_match_prob(p,centre,bo);fallback=True
 raw1,raw2,push=h._shape_cover_probabilities(a,b,spread['line'],bo)
 cfg=h.load_handicap_calibration(SimpleNamespace(disable_calibration=False,calibration_file=None))
 c1,c2=h._calibrate_prob(raw1,cfg),h._calibrate_prob(raw2,cfg)
 p1,reason=h.apply_correction(cfg.payload,base_prob=c1/(c1+c2),surface=surface,line=spread['line'],p1_match_prob=p,
  odds1=spread['odds'][0],odds2=spread['odds'][1],league=spread.get('league'),best_of=bo)
 p2=h._clamp(1-p1,1e-6,1-1e-6)
 if not h._env_bool('SPREAD_V1_ALLOW_CORRECTION_SIGN_FLIP',False) and any(raw*o-1<=0<cal*o-1 for raw,cal,o in zip([raw1,raw2],[p1,p2],spread['odds'])):
  p1,p2=raw1,raw2;reason='sign-flip-guard'
 ev=[p1*spread['odds'][0]-1,p2*spread['odds'][1]-1];side=0 if ev[0]>=ev[1] else 1
 return {'status':'priced','pair':[a,b],'fallback':fallback,'p1_conditional':p1,'p2_conditional':p2,'push':push,
  'raw':[raw1,raw2],'correction':reason,'calibration_enabled':cfg.enabled,'market_gate_blocked':gates,
  'selection':{'side':side if not gates and ev[side]>=.05 else None,'odds':spread['odds'][side],'ev':ev[side]},'quote':spread}

def save_capture(root,output,comparison,current,quotes,completed,*,source_hashes,evidence_path):
 """Append new comparison observations; never revise an earlier forecast."""
 dest=folder(output);dest.mkdir(parents=True,exist_ok=True)
 if not comparison or comparison.get('state')!='compared':
  atomic(dest/'health.json',{'state':'unavailable','checked_at':completed.isoformat(),'detail':comparison});return
 hashes=model_hashes(root);reg=load(dest/'registration.json',None)
 fingerprint={'protocol':PROTOCOL,'hashes':hashes}
 if reg and reg['fingerprint']!=fingerprint:
  atomic(dest/'health.json',{'state':'blocked','reason':'frozen_dependency_changed_review_required','checked_at':completed.isoformat()});return
 if comparison.get('dependency_hashes')!=hashes:raise ValueError('published_dependencies_changed_after_compute')
 from tennis_category_shadow import quote_for
 import gzip
 evidence=json.loads(gzip.decompress(evidence_path.read_bytes()));centres={}
 for packet in evidence['query_responses']:
  if packet.get('status')!=200:continue
  if packet['table']=='surface_league_averages':
   for r in packet['body']:
    if r.get('serve_point_win_pct') is not None:centres['',r['surface']]=float(r['serve_point_win_pct'])
  if packet['table']=='tournament_serve_profile':
   for r in packet['body']:
    if r.get('venue_avg_spw') is not None and int(r.get('match_count') or 0)>=50:centres[str(r['tour_id']),r['surface']]=float(r['venue_avg_spw'])
 ledger=load(dest/'ledger.json',[]);known={r['key'] for r in ledger};added=[];counts=Counter()
 for key,a in current.items():
  if key in known:counts['already_captured']+=1;continue
  q,reason=quote_for(a,quotes)
  if not q:counts[reason]+=1;continue
  q={**q,'orientation':'odds1 corresponds to current.player1; quote_for reverses source order when needed','bookmaker':'Pinnacle'}
  if clock(q['kickoff_iso'])<=datetime.now(timezone.utc):counts['started_during_compute']+=1;continue
  if clock(comparison['snapshot_observed_at'])>clock(comparison['started_at']):raise ValueError('future_source_snapshot')
  if clock(q['captured_at'])>completed or (completed-clock(q['captured_at'])).total_seconds()>7200:counts['quote_expired_during_compute']+=1;continue
  b=comparison['rows'].get(key);coverage=comparison['coverage'][key]
  sp=spread_quote(a,quotes,q)
  row={'key':key,'captured_at':completed.isoformat(),'kickoff':q['kickoff_iso'],'player1':a['player1'],'player2':a['player2'],
   'category':a['official_category'],'surface':a['surface'],'tournament':a['tour_name'],'edition':str(a['tour_id']),
   'snapshot_sha256':comparison['snapshot_sha256'],'snapshot_observed_at':comparison['snapshot_observed_at'],'snapshot_date':comparison['snapshot_date'],
   'source_age_days':comparison['source_age_days'],'coverage':coverage,'quote':q,'spread_quote':sp,'current':a,'published':b,
   'selections':{arm:{mode:ml_selection(r,q,mode) for mode in ['gates','ev5']} for arm,r in [('current',a),('published',b)] if r is not None},
   'handicap':{arm:handicap(root,r,q,sp,centres) for arm,r in [('current',a),('published',b)] if r is not None},
   'evidence_sha256':sha(evidence_path),'source_hashes':source_hashes,'result':'pending'}
  added.append(row)
 if model_hashes(root)!=hashes:raise ValueError('published_dependencies_changed_during_handicap_pricing')
 # Handicap calculations can finish after the full ML engine. Timestamp and
 # verify the completed batch, not merely the start of its final pricing stage.
 completed=datetime.now(timezone.utc);verified=[]
 for row in added:
  if clock(row['kickoff'])<=completed:counts['started_during_handicap_pricing']+=1;continue
  if (completed-clock(row['quote']['captured_at'])).total_seconds()>7200:counts['quote_expired_during_handicap_pricing']+=1;continue
  row['captured_at']=completed.isoformat()
  row['forecast_sha256']=digest(row);verified.append(row)
 added=verified
 if not reg:atomic(dest/'registration.json',{'registered_at':completed.isoformat(),'fingerprint':fingerprint})
 if added:atomic(dest/'ledger.json',ledger+added)
 atomic(dest/'latest.json',comparison)
 atomic(dest/'health.json',{'state':'captured' if added else 'no_new_verified_pairs','checked_at':completed.isoformat(),
  'new_observations':len(added),'new_paired':sum(r['published'] is not None for r in added),'quote_health':dict(counts),
  'coverage':comparison['counts'],'coverage_exclusions':comparison['exclusions'],'first_capture_verified':bool(added or ledger)})

def check_forecast(r):
 frozen={k:v for k,v in r.items() if k not in ('forecast_sha256',)}
 if digest(frozen)!=r['forecast_sha256']:raise ValueError('immutable_forecast_changed')

def settle(root,output):
 """Outcomes separate from immutable predictions. No heuristic rematch joins."""
 from tennis_event_integrity import completed_score
 dest=folder(output);ledger=load(dest/'ledger.json',[])
 if not ledger:return
 wanted={r['key'] for r in ledger};index=defaultdict(list)
 with (root/'data/oncourt/games_atp.csv').open(encoding='utf-8-sig',newline='') as stream:
  for g in csv.DictReader(stream):
   k=':'.join([g['tour_id'],g['round_id'],*sorted([g['winner_id'],g['loser_id']],key=int)])
   if k in wanted:index[k].append(g)
 old=load(dest/'outcomes.json',{});out=copy.deepcopy(old)
 for r in ledger:
  check_forecast(r)
  if r['key'] in old:continue
  matches={digest(g):g for g in index[r['key']]}
  if len(matches)!=1:continue
  g=next(iter(matches.values()))
  if g['date']!=r['kickoff'][:10]:continue
  if not completed_score(g['result']):
   if any(v in g['result'].lower() for v in ('ret','w/o','def')):out[r['key']]={'status':'research_void','score':g['result'],'source':g}
   continue
  import re
  sets=[(int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)',g['result'])]
  if sum(a>b for a,b in sets)!=int(r['current'].get('best_of',3))//2+1:continue
  y=int(str(g['winner_id'])==str(r['current']['player1_id']))
  out[r['key']]={'status':'settled','y':y,'margin_p1':sum(a-b for a,b in sets)*(1 if y else -1),'score':g['result'],'date':g['date'],'source':g}
 if out!=old:atomic(dest/'outcomes.json',out)

def measure(rows,outcomes,arm,mode='gates',market='ML',calibration_keys=None):
 usable=[r for r in rows if r.get(arm) is not None];wins=losses=pushes=void=pending=0;profit=0.;ll=[];brier=[];reliability=defaultdict(list)
 for r in usable:
  o=outcomes.get(r['key'],{});s=r['selections'][arm][mode] if market=='ML' else r['handicap'][arm].get('selection',{})
  if o.get('status')=='settled':
   if market=='ML':
    p=float(r[arm]['p1_win_prob']);y=o['y']
    if int(r[arm]['player1_id'])>int(r[arm]['player2_id']):p=1-p;y=1-y
    ll.append(-(y*math.log(max(1e-9,p))+(1-y)*math.log(max(1e-9,1-p))));brier.append((p-y)**2)
    reliability[min(9,int(p*10))].append((p,y))
   else:
    h=r['handicap'][arm]
    if h.get('status')=='priced' and not h.get('market_gate_blocked',False) and (calibration_keys is None or r['key'] in calibration_keys):
     result=o['margin_p1']+h['quote']['line']
     if abs(result)>1e-9:
      p=h['p1_conditional'];y=int(result>0);ll.append(-(y*math.log(max(1e-9,p))+(1-y)*math.log(max(1e-9,1-p))));brier.append((p-y)**2)
  if s.get('side') is None:continue
  if o.get('status')=='research_void':void+=1;continue
  if o.get('status')!='settled':pending+=1;continue
  if market=='ML':win=o['y']==(1-s['side'])
  else:
   delta=o['margin_p1']+r['handicap'][arm]['quote']['line']
   if abs(delta)<1e-9:pushes+=1;continue
   win=(delta>0)==(s['side']==0)
  if win:wins+=1;profit+=s['odds']-1
  else:losses+=1;profit-=1
 n=wins+losses
 return {'forecasts':len(usable),'scored_fixtures':len(ll),'settled_bets':n,'wins':wins,'losses':losses,'pushes':pushes,'research_void':void,'pending_bets':pending,
  'stake':n,'profit':round(profit,6),'roi_pct':100*profit/n if n else None,
  'log_loss':sum(ll)/len(ll) if ll else None,'brier':sum(brier)/len(brier) if brier else None,
  'reliability':[{'lower':k/10,'n':len(v),'mean_probability':sum(x for x,y in v)/len(v),'win_fraction':sum(y for x,y in v)/len(v)} for k,v in sorted(reliability.items())]}

def paired_accuracy(rows,outcomes):
 """Descriptive edition bootstrap, never used to tune or promote."""
 import random
 groups=defaultdict(list)
 for r in rows:
  o=outcomes.get(r['key'],{})
  if r.get('published') is None or o.get('status')!='settled':continue
  y=o['y'];a=float(r['current']['p1_win_prob']);b=float(r['published']['p1_win_prob'])
  loss=lambda p:-(y*math.log(max(1e-9,p))+(1-y)*math.log(max(1e-9,1-p)))
  groups[r['edition']].append((loss(b)-loss(a),(b-y)**2-(a-y)**2))
 pairs=[v for g in groups.values() for v in g];result={'fixtures':len(pairs),'editions':len(groups),'direction':'published minus current; negative improves','note':'Descriptive; fewer than10 editions is especially uncertain; no automatic promotion.'}
 if not pairs:return result
 result.update(log_loss=sum(a for a,b in pairs)/len(pairs),brier=sum(b for a,b in pairs)/len(pairs))
 if len(groups)>1:
  values=[groups[k] for k in sorted(groups)];rng=random.Random(5050);draws=[[],[]]
  for _ in range(1000):
   selected=[x for _ in values for x in values[rng.randrange(len(values))]]
   for j in (0,1):draws[j].append(sum(x[j] for x in selected)/len(selected))
  for j,key in enumerate(('log_loss_ci95','brier_ci95')):
   v=sorted(draws[j]);result[key]=[v[24],v[974]]
 return result

def report(output):
 dest=folder(output);rows=load(dest/'ledger.json',[]);outcomes=load(dest/'outcomes.json',{})
 for r in rows:check_forecast(r)
 cohorts={}
 for tier in ('ATP','Challenger'):
  allrows=[r for r in rows if (r['category']=='Challenger')==(tier=='Challenger')]
  paired=[r for r in allrows if r.get('published') is not None]
  common_cover={r['key'] for r in paired if all(r['handicap'][a].get('status')=='priced' and not r['handicap'][a].get('market_gate_blocked') for a in ('current','published'))}
  cohorts[tier]={}
  for label,rs,arm in [('current_all',allrows,'current'),('current_paired',paired,'current'),('published_paired',paired,'published')]:
   cohorts[tier][label]={mode:measure(rs,outcomes,arm,mode) for mode in ['gates','ev5']}
   cohorts[tier][label]['handicap']=measure(rs,outcomes,arm,market='handicap',calibration_keys=None if label=='current_all' else common_cover)
  cohorts[tier]['paired_accuracy']=paired_accuracy(paired,outcomes)
  cohorts[tier]['coverage']={'current_all':len(allrows),'paired':len(paired),'common_handicap_prices':len(common_cover)}
  cohorts[tier]['surfaces']={s:{a:measure([r for r in paired if r['surface']==s],outcomes,a) for a in ['current','published']} for s in sorted({r['surface'] for r in paired})}
 result={'name':'Published Elo input comparison','version':VERSION,'status':'PAPER_ONLY','health':load(dest/'health.json',{}),'protocol':PROTOCOL,
  'captured':len(rows),'paired':sum(r.get('published') is not None for r in rows),'settled':sum(x.get('status')=='settled' for x in outcomes.values()),
  'cohorts':cohorts,'surface_semantics_confounded':True,'no_live_change':True,
  'notes':['New observations only, not backdated.','No probability/ROI superiority established by small samples.','Hypothetical available gates lack actual injury/overlay selections.','Date/round mismatches remain unresolved; no silent nearest-result join.']}
 if dest.exists():atomic(dest/'report.json',result)
 return result

def selection_rows(output):
 dest=folder(output);outcomes=load(dest/'outcomes.json',{});out=[]
 for r in load(dest/'ledger.json',[]):
  for arm in ('current','published'):
   if r.get(arm) is None:continue
   s=r['selections'][arm]['gates'];side=s['side'];p=r[arm]['p1_win_prob'];o=outcomes.get(r['key'],{})
   won=(o['y']==1-side) if o.get('status')=='settled' and side is not None else None
   out.append({'date':r['kickoff'][:10],'match':r['player1']+' vs '+r['player2'],'model':'published-source / '+arm,
    'tournament':r['tournament'],'selection':[r['player1'],r['player2']][side] if side is not None else 'No qualifying selection',
    'market':'ML','odds':s['odds'] if side is not None else None,'fair_odds':round(1/(p if side==0 else 1-p),3) if side is not None else None,
    'stake':1 if side is not None else 0,'result':('W' if won else 'L') if won is not None else o.get('status','pending'),
    'profit':(s['odds']-1 if won else -1) if won is not None else None,'paper_only':True,'captured_at':r['captured_at']})
 return out

def weekly_text(r):
 if not r:return []
 lines=[f"PUBLISHED ELO | same formulas; {r.get('paired',0)} verified pairs; {r.get('settled',0)} results. No live change."]
 for tier,c in r.get('cohorts',{}).items():
  for arm in ('current_paired','published_paired'):
   m=c[arm]['gates'];d=c[arm]['ev5'];roi=f"{m['roi_pct']:+.2f}%" if m['roi_pct'] is not None else 'unavailable'
   dr=f"{d['roi_pct']:+.2f}%" if d['roi_pct'] is not None else 'unavailable'
   scores=f"All paired fixtures: LL {m['log_loss']:.4f}/Brier {m['brier']:.4f}" if m['log_loss'] is not None else 'paired accuracy awaiting results'
   lines.append(f"{tier} {arm}: gates {m['wins']}W/{m['losses']}L, {m['profit']:+.2f}u/{m['stake']}u, ROI {roi}; {m['pending_bets']} pending. EV5 diagnostic {d['settled_bets']} settled/ROI {dr}. {scores}.")
 lines.append('Challenger published-rating coverage is limited; its independent review may take months.')
 if r.get('health',{}).get('state') in ('blocked','unavailable'):lines.append('Published source comparison: '+r['health']['state'])
 return lines
