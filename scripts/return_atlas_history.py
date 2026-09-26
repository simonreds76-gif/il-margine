"""Build the private explorer from paired Pinnacle prices and reconciled results."""
import csv, hashlib, json, re, unicodedata, itertools, os
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from return_atlas_identity import source_player_id

CONFIG = json.loads(Path(os.environ['RETURN_ATLAS_CONFIG']).read_text(encoding='utf-8-sig'))
ROOT = Path(os.environ['RETURN_ATLAS_CANDIDATE'])
REPO = ROOT / 'oncourt'
PREVIEW = ROOT / 'preview'
AS_OF = os.environ.get('RETURN_ATLAS_AS_OF', date.today().isoformat())
YEARS = range(2022, date.fromisoformat(AS_OF).year + 1)
ARCHIVES = Path(CONFIG['archives'])
SOURCE_CACHE = Path(CONFIG['stateDirectory']) / 'source-cache'
for directory in [ROOT/'data', PREVIEW]: directory.mkdir(parents=True, exist_ok=True)
SOURCE = 'https://www.valuebetennis.com/en/donnees.htm'
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s.replace('ø','o')).lower() if c.isalnum())
def read(path, delimiter=','):
    return csv.DictReader(path.open(encoding='utf-8-sig', newline=''), delimiter=delimiter)
def sets(score):
    if re.search(r'ret|w/o|walk|def|abn|cancel|\[', score, re.I): return None
    score = re.sub(r'\(\d+\)', '', score).strip()
    if not re.fullmatch(r'\d+-\d+(?:\s+\d+-\d+)*', score): return None
    return [tuple(map(int, x.split('-'))) for x in score.split()]
def complete(score, needed):
    ss=sets(score)
    if not ss: return False
    wins=[0,0]
    for a,b in ss:
        if max(wins)>=needed: return False
        hi,lo=max(a,b),min(a,b)
        if not ((hi==6 and lo<=4) or (hi==7 and lo in [5,6]) or (hi>7 and hi-lo==2)): return False
        wins[a<b]+=1
    return wins[0]==needed and wins[1]<needed
def no_team(name):
    return not re.search(r'united cup|atp cup|davis|laver|next.?gen|olympic|exhibition|juniors', name, re.I)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

