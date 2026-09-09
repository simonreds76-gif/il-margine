"""Independent absorbing-state reference and symmetry regression tests."""
import importlib.util
import sys
import unittest
from pathlib import Path

here=Path(__file__).resolve()
path=here.parent/'tennis_prob.py' if here.parent.name=='outputs' else here.parents[2]/'src/lib/tennis_prob.py'
spec=importlib.util.spec_from_file_location('tested_tennis_probability',path)
t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)

def forward_reference(p,q,first=True):
    """Propagate point-score mass without the production closed-form tail."""
    states={(0,0):1.};won=0.
    for total in range(5000):
        next_states={};a_serves=(total%4 in (0,3))==first;point=p if a_serves else 1-q
        for (a,b),mass in states.items():
            for aa,bb,weight in [(a+1,b,mass*point),(a,b+1,mass*(1-point))]:
                if aa>=7 and aa-bb>=2:won+=weight
                elif bb>=7 and bb-aa>=2:pass
                else:next_states[(aa,bb)]=next_states.get((aa,bb),0)+weight
        states=next_states
        if sum(states.values())<1e-13:return won
    raise AssertionError('Reference did not converge')

class TiebreakProbability(unittest.TestCase):
    def test_calibration_preserves_neutral_ties_in_live_and_replay(self):
        root=here.parents[1]/'lab-model-release' if here.parent.name=='outputs' else here.parents[2]
        sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
        for filename,fn in [('backtest-fair-odds.py','_calibrate_match_prob'),('oncourt-compute-fair-odds.py','_calibrate_match_probability')]:
            spec=importlib.util.spec_from_file_location('calibration_'+filename.replace('-','_'),root/'scripts'/filename)
            m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);calibrate=getattr(m,fn)
            for series in ['ATP250','Masters 1000','Grand Slam']:
                for p in [.5,.5-1e-16,.5+1e-16]:self.assertEqual(calibrate(p,series,'Hard','high'),.5)
                for p in [.25,.4,.6,.75]:self.assertAlmostEqual(calibrate(p,series,'Hard','high')+calibrate(1-p,series,'Hard','high'),1,places=12)

    def test_matches_independent_forward_enumeration(self):
        for p,q in [(.05,.65),(.5,.5),(.65,.60),(.8,.8),(.95,.8),(.99,.99)]:
            for first in [False,True]:
                with self.subTest(p=p,q=q,first=first):self.assertAlmostEqual(t.prob_tiebreak(p,q,first),forward_reference(p,q,first),places=11)

    def test_identical_players_have_equal_chances(self):
        for p in [.05,.25,.5,.65,.8,.95,.99]:
            for first in [False,True]:self.assertAlmostEqual(t.prob_tiebreak(p,p,first),.5,places=12)
            self.assertAlmostEqual(t.prob_match_best_of_3(p,p),.5,places=12)
            self.assertAlmostEqual(t.prob_match_best_of_5(p,p),.5,places=12)

    def test_swap_complements_tiebreak_set_and_match(self):
        for p in [.05,.25,.5,.65,.8,.95]:
            for q in [.05,.25,.5,.65,.8,.95]:
                self.assertAlmostEqual(t.prob_tiebreak(p,q,True)+t.prob_tiebreak(q,p,False),1,places=12)
                self.assertAlmostEqual(t.prob_set(p,q,True)+t.prob_set(q,p,False),1,places=12)
                for fn in [t.prob_match_best_of_3,t.prob_match_best_of_5]:self.assertAlmostEqual(fn(p,q)+fn(q,p),1,places=12)

    def test_improving_serve_never_reduces_win_probability(self):
        probs=[t.prob_tiebreak(p,.65) for p in [.1,.3,.5,.6,.65,.7,.8,.95]]
        self.assertTrue(all(a<b for a,b in zip(probs,probs[1:])))

    def test_total_game_distributions_remain_normalized_and_symmetric(self):
        for n in [3,5]:
            a=t.match_games_pmf(.8,.72,best_of=n);b=t.match_games_pmf(.72,.8,best_of=n)
            self.assertAlmostEqual(sum(a.values()),1,places=12)
            for k in a:self.assertAlmostEqual(a[k],b[k],places=12)

if __name__=='__main__':unittest.main()
