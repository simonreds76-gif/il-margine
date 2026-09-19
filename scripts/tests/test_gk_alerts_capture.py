from datetime import datetime, timezone, timedelta
from pathlib import Path
import importlib.util
import sys
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).parent))
from test_goalkeeper_saves_live import capture, shadow, load_script
alerts=load_script('gk_alerts','goalkeeper-saves-alerts.py')
class NewGkTests(unittest.TestCase):
 def test_all_five_leagues_fit_in_three_batches(self):
  now=datetime(2026,9,19,10,tzinfo=timezone.utc)
  leagues=['England - Premier League','Italy - Serie A','Germany - Bundesliga','Spain - La Liga','France - Ligue 1']
  events=[{'id':i,'league':{'name':leagues[i//6]},'date':'2026-09-19T20:00:00Z'} for i in range(1,30)]
  selected=capture.supported_events(events,max_events=30,kickoff_within_minutes=1440,now=now)
  self.assertEqual(len(selected),29);self.assertEqual(len({capture.event_league(e) for e in selected}),5)
 def test_overflow_rotates_previously_unseen_fixtures(self):
  now=datetime(2026,9,19,10,tzinfo=timezone.utc)
  events=[{'id':i,'league':'France - Ligue 1','date':'2026-09-19T20:00:00Z'} for i in range(1,42)]
  seen={str(i):'2026-09-19T09:00:00Z' for i in range(1,31)}
  selected=capture.supported_events(events,max_events=30,kickoff_within_minutes=1440,now=now,last_seen=seen)
  self.assertTrue(set(range(31,42)).issubset({e['id'] for e in selected}));self.assertEqual(len(selected),30)
 def test_batch_timeout_keeps_successful_batches_and_respects_four_calls(self):
  import tempfile,json,os
  now=datetime.now(timezone.utc);events=[{'id':i,'league':'France - Ligue 1','date':(now+timedelta(hours=4)).isoformat()} for i in range(1,31)]
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder);argv=['capture','--history',str(p/'h.csv'),'--status',str(p/'s.json'),'--market-inventory',str(p/'m.csv')]
   with patch.object(sys,'argv',argv),patch.object(capture,'load_env'),patch.dict(os.environ,{'ODDS_API_KEY':'test'}),patch.object(capture,'request_json',side_effect=[events,[],capture.requests.exceptions.ReadTimeout(),[]]) as request,patch('builtins.print'):
    capture.main()
   d=json.loads((p/'s.json').read_text());self.assertEqual(request.call_count,4);self.assertEqual(d['status'],'PARTIAL_CAPTURE_FAILURE');self.assertEqual(d['requests_used'],4);self.assertEqual(sum(bool(x) for x in d['event_last_checked'].values()),20)
 def row(self,now):
  return {'signal_id':'fixture|keeper|3.5|over','created_at':now.isoformat(),'captured_at':now.isoformat(),'kickoff_at':(now+timedelta(hours=3)).isoformat(),'status':'pending','edge':'.1','odds_decimal':'2.2','fair_odds':'2','selection_policy':'near_even_value_v2','goalkeeper':'Keeper','home_team':'A','away_team':'B','side':'over','line':'3.5','lineup_status':'predicted_starter'}
 def test_claim_once_freezes_original_price_and_survives_rerun(self):
  now=datetime.now(timezone.utc);r=self.row(now);state={}
  self.assertEqual(alerts.claim([r],state,'run:1',now),1)
  r['odds_decimal']='1.9'
  self.assertEqual(alerts.claim([r],state,'run:2',now),0)
  self.assertEqual(state['signals'][r['signal_id']]['signal']['odds_decimal'],'2.2')
 def test_no_stale_settled_tail_or_quarantined_alert(self):
  now=datetime.now(timezone.utc)
  for update in [{'status':'won'},{'duplicate_of':'x'},{'odds_decimal':'8'},{'created_at':(now-timedelta(days=1)).isoformat()},{'captured_at':(now-timedelta(days=1)).isoformat()},{'kickoff_at':(now-timedelta(minutes=1)).isoformat()}]:
   self.assertFalse(alerts.eligible({**self.row(now),**update},now),update)
 def test_signal_price_is_immutable_after_recapture(self):
  import tempfile
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'signals.csv';r={**self.row(datetime.now(timezone.utc)),'event_id':'1','candidate_status':'eligible_shadow','strongest_for_fixture':'yes'}
   shadow.append_signals(p,[r],'2026-09-19T10:00:00Z');r['odds_decimal']='1.8';n,rows=shadow.append_signals(p,[r],'2026-09-19T11:00:00Z')
   self.assertEqual(n,0);self.assertEqual(rows[0]['odds_decimal'],'2.2')
if __name__=='__main__':unittest.main()
