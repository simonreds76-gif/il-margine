import copy,csv,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_breakpoint_evidence as bp
import tennis_elo_rebuild as elo

def packet():
    event={'id':1,'sport':'TENNIS','state':'NOT_STARTED','start':'2026-10-28T14:00:00Z',
           'path':[{'termKey':'atp'}],'homeName':'First Player','awayName':'Second Player','group':'Basel'}
    offer={'id':2,'eventId':1,'criterion':{'id':bp.CRITERION,'englishLabel':'Total Break Points'},
           'betOfferType':{'id':6},'tags':['OFFERED_PREMATCH'],'outcomes':[
               {'type':side,'betOfferId':2,'line':9500,'odds':price,'status':'OPEN','changedDate':'2026-10-28T10:00:00Z'}
               for side,price in [('OT_OVER',1900),('OT_UNDER',1900)]]}
    return {'captured_at':'2026-10-28T12:00:00Z','events':[{'requested_id':1,'captured_at':'2026-10-28T12:00:00Z',
             'payload':{'events':[event],'betOffers':[offer]}}]}

def counts():
    return dict(w_bpof='4',w_bpw='2',w_bpfaced='3',w_bpsaved='3',l_bpof='3',l_bpw='0',l_bpfaced='4',l_bpsaved='2')

def csvfile(p,fields,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)

