import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from tennis_direct_history import crosswalk, overlap_candidates, player_gap, load

class DirectHistoryTests(unittest.TestCase):
    def test_identity_needs_unique_birthdate_match(self):
        oc=[dict(id='1',name='Player One',birthdate='1990-01-01'),dict(id='2',name='Player One',birthdate='1991-01-01')]
        arc=[dict(player_id='100',name_first='Player',name_last='One',dob='19900101')]
        mapping,audit=crosswalk(oc,arc,[])
        self.assertEqual(mapping,{'1':'100'})
        self.assertEqual(len(audit),1)

    def test_ambiguous_identity_is_not_guessed(self):
        oc=[dict(id='1',name='Player One',birthdate='1990-01-01')]
        arc=[dict(player_id=x,name_first='Player',name_last='One',dob='19900101') for x in ['100','101']]
        self.assertEqual(crosswalk(oc,arc,[])[0],{})

    def test_explicit_alias_keeps_dob_requirement(self):
        oc=[dict(id='1',name='Taylor Harry Fritz',birthdate='1997-10-28')]
        arc=[dict(player_id='100',name_first='Taylor',name_last='Fritz',dob='19971028')]
        alias=[dict(tour='ATP',alias='Taylor Harry Fritz',player_name='Taylor Fritz')]
        self.assertEqual(crosswalk(oc,arc,alias)[0],{'1':'100'})

    def test_overlap_uses_pair_score_and_edition_date_window(self):
        row=dict(winner_id='1',loser_id='2',score='6-3 6-2',_date='2026-06-08')
        old=dict(row,_date='2026-06-01')
        index={('1','2','6-3 6-2'):[old,dict(old,_date='2025-06-01')]}
        self.assertEqual(overlap_candidates(row,index),[old])
        self.assertEqual(overlap_candidates(dict(row,score='6-4 6-2'),index),[])

    def test_inactivity_is_not_a_missing_input(self):
        self.assertFalse(player_gap('1','2026-05-01',{'latest_completed_by_player':{'1':'2026-05-01'}}))
        self.assertTrue(player_gap('1','2026-05-01',{'latest_completed_by_player':{'1':'2026-10-28'}}))

    def test_future_rows_excluded_and_qualifier_factor_preserved(self):
        import csv
        from datetime import date
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def write(rel, rows):
                path=root/rel;path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            write('data/oncourt/players_atp.csv',[dict(id=str(i),name=f'Player {i}',birthdate='1990-01-01') for i in (1,2)])
            write('data/sackmann/atp_players.csv',[dict(player_id=str(100+i),name_first='Player',name_last=str(i),dob='19900101') for i in (1,2)])
            write('data/tennis-props/player-name-aliases.csv',[dict(tour='WTA',player_name='Unused',alias='Unused')])
            write('data/oncourt/courts.csv',[dict(id='3',name='I.hard')])
            write('data/oncourt/tours_atp.csv',[dict(id='10',name='Example Open - Example',rank='2',court_id='3')])
            games=[dict(winner_id='1',loser_id='2',tour_id='10',round_id=str(i),result='6-2 6-3',date=d) for i,d in [(1,'2026-06-02'),(2,'2026-06-03'),(3,'2026-06-04')]]
            write('data/oncourt/games_atp.csv',games)
            stats=[{k:g[k] for k in ('winner_id','loser_id','tour_id','round_id')}|{f'{p}_{k}':v for p in ['w','l'] for k,v in [('ace','3'),('df','1'),('svpt','50')]} for g in games]
            write('data/oncourt/stat_atp.csv',stats)
            legacy=[dict(_tour='ATP',_date='2026-06-01',winner_id='101',loser_id='102',score='6-4 6-4',tourney_id='old')]
            fake=SimpleNamespace(adapt=lambda g,s:({'score':g['result']},None),score=lambda s:[(6,2),(6,3)],BOARD={'scheduled_tournament_name':lambda n:'Example'})
            with patch.dict(sys.modules,{'tennis_props_full_refresh':fake}):
                rows,report=load(root,legacy,date(2026,6,3),{'Hard':.8},require_fresh=False)
            # The near-date conflicting legacy score is quarantined, never double counted.
            self.assertEqual(report['exclusions']['overlap_score_conflict'],1)
            self.assertEqual(rows,legacy)
            self.assertNotIn('2026-06-03',report['latest_completed_by_player'].values())
            other=[dict(legacy[0],loser_id='103')]
            with patch.dict(sys.modules,{'tennis_props_full_refresh':fake}):
                rows,report=load(root,other,date(2026,6,3),{'Hard':.8},require_fresh=False)
            added=[r for r in rows if r.get('_oncourt_fixture')]
            self.assertEqual(len(added),1)
            self.assertEqual(added[0]['_date'],'2026-06-02')
            self.assertEqual(added[0]['_ace_factor'],'0.8')
            self.assertEqual(added[0]['_target'],'no')
            self.assertEqual(added[0]['_surface'],'Hard')

    def test_direct_failure_does_not_suppress_count_registration(self):
        script=Path(__file__).resolve().parents[1]/'run-tennis-props-daily.py'
        spec=importlib.util.spec_from_file_location('direct_isolation_test',script)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        calls=[]
        with tempfile.TemporaryDirectory() as directory:
            props=Path(directory);(props/'shadow').mkdir()
            def run(cmd,*args,**kwargs):
                name=Path(cmd[1]).name;calls.append(name)
                files={'tennis-props-v3-live.py':'aces-v3-projection-board.csv','build-tennis-most-aces-board.py':'most-aces-1x2-board.csv'}
                if name in files:
                    import os, time
                    target=props/'shadow'/files[name];target.write_text('fresh')
                    os.utime(target,(time.time()+1,time.time()+1))
                return 2 if name=='tennis-most-aces-direct-live.py' else 0
            with patch.object(m,'PROPS_DIR',props),patch.object(m,'run',side_effect=run),patch.object(m,'most_aces_suspended',return_value=False):
                m.refresh_current_most_aces('2026-10-29')
            self.assertEqual(calls[-1],'tennis_most_aces_current.py')
            self.assertEqual((props/'shadow/most-aces-direct-1x2-board.csv').read_text(),'')

if __name__=='__main__':unittest.main()
