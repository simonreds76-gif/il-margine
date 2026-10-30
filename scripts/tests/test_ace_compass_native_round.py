import sys,unittest,tempfile,json,importlib.util
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from pathlib import Path
W=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
SCRIPTS=W/'scripts' if (W/'scripts').exists() else W.parent
sys.path.insert(0,str(SCRIPTS))
if (W/'scripts').exists():sys.path.append('D:/IlMargine/il-margine/scripts')
s=importlib.util.spec_from_file_location('compass_repair',SCRIPTS/'tennis_ace_compass.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class NativeRoundTests(unittest.TestCase):
    def setUp(self):
        self.b=dict(tour_id='123',player_id='1',opponent_id='2',date='2026-10-30',round='QF')
        self.r=dict(tour_id='123',player1_id='1',player2_id='2',date='2026-10-30',round_id='9',result='',live='',complete='')
    def test_qf_numeric_identity(self):
        self.assertEqual(m.native_round(self.b,[self.r]),('9',None))
        self.assertEqual(m.E.event_phase(m.native_round(self.b,[self.r])[0]),'main_draw')
    def test_reversed_native_order(self):
        self.assertEqual(m.native_round(self.b,[dict(self.r,player1_id='2',player2_id='1')]),('9',None))
    def test_exact_ids_day_edition(self):
        for r in [dict(self.r,date=''),dict(self.r,date='2026-10-29'),dict(self.r,tour_id='124'),dict(self.r,player2_id='3')]:
            self.assertEqual(m.native_round(self.b,[r])[1],'native_fixture_missing')
    def test_conflicting_rounds(self):
        self.assertEqual(m.native_round(self.b,[self.r,dict(self.r,round_id='8')])[1],'native_fixture_ambiguous')
    def test_identical_duplicates_not_ambiguous(self):
        self.assertEqual(m.native_round(self.b,[self.r,self.r]),('9',None))
    def test_no_started_matches(self):
        for field in ('result','live','complete'):
            self.assertEqual(m.native_round(self.b,[self.r,dict(self.r,**{field:'1'})])[1],'native_fixture_started_or_completed')
    def test_no_guess_from_label(self):
        for value in ('QF','', '0','13','9.0'):
            self.assertEqual(m.native_round(self.b,[dict(self.r,round_id=value)])[1],'native_round_invalid')
    def test_native_board_conflict(self):
        self.assertEqual(m.native_round(dict(self.b,round_id='8'),[self.r])[1],'native_round_conflict')
    def test_wimbledon_qualifying_round3(self):
        rid,err=m.native_round(dict(self.b,round='Q3'),[dict(self.r,round_id='3')])
        self.assertIsNone(err);self.assertEqual(m.E.match_best_of('ATP','Wimbledon',rid,slam=True),5)
    def test_settlement_identity_uses_native_round(self):
        rid,_=m.native_round(self.b,[self.r]);self.assertEqual(m.identity(dict(self.b,round=rid)),'123:9:1:2')
    def test_old_lock_file_does_not_permanently_block_and_concurrent_writer_rejected(self):
        with tempfile.TemporaryDirectory(dir=W) as d:
            folder=Path(d);(folder/'.writer.lock').write_text('old process')
            with m.lock(folder):
                with self.assertRaises(OSError):
                    with m.lock(folder):pass
            with m.lock(folder):pass
    def test_amendment_cannot_change_model_or_config(self):
        with tempfile.TemporaryDirectory(dir=W) as d:
            p=Path(d);old={'tennis_ace_compass.py':'old','ace_compass_engine.py':'engine','ace_compass_integrity.py':'integrity'}
            new=dict(old,**{'tennis_ace_compass.py':'new'});reg=dict(config=m.CONFIG,implementation=old)
            with self.assertRaises(ValueError):m.verified_implementation(p,reg,new)
            amend=dict(reason='exact_native_round_identity',before=old,after=new,config_hash=m.digest(m.CONFIG))
            (p/'recorder-amendment-20261030.json').write_text(json.dumps(amend))
            self.assertEqual(m.verified_implementation(p,reg,new)['implementation'],new)
            altered=dict(new,**{'ace_compass_engine.py':'modified'});amend['after']=altered
            (p/'recorder-amendment-20261030.json').write_text(json.dumps(amend))
            with self.assertRaises(ValueError):m.verified_implementation(p,reg,altered)
            with self.assertRaises(ValueError):m.verified_implementation(p,dict(reg,config={}),new)

    def test_quote_captures_then_settles_by_native_key_without_duplicate(self):
        now=datetime.now(timezone.utc);day=now.date().isoformat()
        b=dict(self.b,date=day,generation_date=day,tour='ATP',player='Alpha',opponent='Beta',tournament='Example')
        native=dict(self.r,date=day)
        q=dict(date=day,tour='ATP',market='aces',player='Alpha',opponent='Beta',tournament='Example',line='4.5',over_odds='2.0',bookmaker='Book',capture_ts=now.isoformat(),match_start_utc=(now+timedelta(hours=2)).isoformat(),matched_board='yes',match_source='exact')
        class State:
            def feature(self,*args):return {'event_latest':now.date().toordinal()-2}
        with tempfile.TemporaryDirectory(dir=W) as d:
            root=Path(d);folder=root/'evidence';folder.mkdir();comparison=root/'comparison.csv';comparison.touch()
            today=root/'data/oncourt/today_atp.csv';today.parent.mkdir(parents=True);today.write_text('native fixture')
            tours={'123':dict(name='Example',rank='2',court_id=next(iter(m.E.SURF)))}
            reads=lambda p: [q] if p==comparison else [native] if p==today else [b]
            prediction={k:dict(selected=True,mean=5.,p_win=.55,fair_odds=1/.55,ev=.10) for k in ('control','candidate')}
            with patch.object(m.E,'read',side_effect=reads),patch.object(m,'source_manifest',return_value={}),patch.object(m.E,'history',return_value=([],tours,{})),patch.object(m.E,'build_state',return_value=State()),patch.object(m.E,'predict',return_value=prediction),patch.object(m.pickle,'dump',side_effect=lambda obj,f:f.write(b'test')):
                rows=[];status=m.capture(root,root,folder,rows,comparison,now,{'implementation':{}})
                self.assertEqual(status['added'],1);self.assertEqual(rows[0]['native']['round'],'9');self.assertEqual(rows[0]['native']['round_display'],'QF')
                self.assertEqual(m.capture(root,root,folder,rows,comparison,now,{'implementation':{}})['added'],0)
            g=dict(tour_id='123',round_id='9',winner_id='1',loser_id='2',date=day,result='6-3 6-4')
            stat=dict(g,w_ace='6',l_ace='3')
            with patch.object(m.E,'read',side_effect=lambda p:[g] if p.name=='games_atp.csv' else [stat]),patch.object(m.E,'adapt',return_value=({},None)):
                outcomes={};m.settle(root,rows,outcomes,now+timedelta(hours=3));self.assertEqual(outcomes[rows[0]['id']]['actual'],6)

if __name__=='__main__':unittest.main()
