import copy,csv,json,tempfile,unittest
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oncourt_recent_history_sync import KEY,STAT,prepare,append_contracts,sync_recent_history,Store
from unittest.mock import patch,Mock

def write_csv(root,name,fields,data):
 with (root/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)

class FakeStore:
 def __init__(self):self.tables={'oncourt_players':[{'id':1}],'oncourt_games':[],'oncourt_stat':[]};self.calls=[]
 def read(self,table,params):return copy.deepcopy(self.tables[table])
 def append(self,table,data,on_conflict):
  self.calls.append((table,copy.deepcopy(data),on_conflict));self.tables[table].extend(copy.deepcopy(data))

class SyncTests(unittest.TestCase):
 def fixture(self,root):
  game=dict(zip(KEY,[1,2,30,4]));game.update(date='2026-11-11',result='7-5 6-3')
  write_csv(root,'games_atp.csv',[*KEY,'date','result'],[game,{**game,'tour_id':29,'date':'2026-09-01'}])
  stat={**{k:game[k] for k in KEY},**{f:10 for f in STAT}}
  write_csv(root,'stat_atp.csv',[*KEY,*STAT],[stat])
  write_csv(root,'players_atp.csv',['id','name','birthdate','country'],[{'id':1,'name':'A','birthdate':'1990-01-01','country':'GBR'},{'id':2,'name':'B','birthdate':'1991-01-01','country':'USA'}])
  return game,stat
 def test_recent_only_and_exact_stats_join(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);g,s=self.fixture(p);games,stats,report=prepare(p,date(2026,11,12))
   self.assertEqual(list(games.values()),[g]);self.assertEqual(list(stats.values()),[s]);self.assertEqual(report['through'],'2026-11-11')
 def test_new_opponent_parent_added_and_second_run_idempotent(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p);store=FakeStore()
   a=sync_recent_history(p,'',{},today=date(2026,11,12),store=store)
   self.assertEqual(a['players_added'],1);self.assertEqual(a['games']['appended'],1);self.assertEqual(a['stats']['appended'],1)
   b=sync_recent_history(p,'',{},today=date(2026,11,12),store=store)
   self.assertEqual(b['games']['appended'],0);self.assertEqual(b['stats']['appended'],0);self.assertEqual(b['historical_rows_overwritten'],0)
 def test_existing_result_conflict_is_preserved(self):
  store=FakeStore();g={**dict(zip(KEY,[1,2,30,4])),'date':'2026-11-11','result':'6-0 6-0'};store.tables['oncourt_games']=[g]
  new={**g,'result':'7-5 6-3'};r=append_contracts(store,'oncourt_games',{tuple(g[k] for k in KEY):new})
  self.assertEqual(r['appended'],0);self.assertEqual(len(r['existing_conflicts']),1);self.assertEqual(store.tables['oncourt_games'],[g])
 def test_missing_readback_is_failure(self):
  store=FakeStore();store.append=lambda *a:None;g={**dict(zip(KEY,[1,2,30,4])),'date':'2026-11-11','result':'7-5 6-3'}
  with self.assertRaisesRegex(RuntimeError,'readback'):append_contracts(store,'oncourt_games',{tuple(g[k] for k in KEY):g})
 def test_conflicting_local_rows_quarantined_without_overwriting(self):
  from oncourt_recent_history_sync import unique
  a=dict(zip(KEY,[1,2,3,4]));a['result']='6-0 6-0';b={**a,'result':'6-1 6-1'}
  accepted,conflicts=unique([a,b,{**a,'tour_id':9}]);self.assertEqual(len(accepted),1);self.assertEqual(conflicts,[(1,2,3,4)])
 def test_http_append_never_merges_existing_records(self):
  store=Store('https://example.invalid',{'apikey':'dummy'})
  with patch('oncourt_recent_history_sync.requests.post',return_value=Mock(ok=True)) as post:
   store.append('oncourt_games',[{'id':1}],'id')
  self.assertEqual(post.call_args.kwargs['headers']['Prefer'],'resolution=ignore-duplicates,return=minimal')
 def test_failure_does_not_echo_authentication(self):
  store=Store('https://example.invalid',{'apikey':'dummy'})
  with patch('oncourt_recent_history_sync.requests.get',return_value=Mock(ok=False,status_code=503,text='secret')):
   with self.assertRaisesRegex(RuntimeError,'HTTP 503') as e:store.read('oncourt_games',{})
  self.assertNotIn('secret',str(e.exception))

if __name__=='__main__':unittest.main()
