"""Build a display-only context snapshot. No probabilities, signals or credentials."""
import argparse,csv,json,sys,unicodedata
from datetime import datetime,timezone
from pathlib import Path

def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if c.isalnum() and ord(c)<128)
def build(root,notes_path):
 sys.path.insert(0,str(root/'scripts'))
 from tennis_break_point_history import histories
 names={r['id']:r['name'] for r in csv.DictReader((root/'data/oncourt/players_atp.csv').open(encoding='utf-8-sig'))}
 matches=list(csv.DictReader((root/'data/oncourt/today_atp.csv').open(encoding='utf-8-sig')))
 cut=datetime.now(timezone.utc).date().isoformat()
 selected=[r for r in matches if r['tour_id']=='21362' and not r.get('result')]
 ids={r[k] for r in selected for k in ('player1_id','player2_id')}
 requests=[('ATP','21362',i,cut) for i in ids]
 data=histories(root,requests)
 players={names[i]:{'name':names[i],'edition':'Paris 2026','history':data.get(('ATP','21362',i,cut),{}).get('logs',[])} for i in ids}
 source=json.loads(notes_path.read_text(encoding='utf-8'))
 games=[g for g in csv.DictReader((root/'data/oncourt/games_atp.csv').open(encoding='utf-8-sig')) if g['date']>='2026-11-04']
 notes=[]
 for n in source['records']:
  ids2=[[i for i,v in names.items() if norm(v)==norm(n[k])] for k in ('player','opponent')]
  if not all(len(i)==1 for i in ids2):continue
  exact=[g for g in games if {g['winner_id'],g['loser_id']}=={ids2[0][0],ids2[1][0]} and g['date']==n['posted_at'][:10]]
  if len(exact)!=1:continue
  notes.append({k:n.get(k) for k in ('player','opponent','kind','reported_area','posted_at','first_seen_at','url','correction_url')})
  notes[-1]['identity_note']='Player and match date matched to results; medical report not independently verified.'
 pace=next(r for r in csv.DictReader((root/'data/backtest/tennisabstract-atp-surface-speed.csv').open(encoding='utf-8-sig')) if r['tournament_name']=='Paris Masters' and r['season_year']=='2025')
 return {'generatedAt':datetime.now(timezone.utc).isoformat(),'historyBefore':cut,'players':players,'notes':notes,'notesObservedAt':source['observed_at'],'notesCoverage':'Partial public timeline; absence of a note does not establish fitness.','conditions':{'event':'Paris','year':2025,'speed':float(pace['ta_surface_speed']),'sample':None,'checkedAt':pace['updated_at'],'label':'Previous-season surface-speed estimate','limitation':'2025 event estimate, not a measurement of the 2026 court. Sample size was not supplied in the saved feed; no fast/slow classification is assigned.'}}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--notes',type=Path,required=True);a.add_argument('--output',type=Path,required=True);v=a.parse_args()
 result=build(v.root,v.notes);v.output.parent.mkdir(parents=True,exist_ok=True);v.output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8');print('Context snapshot:',len(result['players']),'players;',len(result['notes']),'identity-matched notes; no forecasts exported')