from functools import lru_cache
def build():
    players={r['id']:r for r in read(REPO/'players_atp.csv') if '/' not in r['name']}
    tours={r['id']:r for r in read(REPO/'tours_atp.csv') if r['date']>='2021-12-15' and r['rank'] in ['2','3','4'] and no_team(r['name'])}
    games=defaultdict(list)
    eligible=Counter()
    for r in read(REPO/'games_atp.csv'):
        if not ('2022-01-01'<=r['date']<=AS_OF) or r['tour_id'] not in tours: continue
        if r['winner_id'] not in players or r['loser_id'] not in players or int(r['round_id'])<4: continue
        tour=tours[r['tour_id']]
        if not complete(r['result'],3 if tour['rank']=='4' else 2): continue
        pair=tuple(sorted([norm(players[r['winner_id']]['name']),norm(players[r['loser_id']]['name'])]))
        games[pair].append({**r,'tour':tour})
        eligible[r['date'][:4]]+=1
    # This second archive is a cross-check; it has only partial 2026 coverage.
    independent=defaultdict(list)
    for y in YEARS:
        independent_path = ARCHIVES / f'lab-model-release/data/sackmann/atp_matches_{y}.csv'
        if not independent_path.exists(): continue
        for r in read(independent_path):
            if r['tourney_level'] not in ['A','M','G','F'] or not no_team(r['tourney_name']): continue
            pair=tuple(sorted([norm(r['winner_name']),norm(r['loser_name'])]))
            independent[pair].append(r)
    canonical={}; player_oc={}; matches=[]; audit={}; quarantine=[]; seen=set(); seen_games=set(); files=[]
    surfaces={'dur':'outdoor-hard','terre battue':'clay','gazon':'grass','dur int\ufffdrieur':'indoor-hard','dur intérieur':'indoor-hard'}
    for y in YEARS:
        path=ARCHIVES/'outputs/atp-returns-design-20260919/data'/f'valuebetennis-atp-{y}.csv' if y<2025 else SOURCE_CACHE/f'valuebetennis-{y}.csv'
        files.append({'path':str(path),'sha256':sha(path),'source':f'https://www.valuebetennis.com/datasets/valuebetennis-matchs-{y}.csv'})
        counts=Counter(); first=None; last=None
        for r in read(path,',' if y<2025 else ';'):
            if r['genre']!='atp' or r['categorie'] not in ['Main tour','Masters','Grand Chelem']: continue
            counts['source_atp_category_rows']+=1
            def reject(reason):
                counts[reason]+=1
                quarantine.append({'id':r['match_id'],'date':r['date'],'event':r['tournoi'],'players':[r['joueur1'],r['joueur2']],'reason':reason})
            if r['match_id'] in seen: reject('duplicate_source_id'); continue
            seen.add(r['match_id'])
            if not no_team(r['tournoi']): reject('team_or_special_event'); continue
            if int(r['tour'])<4: reject('qualifying'); continue
            counts['main_draw_source_rows']+=1
            if r['vainqueur_id'] not in [r['joueur1_id'],r['joueur2_id']]: reject('invalid_winner');continue
            ss=sets(r['score']); p1win=r['vainqueur_id']==r['joueur1_id']
            oriented=' '.join(f'{a}-{b}' if p1win else f'{b}-{a}' for a,b in (ss or []))
            source_complete=complete(oriented,3 if r['categorie']=='Grand Chelem' else 2)
            if source_complete: counts['completed_source_rows']+=1
            try: odds=[float(r['cote1_cloture']),float(r['cote2_cloture'])]
            except ValueError: reject('missing_paired_prices');continue
            if not all(1<o<1001 for o in odds): reject('invalid_prices');continue
            if r['surface'] not in surfaces: reject('unknown_surface');continue
            day=r['date'][:10]; pair=tuple(sorted([norm(r['joueur1']),norm(r['joueur2'])]))
            candidates=[g for g in games.get(pair,[]) if abs((date.fromisoformat(g['date'])-date.fromisoformat(day)).days)<=1 and norm(g['tour']['name'])==norm(r['tournoi']) and g['round_id']==r['tour']]
            if len(candidates)!=1: reject('unmatched_result' if not candidates else 'ambiguous_result');continue
            g=candidates[0]; winning_name=r['joueur1'] if p1win else r['joueur2']
            if norm(players[g['winner_id']]['name'])!=norm(winning_name): reject('result_disagreement');continue
            if source_complete and sets(g['result'])!=sets(oriented): reject('score_disagreement');continue
            if not source_complete: counts['partial_source_score_resolved_from_archive']+=1
            oriented=g['result']
            expected={'1':'outdoor-hard','2':'clay','3':'indoor-hard','5':'grass'}.get(g['tour']['court_id'])
            if expected!=surfaces[r['surface']]: reject('surface_disagreement');continue
            game_key=(g['date'],g['tour_id'],g['round_id'],g['winner_id'],g['loser_id'])
            if game_key in seen_games: reject('duplicate_fixture');continue
            seen_games.add(game_key)
            sid1=source_player_id(r['joueur1_id'],g['winner_id'] if p1win else g['loser_id'])
            sid2=source_player_id(r['joueur2_id'],g['loser_id'] if p1win else g['winner_id'])
            winner=sid1 if p1win else sid2
            for sid,name,ocid in [(sid1,r['joueur1'],g['winner_id'] if p1win else g['loser_id']),(sid2,r['joueur2'],g['loser_id'] if p1win else g['winner_id'])]:
                if sid in canonical and norm(canonical[sid]['name'])!=norm(name): raise ValueError('Conflicting source player identity '+sid)
                player_oc[ocid]=sid
                canonical[sid]={'id':sid,'name':name,'country':players[ocid]['country'],'initials':''.join(x[0] for x in name.split()[:2]),'index':len(canonical) if sid not in canonical else canonical[sid]['index']}
            # Full-name result confirmation is supplementary, never a guessed identity join.
            extra=[s for s in independent.get(pair,[]) if -1<=(date.fromisoformat(day)-date.fromisoformat(s['tourney_date'][:4]+'-'+s['tourney_date'][4:6]+'-'+s['tourney_date'][6:8])).days<=15]
            checked=[s for s in extra if norm(s['winner_name'])==norm(winning_name) and sets(s['score'])==sets(oriented)]
            if extra and not checked: counts['secondary_archive_disagreement']+=1
            elif checked: counts['secondary_archive_confirmed']+=1
            else: counts['secondary_archive_unmatched']+=1
            matches.append({'id':'vbt-'+r['match_id'],'date':day,'p1':sid1,'p2':sid2,'o1':odds[0],'o2':odds[1],'winner':winner,'surface':surfaces[r['surface']],'status':'completed','level':'ATP-main','event':r['tournoi'],'round':r['tour'],'score':oriented,'scoreOrientation':'winner-first','source':'Valuebetennis','priceBasis':'Pinnacle last recorded pre-match','resultArchive':'OnCourt','secondaryConfirmed':bool(checked)})
            counts['accepted']+=1;first=min(first or day,day);last=max(last or day,day)
        audit[str(y)]={**counts,'first':first,'last':last,'archive_completed_main_draw_matches':eligible[str(y)]}
    # Supplement missing matches with the saved same-bookmaker workbook series.
    # PSW/PSL prices do not establish a closing timestamp; retain that distinction.
    import openpyxl
    date_games=defaultdict(list)
    for entries in games.values():
        for g in entries: date_games[g['date']].append(g)
    @lru_cache(maxsize=100000)
    def abbreviated(short, full):
        parts=short.replace('-',' ').split()
        if len(parts)<2:return False
        initials=norm(parts[-1]);surname=norm(' '.join(parts[:-1]))
        fullparts=re.findall(r'[^\W\d_]+', unicodedata.normalize('NFKD',full), re.UNICODE)
        fullparts=[norm(x) for x in fullparts if norm(x)]
        if not initials or not fullparts or initials[0]!=fullparts[0][0]:return False
        tails=fullparts[1:]
        return any(surname==''.join(chunk) for n in range(1,len(tails)+1) for chunk in itertools.combinations(tails,n))
    supplement=Counter()
    for fileyear in YEARS:
        path=Path(CONFIG['oncourt']).parent/'backtest'/f'atp-{fileyear}.xlsx'
        if not path.exists(): continue
        files.append({'path':str(path),'sha256':sha(path),'source':'https://www.tennis-data.co.uk/','priceBasis':'Pinnacle PSW/PSL archived snapshot; closing timestamp unverified'})
        wb=openpyxl.load_workbook(path,read_only=True,data_only=True);it=iter(wb.active.values);head=next(it)
        for index,values in enumerate(it,2):
            r=dict(zip(head,values))
            if r.get('Comment')!='Completed': continue
            day=str(r['Date'])[:10]
            if day[:4] not in audit:continue
            try: odds=[float(r['PSW']),float(r['PSL'])]
            except (TypeError,ValueError):continue
            if not all(1<o<1001 for o in odds):continue
            window=[(date.fromisoformat(day)+timedelta(days=delta)).isoformat() for delta in [-1,0,1]]
            candidates=[g for d in window for g in date_games.get(d,[]) if abbreviated(r['Winner'],players[g['winner_id']]['name']) and abbreviated(r['Loser'],players[g['loser_id']]['name'])]
            if len(candidates)!=1: supplement['unresolved_or_ambiguous_workbook_join']+=1;continue
            g=candidates[0];game_key=(g['date'],g['tour_id'],g['round_id'],g['winner_id'],g['loser_id'])
            if game_key in seen_games:continue
            # Match the workbook set scores as well as the named result.
            try: score=[(int(r[f'W{i}']),int(r[f'L{i}'])) for i in range(1,6) if r.get(f'W{i}') is not None and r.get(f'L{i}') is not None]
            except (TypeError,ValueError): supplement['workbook_score_unknown']+=1;continue
            if score!=sets(g['result']):supplement['workbook_score_disagreement']+=1;continue
            surface={'1':'outdoor-hard','2':'clay','3':'indoor-hard','5':'grass'}.get(g['tour']['court_id'])
            if not surface:continue
            pids=[]
            for oid in [g['winner_id'],g['loser_id']]:
                sid=player_oc.get(oid,'oc-'+oid);player_oc[oid]=sid;pids.append(sid)
                if sid not in canonical:
                    p=players[oid];canonical[sid]={'id':sid,'name':p['name'],'country':p['country'],'initials':''.join(x[0] for x in p['name'].split()[:2]),'index':len(canonical)}
            matches.append({'id':f'tsd-{fileyear}-{index}','date':g['date'],'p1':pids[0],'p2':pids[1],'o1':odds[0],'o2':odds[1],'winner':pids[0],'surface':surface,'status':'completed','level':'ATP-main','event':g['tour']['name'],'round':g['round_id'],'score':g['result'],'scoreOrientation':'winner-first','source':'Tennis-Data','priceBasis':'Pinnacle archived snapshot (closing time unverified)','resultArchive':'OnCourt'})
            seen_games.add(game_key);a=audit[g['date'][:4]];a['archive_supplement']=a.get('archive_supplement',0)+1;a['accepted']+=1;a['first']=min(a['first'] or g['date'],g['date']);a['last']=max(a['last'] or g['date'],g['date'])
        wb.close()
    capture_path=ARCHIVES/'outputs/tennis-rebuild-20260909/prices/ml-real-scored-atp.csv'
    files.append({'path':str(capture_path),'sha256':sha(capture_path),'source':'Saved Pinnacle capture archive','priceBasis':'Timestamp-checked pre-match capture; not assumed closing'})
    for r in read(capture_path):
        if r['publication_timing_quality'] not in ['verified_prestart','inferred_prior_day']:continue
        try:
            captured=datetime.fromisoformat(r['publication_at'].replace('Z','+00:00'))
            kickoff=datetime.fromisoformat(r['kickoff_iso'].replace('Z','+00:00')) if r['kickoff_iso'] else None
            if kickoff is not None:
                if captured>=kickoff:continue
            elif captured.astimezone(timezone.utc).date().isoformat()>=r['match_date']:continue
            odds=[float(r['ml_odds1']),float(r['ml_odds2'])]
        except (ValueError,TypeError):continue
        if not all(1<o<1001 for o in odds):continue
        candidates=[g for g in date_games.get(r['match_date'],[]) if g['tour_id']==r['tour_id'] and g['round_id']==r['round_id'] and {g['winner_id'],g['loser_id']}=={r['player1_id'],r['player2_id']}]
        if len(candidates)!=1:continue
        g=candidates[0];game_key=(g['date'],g['tour_id'],g['round_id'],g['winner_id'],g['loser_id'])
        if game_key in seen_games:continue
        if g['winner_id']!=r['actual_winner_id'] or sets(g['result'])!=sets(r['result']):continue
        pids=[]
        for oid in [r['player1_id'],r['player2_id']]:
            sid=player_oc.get(oid,'oc-'+oid);player_oc[oid]=sid;pids.append(sid)
            if sid not in canonical:
                p=players[oid];canonical[sid]={'id':sid,'name':p['name'],'country':p['country'],'initials':''.join(x[0] for x in p['name'].split()[:2]),'index':len(canonical)}
        surface={'1':'outdoor-hard','2':'clay','3':'indoor-hard','5':'grass'}.get(g['tour']['court_id'])
        if not surface:continue
        matches.append({'id':'capture-'+r['match_key'],'date':g['date'],'p1':pids[0],'p2':pids[1],'o1':odds[0],'o2':odds[1],'winner':player_oc[g['winner_id']],'surface':surface,'status':'completed','level':'ATP-main','event':g['tour']['name'],'round':g['round_id'],'score':g['result'],'scoreOrientation':'winner-first','source':'Il Margine capture','priceBasis':'Pinnacle captured pre-match (not assumed closing)','priceCapturedAt':r['publication_at'],'resultArchive':'OnCourt'})
        seen_games.add(game_key);a=audit[g['date'][:4]];a['captured_supplement']=a.get('captured_supplement',0)+1;a['accepted']+=1
    eligible_records=[]
    for entries in games.values():
        for g in entries:
            surf={'1':'outdoor-hard','2':'clay','3':'indoor-hard','5':'grass'}.get(g['tour']['court_id'])
            for oid in [g['winner_id'],g['loser_id']]:
                if oid in player_oc: eligible_records.append([player_oc[oid],g['date'],surf])
    metadata={'years':list(YEARS),'through':max(m['date'] for m in matches),'matches':len(matches),'players':len(canonical),'source':SOURCE,'licence':'Valuebetennis CC BY 4.0; supplemental Tennis-Data archive reviewed locally','priceBasis':'Pinnacle: last pre-match plus archived snapshots','coverage':audit,'supplementAudit':dict(supplement),'files':files,'resultArchives':[{'path':str(REPO/p),'sha256':sha(REPO/p)} for p in ['games_atp.csv','players_atp.csv','tours_atp.csv']],'limitations':[f'{date.fromisoformat(AS_OF).year} is a partial season. Coverage excludes missing prices, unresolved joins and incomplete scores.','Valuebetennis closing means the provider’s last recorded pre-match price; it can differ from the final market tick. Tennis-Data snapshots have no verified closing timestamp and are labelled separately.','OnCourt result agreement is not a guarantee of upstream source independence. Sackmann is a supplementary check and its local 2026 file ends during Roland Garros.']}
    (ROOT/'data'/'audit.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    uncovered=[{'date':g['date'],'event':g['tour']['name'],'winner':players[g['winner_id']]['name'],'loser':players[g['loser_id']]['name']} for entries in games.values() for g in entries if (g['date'],g['tour_id'],g['round_id'],g['winner_id'],g['loser_id']) not in seen_games]
    (ROOT/'data'/'uncovered-results.json').write_text(json.dumps(uncovered,indent=2),encoding='utf-8')
    (ROOT/'data'/'quarantine.json').write_text(json.dumps(quarantine,ensure_ascii=False,indent=2),encoding='utf-8')
    matches.sort(key=lambda m:(m['date'],m['id']))
    (PREVIEW/'real-data.mjs').write_text('export const metadata='+json.dumps({k:v for k,v in metadata.items() if k not in ['files','resultArchives']},ensure_ascii=False,separators=(',',':'))+';\nexport const eligibleRecords='+json.dumps(eligible_records,separators=(',',':'))+';\nexport const players='+json.dumps(list(canonical.values()),ensure_ascii=False,separators=(',',':'))+';\nexport const matches='+json.dumps(matches,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(json.dumps({'matches':len(matches),'players':len(canonical),'coverage':audit},indent=2))
if __name__=='__main__':build()
