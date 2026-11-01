"""Read-only research extract. No live model, schedule, ledger or price writes."""
import csv,gzip,json,hashlib,re,sys,unicodedata
from pathlib import Path
from datetime import date,datetime,timedelta
from collections import defaultdict,Counter


from tennis_breakpoint_evidence import valid_counts
from ace_compass_integrity import completed_score,match_best_of,event_phase



def build(root,cutoff):
    ROOT=Path(root); hashes={}; counts=Counter(); exclusions=[]
    def read(p):
        hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
    def norm(s):
        if ',' in s:a,b=s.split(',',1);s=b+' '+a
        return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode())
    def skey(r):return tuple(r.get(k,'') for k in ('winner_id','loser_id','tour_id','round_id'))
    def sets(s):return tuple((int(a),int(b)) for a,b in re.findall(r'(\d+)-(\d+)(?:\(\d+\))?',s))
    def write(name,rows):
        if not rows:return
        fields=list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/name).open('w',encoding='utf8',newline='') as h:
            w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
    
    S=ROOT/'data/oncourt'
    players={r['id']:r['name'] for r in read(S/'players_atp.csv')}
    tours={r['id']:r for r in read(S/'tours_atp.csv')}
    allgames=read(S/'games_atp.csv')
    games=defaultdict(list)
    for r in allgames:
        if '2020-01-01'<=r['date']<cutoff:games[skey(r)].append(r)
    stats=defaultdict(list)
    for r in read(S/'stat_atp.csv'):
        if skey(r) in games:stats[skey(r)].append(r)
    aliases={}
    for r in read(ROOT/'data/tennis-props/player-name-aliases.csv'):
        if r.get('tour','').lower()=='atp':aliases[norm(r['alias'])]=norm(r['player_name'])
    def nm(s):return aliases.get(norm(s),norm(s))
    sack=defaultdict(list)
    for p in sorted((ROOT/'data/sackmann').glob('atp_matches*202*.csv')):
        for r in read(p):
            if not r.get('tourney_date','').startswith(('2020','2021','2022','2023','2024','2025','2026')):continue
            if not completed_score(r.get('score')):continue
            key=(nm(r['winner_name']),nm(r['loser_name']),sets(r['score']))
            r['_file']=p.name;sack[key].append(r)
    
    rows=[]; result_index=defaultdict(list)
    for k,gg in games.items():
        g=gg[0];t=tours.get(g['tour_id'],{});wid,lid=g['winner_id'],g['loser_id']
        if str(t.get('rank')) not in {'2','3','4'}:continue
        tn=t.get('name','').lower()
        if any(x in tn for x in ('junior','itf','next gen','nextgen','laver cup','exhibition','wild card','wildcard','play-off','playoff','united cup','atp cup','davis cup','hopman','olympic','atp finals','masters cup','world tour finals')):continue
        if not players.get(wid) or not players.get(lid) or '/' in players[wid]+players[lid]:continue
        mid='atp:'+':'.join(k); base=dict(match_id=mid,edition_id=g['tour_id'],result_date=g['date'],tournament=t['name'],w_id=wid,l_id=lid,w_name=players[wid],l_name=players[lid],score=g['result'])
        result_index[tuple(sorted((nm(players[wid]),nm(players[lid]))))].append(base)
        reason=None
        if len({(r['date'],r['result']) for r in gg})!=1:reason='conflicting_results'
        elif not completed_score(g['result']):reason='unfinished_or_unsupported_score'
        phase=event_phase(g['round_id']);bo=match_best_of('ATP',t['name'],g['round_id'])
        ss={tuple(sorted(r.items())) for r in stats.get(k,[])}
        if reason is None and len(ss)!=1:reason='missing_or_conflicting_stats'
        v=valid_counts(stats[k][0],g['result']) if len(ss)==1 else None
        if reason is None and v is None:reason='invalid_reciprocal_bp_counts'
        sf={'1':'Hard','2':'Clay','3':'Indoor hard','4':'Carpet','5':'Grass','6':'Hard'}.get(t.get('court_id'))
        if reason is None and (not sf or not phase or bo not in (3,5)):reason='unknown_context'
        if reason:counts[reason]+=1;exclusions.append(dict(base,reason=reason));continue
        # Primary BO3 only. Keep BO5 result rows in audit, not this feature/history cohort.
        if bo!=3:counts['BO5_outside_scope']+=1;continue
        sp=sets(g['result']);gameswon=[sum(a[i] for a in sp) for i in (0,1)]
        tbwon=[sum({a,b}=={6,7} and ((a>b) if i==0 else (b>a)) for a,b in sp) for i in (0,1)]
        br=[v[p+'_bpfaced']-v[p+'_bpsaved'] for p in ('w','l')]
        sg=[gameswon[i]-tbwon[i]-br[1-i]+br[i] for i in (0,1)]
        if min(sg)<=0 or any(br[i]>sg[i] for i in (0,1)) or abs(sg[0]-sg[1])>1+sum(tbwon):
            counts['invalid_service_games']+=1;exclusions.append(dict(base,reason='invalid_service_games'));continue
        source='oncourt'; native_y=v['w_bpfaced']+v['l_bpfaced'];parity='not_available'
        candidates=[]
        for r in sack.get((nm(players[wid]),nm(players[lid]),sp),[]):
            sd=date.fromisoformat(r['tourney_date'][:4]+'-'+r['tourney_date'][4:6]+'-'+r['tourney_date'][6:8])
            if 0<=(date.fromisoformat(g['date'])-sd).days<=21 and (str(r.get('round','')).startswith('Q') and r.get('round')!='QF')==(phase=='qualifying'):
                candidates.append(r)
        if len(candidates)==1:
            r=candidates[0]
            try:
                vv={p+'_'+f:int(r[p+'_'+f]) for p in ('w','l') for f in ('bpFaced','bpSaved','SvGms')}
                ok=all(vv[p+'_SvGms']>0 and 0<=vv[p+'_bpSaved']<=vv[p+'_bpFaced'] and vv[p+'_bpFaced']-vv[p+'_bpSaved']<=vv[p+'_SvGms'] for p in ('w','l'))
                ok=ok and vv['w_SvGms']+vv['l_SvGms']==sum(gameswon)-sum(tbwon)
                if ok:
                    parity='equal' if all(v[p+'_'+f.lower()]==vv[p+'_'+f] for p in ('w','l') for f in ('bpFaced','bpSaved')) else 'different_prefer_sackmann'
                    for i,p in enumerate(('w','l')):
                        v[p+'_bpfaced']=vv[p+'_bpFaced'];v[p+'_bpsaved']=vv[p+'_bpSaved'];sg[i]=vv[p+'_SvGms']
                    source='sackmann:'+r['_file']
            except (KeyError,TypeError,ValueError):pass
        counts['source_'+source.split(':')[0]]+=1;counts['parity_'+parity]+=1
        row=dict(base,tour='ATP',level='Slam' if t.get('rank')=='4' else 'Masters' if t.get('rank')=='3' else '250_500',surface=sf,indoor=int(sf=='Indoor hard'),phase=phase,best_of=bo,round=g['round_id'],status='completed',source=source,source_parity=parity,native_y=native_y)
        for i,p in enumerate(('w','l')):
            q='l' if p=='w' else 'w';row.update({p+'_SvGms':sg[i],p+'_bpFaced':v[p+'_bpfaced'],p+'_bpSaved':v[p+'_bpsaved'],p+'_created':v[q+'_bpfaced'],p+'_converted':v[q+'_bpfaced']-v[q+'_bpsaved']})
        row['y']=row['w_bpFaced']+row['l_bpFaced'];rows.append(row)
    rows.sort(key=lambda r:(r['result_date'],r['match_id']))
    from types import SimpleNamespace
    from tennis_breakpoint_model import valid_row
    valid=[]
    for r in rows:
        if valid_row(SimpleNamespace(**r)):valid.append(r)
        else:exclusions.append(dict(r,reason='strict_v2_score_count_mismatch'))
    for p,h in hashes.items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('source_changed_during_history_build')
    return valid,dict(counts),exclusions,hashes