class PriceTests(unittest.TestCase):
    def test_exact_contract_and_units(self):
        rows,bad=bp.parse(packet(),Path('raw'), 'a');self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['line'],rows[0]['over']),(9.5,1.9));self.assertFalse(rows[0]['predictions_present'])
    def test_wrong_set_or_breaks_market_rejected(self):
        p=packet();p['events'][0]['payload']['betOffers'][0]['criterion']['id']+=1
        self.assertFalse(bp.parse(p,Path('raw'),'a')[0])
    def test_inplay_doubles_and_future_prices_rejected(self):
        for path,value in [('state','STARTED'),('homeName','First / Partner'),('start','2026-10-28T11:00:00Z')]:
            p=packet();p['events'][0]['payload']['events'][0][path]=value
            self.assertFalse(bp.parse(p,Path('raw'),'a')[0])
        p=packet();p['events'][0]['payload']['betOffers'][0]['outcomes'][0]['changedDate']='2026-10-28T13:00:00Z'
        self.assertFalse(bp.parse(p,Path('raw'),'a')[0])
    def test_unpaired_line_and_decimal_wire_value_rejected(self):
        for field,value in [('line',10500),('odds',1.9),('status','CLOSED')]:
            p=packet();p['events'][0]['payload']['betOffers'][0]['outcomes'][1][field]=value
            self.assertFalse(bp.parse(p,Path('raw'),'a')[0])
    def test_idempotent_import_and_schedule_revision(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            root=Path(d);raw=root/'raw.json';raw.write_text(json.dumps(packet()))
            self.assertEqual(bp.ingest(root,packet(),raw),1);self.assertEqual(bp.ingest(root,packet(),raw),0)
            p=packet();p['events'][0]['payload']['events'][0]['start']='2026-10-28T15:00:00Z'
            self.assertEqual(bp.ingest(root,p,raw),1)
            self.assertEqual(len(bp.rows(root/bp.RELATIVE/'quotes.jsonl')),2)
    def test_lock_conflict_then_release(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            with bp.process_lock(Path(d)):
                with self.assertRaises(OSError):
                    with bp.process_lock(Path(d)):pass
            with bp.process_lock(Path(d)):pass

class ResultsTests(unittest.TestCase):
    def fixture(self,p):
        b=p/'data/oncourt'
        csvfile(b/'players_atp.csv',['id','name'],[{'id':1,'name':'First Player'},{'id':2,'name':'Second Player'}])
        csvfile(b/'tours_atp.csv',['id','name'],[{'id':8,'name':'Basel'}])
        self.g={'winner_id':'1','loser_id':'2','tour_id':'8','round_id':'4','date':'2026-10-28','result':'6-4 6-4'}
        csvfile(b/'games_atp.csv',self.g,[self.g])
        stat={**{k:self.g[k] for k in ('winner_id','loser_id','tour_id','round_id')},**counts()}
        csvfile(b/'stat_atp.csv',stat,[stat]);self.stat=stat
        csvfile(p/'data/tennis-props/player-name-aliases.csv',['tour','alias','player_name'],[])
        raw=p/'raw';raw.write_text(json.dumps(packet()));bp.ingest(p,packet(),raw)
    def test_exact_result_then_conflict_and_correction_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);self.fixture(p);r=bp.settle(p)
            self.assertEqual(r['events_with_completed_results'],1);self.assertIsNone(r['roi'])
            out=p/bp.RELATIVE/'results.jsonl';self.assertEqual(bp.rows(out)[0]['y'],7)
            self.assertEqual(bp.settle(p)['new_result_observations'],0)
            # An unrelated export row cannot create a spurious result revision.
            csvfile(p/'data/oncourt/players_atp.csv',['id','name'],[{'id':1,'name':'First Player'},{'id':2,'name':'Second Player'},{'id':3,'name':'Other Player'}])
            self.assertEqual(bp.settle(p)['new_result_observations'],0)
            csvfile(p/'data/oncourt/games_atp.csv',self.g,[self.g,{**self.g,'result':'6-3 6-4'}])
            self.assertEqual(bp.settle(p)['statuses'],{'AMBIGUOUS_FIXTURE':1});self.assertEqual(len(bp.rows(out)),2)
            csvfile(p/'data/oncourt/games_atp.csv',self.g,[self.g]);bp.settle(p)
            self.assertEqual(len(bp.rows(out)),3)
    def test_retirement_stats_conflict_and_wrong_day_not_settled(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);self.fixture(p)
            for change,expected in [({'result':'6-4 2-1 RET'},'UNFINISHED_CONTRACT_REVIEW'),({'date':'2026-10-29'},'OVERDUE_EXACT_FIXTURE_UNRESOLVED')]:
                csvfile(p/'data/oncourt/games_atp.csv',self.g,[{**self.g,**change}])
                self.assertEqual(bp.settle(p)['statuses'],{expected:1})
            csvfile(p/'data/oncourt/games_atp.csv',self.g,[self.g])
            csvfile(p/'data/oncourt/stat_atp.csv',self.stat,[self.stat,{**self.stat,'w_bpof':'5'}])
            self.assertEqual(bp.settle(p)['statuses'],{'MISSING_OR_CONFLICTING_STATS':1})
    def test_reciprocity_and_score_sanity(self):
        self.assertIsNotNone(bp.valid_counts(counts(),'6-4 6-4'))
        for s in [{**counts(),'w_bpof':''},{**counts(),'w_bpfaced':'nan'},{**counts(),'w_bpof':'5'}]:self.assertIsNone(bp.valid_counts(s,'6-4 6-4'))
        self.assertIsNone(bp.valid_counts(counts(),'6-0 6-0'))
    def test_alias_applies_to_native_and_quote_identity(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);self.fixture(p)
            csvfile(p/'data/oncourt/players_atp.csv',['id','name'],[{'id':1,'name':'First Middle Player'},{'id':2,'name':'Second Player'}])
            csvfile(p/'data/tennis-props/player-name-aliases.csv',['tour','alias','player_name'],[{'tour':'ATP','alias':'First Middle Player','player_name':'First Player'}])
            self.assertEqual(bp.settle(p)['events_with_completed_results'],1)

class NativeSourceTests(unittest.TestCase):
    def test_itf_opt_in_and_no_synthetic_indoor(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);b=p/'data/oncourt';s=p/'data/sackmann'
            csvfile(b/'players_atp.csv',['id','name'],[{'id':1,'name':'First Player'},{'id':2,'name':'Second Player'}])
            csvfile(b/'tours_atp.csv',['id','name','date','court_id','rank'],[{'id':8,'name':'ITF','date':'2026-10-26','court_id':1,'rank':0},{'id':9,'name':'Challenger','date':'2026-10-26','court_id':1,'rank':1}])
            fields=['winner_id','loser_id','tour_id','round_id','date','result']
            csvfile(b/'games_atp.csv',fields,[dict(zip(fields,[1,2,t,4,'2026-10-28','6-4 6-4'])) for t in [8,9]])
            csvfile(b/'courts.csv',['id','name'],[{'id':1,'name':'Clay'}]);csvfile(s/'atp_players.csv',['player_id','name_first','name_last'],[])
            csvfile(p/'data/tennis-props/player-name-aliases.csv',['tour','alias','player_name'],[])
            with patch('tennis_direct_history.crosswalk',return_value=({},{})),patch('tennis_source_contract.court_surfaces',return_value={'1':'Clay'}):
                default,_=elo.source_history(p);explicit,_=elo.source_history(p,include_adult_itf=False)
                adult,_=elo.source_history(p,include_adult_itf=True)
            self.assertEqual(default,explicit);self.assertEqual(len(default),1);self.assertEqual(len(adult),2)
            rows=elo.rating_rows(elo.advance(elo.empty_state(),adult,'2026-10-29'))
            self.assertEqual({r['surface'] for r in rows},{'Clay','Overall'})
    def test_frozen_output_forbidden(self):
        from tennis_elo_native_source import build
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            with self.assertRaises(ValueError):build(Path(d),Path(d)/'data/tennis-elo-rebuild','2026-11-01')
    def test_valid_source_cache_reuse_and_tamper_detection(self):
        import tennis_elo_native_source as native
        from datetime import datetime,timezone
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
            p=Path(d);out=p/native.RELATIVE;f=p/'data/oncourt/players_atp.csv'
            csvfile(f,['id','name'],[{'id':1,'name':'Player One'},{'id':2,'name':'Player Two'}])
            (f.parent/'games_atp.csv').write_text('test fixture')
            h=[{'key':'a','winner':1,'loser':2,'date':'2026-01-01','available_date':'2026-01-01','surface':'Hard','rank':0}]
            audit={'source_hashes':{'data/oncourt/players_atp.csv':elo.sha(f)}}
            cutoff=datetime.now(timezone.utc).date().isoformat()
            with patch.object(native,'source_history',return_value=(h,audit)):
                first=native.build(p,out,cutoff)
            with patch.object(native,'source_history',side_effect=AssertionError('must reuse verified cache')):
                second=native.build(p,out,cutoff)
            self.assertEqual(first['rating_hash'],second['rating_hash'])
            from tennis_elo_health import native_research_source
            self.assertTrue(native_research_source(p,datetime.now(timezone.utc))['integrity_verified'])
            (out/'candidate.json').write_text('{}')
            self.assertEqual(native_research_source(p,datetime.now(timezone.utc))['state'],'INVALID_EVIDENCE')
            with patch.object(native,'source_history',side_effect=ValueError('source retry')):
                with self.assertRaisesRegex(ValueError,'source retry'):native.build(p,out,cutoff)

if __name__=='__main__':unittest.main()
