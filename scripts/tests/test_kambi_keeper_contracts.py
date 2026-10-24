import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
shadow=load('goalkeeper-saves-shadow'); settle=load('goalkeeper-saves-settle'); alerts=load('club-penalty-review-alert')

class KambiContracts(unittest.TestCase):
    def test_maps_only_same_fixture_and_side(self):
        common=dict(event_id='1',match_date='2026-10-25',home_team='Arsenal',away_team='Everton',league='epl',line='3.5',side='over',odds_decimal='2.0',captured_at='2026-10-24T12:00:00Z',kickoff_at='2026-10-25T14:00:00Z')
        offers=[dict(common,bookmaker='Bet365',player='David Raya'),dict(common,bookmaker='Kambi',player='Home goalkeeper',source='odds_api_io:team_goalkeeper_home:bookmaker_ml'),dict(common,bookmaker='Kambi',player='Away goalkeeper',source='odds_api_io:team_goalkeeper_away:bookmaker_ml')]
        fixture=dict(lineup_type='predicted',home_starters=[dict(name='David Raya',role_group='GK')],away_starters=[dict(name='Jordan Pickford',role_group='GK')])
        with patch.object(shadow,'build_features',return_value=(tuple(range(9)),[])),patch.object(shadow,'predict_mean',return_value=4),patch.object(shadow,'price_side',return_value=dict(edge=.1,model_probability=.55,push_probability=0,fair_odds=1.818)):
            rows=shadow.build_candidates(offers,{},dict(alpha=.2),{('2026-10-25','arsenal','everton'):fixture},'2026-10-24T12:00:00Z')
        home=next(r for r in rows if r['contract_scope']=='team_goalkeeper_home')
        away=next(r for r in rows if r['contract_scope']=='team_goalkeeper_away')
        self.assertEqual(home['goalkeeper'],'David Raya');self.assertEqual(home['candidate_status'],'eligible_shadow')
        self.assertEqual(away['candidate_status'],'blocked')
        with tempfile.TemporaryDirectory() as d:
            added,ledger=shadow.append_signals(Path(d)/'signals.csv',rows,'2026-10-24T12:00:00Z')
            # Both contracts are captured above, but equal prices produce one
            # tracked selection, preferring the named-player Bet365 contract.
            self.assertEqual(added,1)
            self.assertEqual({r['bookmaker'] for r in ledger},{'Bet365'})
            self.assertEqual(shadow.append_signals(Path(d)/'signals.csv',rows,'2026-10-24T13:00:00Z')[0],0)

    def test_team_scope_counts_replacement_keeper_not_opponent(self):
        shots=[dict(id=1,teamId=20,eventType='AttemptSaved',keeperId=100),dict(id=2,teamId=20,eventType='AttemptSaved',keeperId=101),dict(id=3,teamId=10,eventType='AttemptSaved',keeperId=200),dict(id=4,teamId=20,eventType='AttemptSaved',keeperId=100,isBlocked=True)]
        payload={'props':{'pageProps':{'header':{'status':{'finished':True},'teams':[{'id':10},{'id':20}]},'content':{'shotmap':{'shots':shots}}}}}
        self.assertEqual(settle.fotmob_team_saves(payload,'home')[0],2)
        self.assertEqual(settle.fotmob_team_saves(payload,'away')[0],1)
        shots[0].pop('keeperId')
        self.assertIsNone(settle.fotmob_team_saves(payload,'home')[0])

    def test_unknown_ticket_retries_when_context_is_repaired(self):
        base=dict(date='2026-10-24',league='la-liga',team='Elche',opponent='Rayo',actual_taker='Fer Nino',review_priority='high')
        bad=dict(base,primary_on_pitch_at_penalty='Unknown - missing explicit player timeline')
        good=dict(base,primary_on_pitch_at_penalty='No - bench',secondary_on_pitch_at_penalty='Yes - started',tertiary_on_pitch_at_penalty='Yes - started',actual_taker_on_pitch_at_penalty='Yes - started')
        self.assertEqual(alerts.new_actionable_rows([bad],[]),[])
        self.assertEqual(len(alerts.new_actionable_rows([good],[bad])),1)
        self.assertEqual(alerts.new_actionable_rows([good],[good]),[])

    def test_mapped_contract_holds_substitution_or_nonstarter(self):
        player=dict(id=100,name='David Raya',positionId=11)
        stats={'stats':[{'stats':{'Minutes played':{'key':'minutes_played','stat':{'value':90}}}}]}
        content={'lineup':{'homeTeam':{'starters':[player]}},'playerStats':{'100':stats},
                 'shotmap':{'shots':[dict(id=1,teamId=20,eventType='AttemptSaved',keeperId=100)]}}
        payload={'props':{'pageProps':{'header':{'status':{'finished':True},'teams':[{'id':10},{'id':20}]},'content':content}}}
        self.assertEqual(settle.fotmob_mapped_keeper_saves(payload,'home','David Raya')[0],1)
        stats['stats'][0]['stats']['Minutes played']['stat']['value']=80
        self.assertIsNone(settle.fotmob_mapped_keeper_saves(payload,'home','David Raya')[0])
        stats['stats'][0]['stats']['Minutes played']['stat']['value']=90
        content['shotmap']['shots'].append(dict(id=2,teamId=20,eventType='AttemptSaved',keeperId=101))
        self.assertIsNone(settle.fotmob_mapped_keeper_saves(payload,'home','David Raya')[0])
        content['shotmap']['shots'].pop()
        content['lineup']['homeTeam']={'starters':[],'subs':[player]}
        self.assertIsNone(settle.fotmob_mapped_keeper_saves(payload,'home','David Raya')[0])

if __name__=='__main__':unittest.main()
