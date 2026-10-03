import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verified_player_targets as M


def sample():
    teams = [dict(id=10, name='Home'), dict(id=20, name='Away')]
    lineup = {'matchId': 100, 'source': 'explicit provider lineup'}
    stats = {}
    for n, side in enumerate(('homeTeam', 'awayTeam')):
        people = [dict(id=n*100+i) for i in range(1, 12)]
        lineup[side] = {**teams[n], 'starters': people, 'subs': [dict(id=n*100+12)]}
        for p in people:
            pid = p['id']
            values = {'minutes_played': 90}
            if pid == 1: values.update(saves=1, goals_conceded=0)
            if pid == 101: values.update(saves=0, goals_conceded=0)
            stats[str(pid)] = dict(id=pid, teamId=teams[n]['id'], name=str(pid), isGoalkeeper=pid in (1,101),
                stats=[{'stats': {k: {'key':k, 'stat':{'value':v}} for k,v in values.items()}}])
    return {'props': {'pageProps': {
        'general': {'matchId':100, 'finished':True, 'homeTeam':teams[0], 'awayTeam':teams[1]},
        'header': {'teams':[{**t, 'score':0} for t in teams]},
        'content': {'lineup':lineup, 'playerStats':stats,
            'stats': {'Periods': {'All': {'stats': [{'stats': [
                {'key':'total_shots', 'stats':[0,1]}, {'key':'ShotsOnTarget', 'stats':[0,1]}]}]}}},
            'shotmap': {'shots':[dict(id=4, teamId=20, playerId=102, keeperId=1,
                eventType='AttemptSaved', isBlocked=False, isSavedOffLine=False, isOnTarget=True)]}}}}}


class VerifiedTargetsTests(unittest.TestCase):
    def test_explicit_roles_and_unused_bench(self):
        rows = M.extract(sample(),'source')
        self.assertEqual(len(rows),22)
        self.assertTrue(all(r['started'] for r in rows))
        self.assertTrue(all(r['minutes']==90 for r in rows))
        self.assertEqual([r['saves'] for r in rows if r['is_goalkeeper']], [1,0])
    def test_partial_map_cannot_invent_zero(self):
        p=sample();p['props']['pageProps']['content']['shotmap']['shots']=[]
        rows=M.extract(p,'x')
        self.assertTrue(all(r['verified_event_sot'] is None and r['event_saves'] is None for r in rows))
    def test_missing_sot_count_cannot_invent_zero(self):
        p=sample();p['props']['pageProps']['content']['stats']['Periods']['All']['stats'][0]['stats'].pop()
        self.assertTrue(all(r['verified_event_sot'] is None for r in M.extract(p,'x')))
    def test_duplicate_events_rejected_for_derived_targets(self):
        p=sample();s=p['props']['pageProps']['content']['shotmap']['shots'];s.append(copy.deepcopy(s[0]))
        self.assertTrue(all(r['event_saves'] is None for r in M.extract(p,'x')))
    def test_blocked_is_on_target_does_not_count(self):
        p=sample();c=p['props']['pageProps']['content'];c['shotmap']['shots'][0]['isBlocked']=True
        c['stats']['Periods']['All']['stats'][0]['stats'][1]['stats']=[0,0]
        rows=M.extract(p,'x')
        self.assertTrue(all(r['verified_event_sot']==0 for r in rows))
        self.assertTrue(next(r for r in rows if r['player_id']==1)['target_conflict'])
    def test_fractional_team_total_not_truncated(self):
        p=sample();p['props']['pageProps']['content']['stats']['Periods']['All']['stats'][0]['stats'][0]['stats']=[0,1.8]
        self.assertTrue(all(r['verified_event_sot'] is None for r in M.extract(p,'x')))
    def test_bad_identity_or_unfinished_rejected(self):
        p=sample();p['props']['pageProps']['general']['finished']=False
        with self.assertRaisesRegex(ValueError,'unfinished'):M.extract(p,'x')
        p=sample();p['props']['pageProps']['content']['lineup']['awayTeam']['id']=99
        with self.assertRaisesRegex(ValueError,'team ID'):M.extract(p,'x')
    def test_no_requests_and_idempotent_append(self):
        with tempfile.TemporaryDirectory() as d:
            p=sample();a=M.archive_observed_targets(p,d,100)
            p['unrelated']='page presentation changed'
            b=M.archive_observed_targets(p,d,100)
            self.assertEqual((a['status'],b['status']),('saved','unchanged'))
            self.assertEqual(len(list(Path(d).rglob('*.json'))),1)
    def test_corrected_source_keeps_previous_version(self):
        with tempfile.TemporaryDirectory() as d:
            p=sample();M.archive_observed_targets(p,d,100)
            p['props']['pageProps']['content']['playerStats']['2']['stats'][0]['stats']['minutes_played']['stat']['value']=80
            M.archive_observed_targets(p,d,100)
            self.assertEqual(len(list(Path(d).rglob('*.json'))),2)
    def test_conflicting_target_not_archived(self):
        with tempfile.TemporaryDirectory() as d:
            p=sample();p['props']['pageProps']['content']['playerStats']['1']['stats'][0]['stats']['saves']['stat']['value']=2
            with self.assertRaisesRegex(ValueError,'disagree'):M.archive_observed_targets(p,d,100)
            self.assertFalse(list(Path(d).rglob('*.json')))
    def test_existing_corrupt_archive_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            M.archive_observed_targets(sample(),d,100)
            next(Path(d).rglob('*.json')).write_text('{}')
            with self.assertRaisesRegex(ValueError,'integrity'):M.archive_observed_targets(sample(),d,100)
    def test_requested_match_id_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'identity'):M.archive_observed_targets(sample(),d,101)


if __name__=='__main__':unittest.main()
