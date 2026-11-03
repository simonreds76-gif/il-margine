import unittest
import runpy
from pathlib import Path
globals().update({k:v for k,v in runpy.run_path(str(Path(__file__).resolve().parents[1]/'build-tennis-conditions.py')).items() if k in ('Edition','History','metrics','score','phase')})
class ProfilesTest(unittest.TestCase):
    def test_earlier_edition_excludes_both_players_and_rematches(self):
        e=Edition();m=[{'sw':40,'sp':60},{'sw':35,'sp':60}]
        for i in range(6):e.add('c'+str(i),'d'+str(i),m,[.6,.6],'2022-01-01')
        base=e.label('a','b');e.add('a','b',[{'sw':60,'sp':60}]*2,[.1,.1],'2022-01-02');e.add('c','a',m,[.9,.9],'2022-01-03')
        self.assertEqual(base,e.label('a','b'))
        self.assertEqual(e.label('z','b')[1],7)
    def test_tiebreak_not_service_game(self):
        g={'result':'7-6(4) 6-4'};s={'w_bpw':'1','l_bpw':'0','w_bpfaced':'0','w_bpsaved':'0','l_bpfaced':'3','l_bpsaved':'2'}
        a,b=metrics(g,s);self.assertEqual((a['h'],a['sg'],a['b'],a['rg']),(11,11,1,11));self.assertNotIn('sp',a)
    def test_bad_break_reciprocity_does_not_erase_valid_points(self):
        a,b=metrics({'result':'6-4 6-4'},{'w_svpt':'60','w_w1s':'30','w_w2s':'10','w_ace':'4','w_df':'1','w_bpw':'99'})
        self.assertEqual(a['sw'],40);self.assertNotIn('h',a)
    def test_nonstandard_and_unfinished_scores(self):
        for s in ['6-4 2-0 RET','W/O','4-2 4-3 4-2','6-4 4-6 [10-8]','6-4 4-6']:
            self.assertIsNone(score(s))
        self.assertIsNotNone(score('6-4 7-6(3)'))
        self.assertIsNotNone(score('6-4 3-6 6-2 6-4'))
    def test_no_phase_mixing(self):self.assertEqual(phase('3'),'Q');self.assertEqual(phase('4'),'M');self.assertIsNone(phase('8'))
    def test_profile_excludes_own_edition(self):
        h=History();base=h.prior('a','Hard','event')
        h.add(1,'a','Hard','event',{'sw':50,'sp':50,'rw':50,'rp':50})
        self.assertEqual(base,h.prior('a','Hard','event'))
    def test_missing_zero_distinguished(self):
        a,b=metrics({'result':'6-4 6-4'},{'w_svpt':'50','w_ace':'0'})
        self.assertEqual(a['ace'],0);self.assertNotIn('df',a)
if __name__=='__main__':unittest.main()

