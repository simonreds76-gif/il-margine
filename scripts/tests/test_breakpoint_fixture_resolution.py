import sys,unittest
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
if (Path(__file__).resolve().parents[1]/'tennis_breakpoint_results.py').is_file():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_breakpoint_results as b

class FixtureResolution(unittest.TestCase):
    def setUp(self):
        self.q=dict(event_id='14',group_id='9',tour='WTA',group='Chennai',home='A',away='B',event_state='NOT_STARTED',capture_at='2026-11-02T06:00:00Z',scheduled_start='2026-11-02T09:00:00Z')
        self.updated=dict(self.q,capture_at='2026-11-03T06:00:00Z',scheduled_start='2026-11-03T09:00:00Z')
        self.pair={'1','2'}
        self.g=dict(winner_id='1',loser_id='2',tour_id='11',round_id='4',date='2026-11-03',result='6-4 7-5')
        self.editions={'11':{'name':'Chennai Open - Chennai'}}
        self.now=datetime(2026,11,10,tzinfo=timezone.utc)
        self.proof=dict(tour='WTA',group='Chennai',group_id='9',original_ids=['2','1'],scheduled_day='2026-11-02',day='2026-11-03',kind='played',native_fixture='1:2:11:4')
    def matches(self,quotes,games,proof=None):
        return b.corroborated_games(self.q,self.pair,games,self.editions,b.event_schedules(quotes),proof,self.now)[0]
    def test_earlier_qualifying_rematch(self):
        old=dict(self.g,date='2026-11-01',round_id='3')
        self.assertEqual(self.matches([self.q,self.updated],[old,self.g]),[self.g])
    def test_date_proximity_alone_has_no_grade(self):
        self.assertEqual(self.matches([self.q],[self.g]),[])
    def test_identity_change_or_new_book_id(self):
        for changed in [dict(self.updated,event_id='15'),dict(self.updated,away='C'),dict(self.updated,group_id='10'),dict(self.updated,tour='ATP')]:
            self.assertEqual(self.matches([self.q,changed],[self.g]),[])
    def test_live_capture_cannot_establish_pre_match_revision(self):
        for bad in [dict(self.updated,capture_at=self.updated['scheduled_start']),dict(self.updated,event_state='STARTED')]:
            self.assertEqual(self.matches([self.q,bad],[self.g]),[])
    def test_official_identity_and_round(self):
        self.assertIsNone(b.binding(self.q,{'1','3'},self.proof))
        self.assertIsNone(b.binding(dict(self.q,group_id='4'),self.pair,self.proof))
        self.assertEqual(self.matches([self.q],[dict(self.g,round_id='3'),self.g],self.proof),[self.g])
    def test_sponsor_aliases(self):
        self.assertTrue(b.walkover_venue('ATP','Stockholm Open',{'name':'BNP Paribas Nordic Open - Stockholm'}))
        self.assertFalse(b.walkover_venue('ATP','Stockholm Open',{'name':'Stockholm Challenger'}))
        self.assertFalse(b.corroborated_venue('WTA','Chennai',{'name':'Chennaiville'}))
    def test_competing_rounds_remain_ambiguous(self):
        other=dict(self.g,round_id='5')
        self.assertEqual(len(self.matches([self.q,self.updated],[self.g,other])),2)
    def test_replacement_requires_actual_alternate_and_no_original_stats(self):
        alt=dict(self.g,loser_id='3');key=('1','3','11','4');proof=dict(self.proof,kind='replaced',native_fixture=':'.join(key))
        games,extras,stats=(defaultdict(list) for _ in range(3));pair=frozenset(self.pair)
        def check(by_key):return b.verified_replacement(self.q,pair,proof,by_key,games,extras,stats,self.editions,self.now)
        self.assertFalse(check({}))
        self.assertTrue(check({key:[alt]}))
        stats['2','1','11','4']=[{}];self.assertFalse(check({key:[alt]}));stats.clear()
        games[pair]=[self.g];self.assertFalse(check({key:[alt]}))
if __name__=='__main__':unittest.main()

