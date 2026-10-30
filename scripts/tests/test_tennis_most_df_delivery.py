import sys,unittest,tempfile,json,shutil,importlib.util,ast,hashlib,csv
from pathlib import Path
from datetime import datetime,timezone,timedelta
W=Path(__file__).resolve().parents[2];R=W;sys.dont_write_bytecode=True
sys.path[:0]=[str(W/'scripts'),str(R/'scripts')]
import tennis_most_df as m,tennis_most_df_delivery as d
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);o=importlib.util.module_from_spec(spec);sys.modules[name]=o;spec.loader.exec_module(o);return o
digest=load('df_digest',W/'runtime/scripts/tennis-daily-signal-digest.py')
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))
def writecsv(p,rows):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
class Test(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=W);self.root=Path(self.tmp.name);self.f=self.root/m.REL;self.now=datetime.now(timezone.utc)
  for name in ['tennis_most_df.py','tennis_most_df_delivery.py']:
   p=self.root/'scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(W/'scripts'/name,p)
  shutil.copyfile(R/'scripts/tennis_props_model.py',self.root/'scripts/tennis_props_model.py')
  reg={'code_sha256':'original','model_sha256':d.hashed(self.root/'scripts/tennis_props_model.py'),'config':m.CONFIG,'registered_at':self.now.isoformat()}
  dump(self.f/'registration.json',reg);self.reg=reg
  self.activation={'scope':'most-df-paper-delivery-only','pricing_changed':False,'real_stake':0,'paper_stake':1,'effective_at':self.now.isoformat(),'registration_sha256':d.hashed(self.f/'registration.json'),'original_code_sha256':'original','current_code_sha256':d.hashed(self.root/'scripts/tennis_most_df.py'),'delivery_code_sha256':d.hashed(self.root/'scripts/tennis_most_df_delivery.py'),'model_sha256':reg['model_sha256']}
  dump(self.f/'delivery-activation.json',self.activation)
 def tearDown(self):self.tmp.cleanup()
 def test_activation_guards(self):
  self.assertTrue(d.activated(self.root,self.reg,self.now))
  for k,v in [('pricing_changed',True),('real_stake',1),('paper_stake',2),('scope','other'),('registration_sha256','x'),('current_code_sha256','x'),('delivery_code_sha256','x'),('model_sha256','x'),('effective_at',(self.now+timedelta(seconds=1)).isoformat())]:
   dump(self.f/'delivery-activation.json',{**self.activation,k:v});self.assertFalse(d.activated(self.root,self.reg,self.now),k)
 def fixture(self):
  now=self.now;a=dict(date=now.date().isoformat(),tour='ATP',tournament='Vienna',player='One',player_id='11');b={**a,'player':'Two','player_id':'22'}
  self.quote=dict(date=a['date'],tour='ATP',tournament='Vienna',player1='One',player2='Two',player1_odds='2.5',draw_odds='6',player2_odds='2',bookmaker='Bet365',raw_market_name='Most Double Faults',capture_ts=now.isoformat(),match_start_utc=(now+timedelta(hours=10)).isoformat())
  raw={'name':'Most Double Faults','odds':[{'home':2.5,'draw':6,'away':2}]};self.quote['raw_market_json']=json.dumps(raw);self.quote['evidence_sha256']=hashlib.sha256(json.dumps(raw).encode()).hexdigest()
  prices,_=m.current_prices([self.quote],a,b,now);_,s=m.select(prices,[.6,.15,.25])
  row=dict(id='a',fixture='ATP:321:7:11:22',date=a['date'],names=['One','Two'],players=['11','22'],inputs=[b,a],selection=s,probabilities=[.6,.15,.25],start=self.quote['match_start_utc'],captured_at=now.isoformat(),registration_sha256=d.hashed(self.f/'registration.json'))
  dump(self.f/'captures/a.json',row);dump(self.f/'outcomes.json',{});dump(self.f/'report.json',{'generated_at':now.isoformat()})
  self.quotes=self.root/'data/tennis-props/inbox'/f'most-df-1x2-{now.date().isoformat()}.csv';writecsv(self.quotes,[self.quote]);return row
 def test_current_price_and_orientation(self):
  self.fixture();self.assertEqual(len(d.alert_rows(self.root,now=self.now)),1)
  writecsv(self.quotes,[] if False else [{**self.quote,'raw_market_name':'Most Aces'}]);self.assertEqual(d.alert_rows(self.root,now=self.now),[])
 def test_old_started_settled(self):
  self.fixture();self.assertFalse(d.alert_rows(self.root,now=self.now+timedelta(minutes=31)))
  dump(self.f/'outcomes.json',{'a':{'status':'settled'}});self.assertFalse(d.alert_rows(self.root,now=self.now))
 def test_better_book_never_advertises_inferior_frozen_price(self):
  self.fixture();q={**self.quote,'bookmaker':'Grosvenor','player1_odds':'2.7'};raw=json.loads(q['raw_market_json']);raw['odds'][0]['home']=2.7;q['raw_market_json']=json.dumps(raw);q['evidence_sha256']=hashlib.sha256(q['raw_market_json'].encode()).hexdigest()
  writecsv(self.quotes,[self.quote,q]);self.assertFalse(d.alert_rows(self.root,now=self.now))
 def test_dedup_key_ignores_book_price_outcome(self):
  s=digest.Signal('MOST DOUBLE FAULTS 1X2 Â· PAPER ONLY',47,['MOST DF PAPER'],'One vs Two','One @2.5 Bet365',50,key=('2026-10-31','ATP:321:7:11:22','most_df_1x2'))
  state={'signal_ids':[digest.signal_id(s)]};s.selection='Tie @7 Grosvenor';self.assertFalse(digest.new_signals_since_state([s],state,'2026-10-31'))
if __name__=='__main__':unittest.main()
