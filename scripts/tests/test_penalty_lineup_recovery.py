import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
r = load('goalscorer-live-penalty-review')
a = load('club-penalty-review-alert')
from penalty_alert_reviews import ticket_id

class RecoveryTests(unittest.TestCase):
    def team(self, name='First Player', pid=1):
        return {'starters': [{'id':pid,'name':name}] + [{'id':i,'name':f'Other {i}'} for i in range(2,12)], 'subs':[], 'unavailable':[]}

    def timeline(self, team, events=None, standard=True):
        return r._attach_match_timeline(team, {'lineup':{'lineupType':'standard' if standard else 'predicted'},
            'matchFacts':{'events':{'ongoing':False,'events':events or []}}}, True, True)

    def test_confirmed_absence_is_not_missing_timeline(self):
        team=self.timeline(self.team())
        present,proof=r._on_pitch_at(team,'Absent Playername',40)
        self.assertFalse(present);self.assertEqual(proof['reason'],'absent_from_matchday_squad')
        self.assertEqual(len(proof['squad_player_ids']),11)
        self.assertIsNone(r._on_pitch_at(self.timeline(self.team(),standard=False),'Absent Playername',40)[0])
        self.assertIsNone(r._on_pitch_at(team,'Different Player',40)[0])
        self.assertIsNone(r._on_pitch_at(team,'',40)[0])

    def test_alias_is_bound_to_exact_provider_id(self):
        for name,pid,alias in [('Raúl García',1094778,'Raúl García de Haro'),('Jaden Philogene-Bidace',1089645,'Jaden Philogene')]:
            self.assertTrue(r._on_pitch_at(self.timeline(self.team(name,pid)),alias,30)[0])
            self.assertIsNone(r._on_pitch_at(self.timeline(self.team(name,999)),alias,30)[0])

    def test_added_time_is_preserved_and_exact_ties_remain_unknown(self):
        team=self.team();team['subs']=[{'id':12,'name':'Backup Player'}]
        team=self.timeline(team,[{'type':'Substitution','isHome':True,'time':90,'overloadTime':1,'swap':[{'id':12},{'id':1}]}])
        self.assertTrue(r._on_pitch_at(team,'First Player',90,0)[0])
        self.assertFalse(r._on_pitch_at(team,'Backup Player',90,0)[0])
        self.assertIsNone(r._on_pitch_at(team,'First Player',90,1)[0])
        self.assertFalse(r._on_pitch_at(team,'First Player',90,2)[0])
        self.assertTrue(r._on_pitch_at(team,'Backup Player',90,2)[0])

    def test_empty_hierarchy_slot_is_not_missing_player(self):
        row={k+'_on_pitch_at_penalty':'Not assigned - hierarchy slot empty' for k in ('primary','secondary','tertiary')}
        row['actual_taker_on_pitch_at_penalty']='Yes - started'
        self.assertTrue(a.has_reliable_pitch_context(row))
        row['primary_pre_match']='Someone Named'
        self.assertFalse(a.has_reliable_pitch_context(row))

    def test_closed_and_delivered_tickets_survive_context_repair(self):
        row={'date':'2026-10-17','league':'epl','team':'Ipswich Town','opponent':'Manchester City','actual_taker':'Zian Flemming','review_priority':'high'}
        identity=ticket_id(row)
        for k in ('primary','secondary','tertiary','actual_taker'):
            row[k+'_on_pitch_at_penalty']='No - bench' if k!='actual_taker' else 'Yes - started'
        self.assertEqual(ticket_id(row),identity)
        self.assertEqual(a.new_actionable_rows([row],[],reviews={'tickets':{identity:{'status':'done'}}}),[])
        self.assertEqual(a.new_actionable_rows([row],[],alerted_identities={a.row_identity(row)}),[])
        self.assertEqual(len(a.new_actionable_rows([row],[])),1)

    def test_admin_order_applies_only_when_known_before_match(self):
        old={'primary':'Old Player','secondary':'','tertiary':'','_approved_override':{'primary':'New Player','secondary':'','tertiary':'','_generated_at':'2026-10-18T09:05:00Z'}}
        self.assertEqual(r._apply_hierarchy_fallback({},old,'2026-10-17T13:30:00Z')['primary'],'Old Player')
        self.assertEqual(r._apply_hierarchy_fallback({},old,'2026-10-19T13:30:00Z')['primary'],'New Player')
        self.assertEqual(r._apply_hierarchy_fallback({'primary':'Captured Player'},old,'2026-10-19T13:30:00Z')['primary'],'Captured Player')

    def test_wrong_fixture_html_cannot_be_accepted(self):
        with patch.object(r,'_fetch_json',side_effect=[ValueError('unavailable'),{'pageUrl':'/shared#1'}]),patch.object(r,'_fetch_text',return_value='x'),patch.object(r,'_extract_next_payload',return_value={'props':{'pageProps':{'general':{'matchId':2}}}}):
            with self.assertRaisesRegex(ValueError,'another fixture'):r._fetch_match_payload(1)

if __name__=='__main__':unittest.main()
