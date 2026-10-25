import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aerial_data import utc, read, save
from aerial_heights import merge_squad, profile_record, secondary_record, recover, lineup_targets

NOW = utc('2026-10-25T12:00:00Z')


def profile(pid='123', height=185):
    return {'data': {'id': int(pid), 'name': 'Elliot Stroud', 'birthDate': {'utcTime': '2002-06-22T00:00:00Z'},
                     'primaryTeam': {'teamId': 999}, 'playerInformation': [] if height is None else
                     [{'translationKey': 'height_sentencecase', 'value': {'numberValue': height}}]}}


class HeightRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root/'data/aerial'
        self.old = dict(id='123', name='Elliot Stroud', height_cm=185, team_id='1',
                        source_url='https://old.example/player', observed_at='2026-10-01T00:00:00Z',
                        source_sha256='old', source_kind='player_profile', status='reported')

    def test_blank_squad_preserves_height_and_original_provenance_on_transfer(self):
        p = {'id': 123, 'name': 'Elliot Stroud', 'height': None}
        result = merge_squad(self.old, p, '2', 'defenders', 'https://new.example', 'new', NOW)
        for field in ('height_cm','source_url','observed_at','source_sha256'):
            self.assertEqual(result[field], self.old[field])
        self.assertEqual(result['team_id'], '2')
        self.assertEqual(result['club_observed_at'], NOW.isoformat())

    def test_reviewed_height_keeps_measurement_but_updates_membership(self):
        old = {**self.old, 'source_kind': 'reviewed_external'}
        result = merge_squad(old, {'id':123,'name':'Elliot Stroud','height':175}, '2', 'defenders','u','h',NOW)
        self.assertEqual((result['height_cm'],result['team_id'],result['source_url']), (185,'2',old['source_url']))

    def test_held_conflict_not_filled(self):
        old = {**self.old,'height_cm':None,'height_status':'held'}
        result = merge_squad(old, {'id':123,'name':'Elliot Stroud','height':185}, '2','defenders','u','h',NOW)
        self.assertIsNone(result['height_cm'])
        save(self.data/'heights.json.gz', {'123':old})
        fetch = Mock()
        report = recover(self.root, {}, NOW, fetch)
        fetch.assert_not_called()
        self.assertEqual(report['gaps'][0]['status'], 'held')

    def test_profile_mismatch_and_invalid_height_rejected(self):
        for source in (profile('124'), profile(height=0), profile(height=True)):
            with self.assertRaises(ValueError):
                profile_record(source,'123',self.old,'u','h',NOW)
        with self.assertRaises(ValueError):
            profile_record(profile(),'123',{**self.old,'dob':'2001-01-01'},'u','h',NOW)

    def test_profile_team_does_not_overwrite_fixture_membership(self):
        result, value = profile_record(profile(),'123',self.old,'u','h',NOW)
        self.assertEqual(value,185)
        self.assertEqual(result['team_id'],'1')
        self.assertEqual(result['profile_team_id'],'999')

    def test_daily_budget_and_restart_cooldown(self):
        save(self.data/'heights.json.gz', {str(i):dict(id=str(i),name='Elliot Stroud',height_cm=None) for i in range(1,5)})
        fetch = Mock(side_effect=lambda url:(profile(url.rsplit('/',1)[1],None),'digest'))
        a = recover(self.root,{},NOW,fetch,max_per_run=2,max_per_day=6)
        b = recover(self.root,{},NOW,fetch,max_per_run=2,max_per_day=6)
        c = recover(self.root,{},NOW,fetch,max_per_run=2,max_per_day=6)
        self.assertEqual([len(r['attempted']) for r in (a,b,c)],[2,1,0])
        self.assertEqual(fetch.call_count,3) # other half reserved for new XIs

    def test_blocked_source_stops_and_persists_cooldown(self):
        save(self.data/'heights.json.gz', {'1':{'name':'A'},'2':{'name':'B'}})
        response = requests.Response(); response.status_code=429
        fetch = Mock(side_effect=requests.HTTPError('rate limited',response=response))
        recover(self.root,{},NOW,fetch)
        recover(self.root,{},NOW,fetch)
        self.assertEqual(fetch.call_count,1)

    def test_secondary_exact_identity_gates(self):
        url='https://sport.sky.it/calcio/atleti/elliot-stroud/608227'
        person=dict(**{'@type':'Person'},name='Elliot Stroud',birthDate='2002-06-22',height='185 cm')
        def html(p, canon=url):
            return f'<link rel="canonical" href="{canon}"/><script type="application/ld+json">{json.dumps([p])}</script>'
        old={**self.old,'dob':'2002-06-22','height_cm':None}
        entry,value,_=secondary_record(html(person),old,url,'hash',NOW)
        self.assertEqual(value,185)
        self.assertEqual(entry['source_kind'],'mapped_secondary_profile')
        for bad in ({**person,'birthDate':'2002-06-23'},{**person,'name':'Different Player'}, {**person,'height':'300 cm'}):
            with self.assertRaises(ValueError):secondary_record(html(bad),old,url,'hash',NOW)
        with self.assertRaises(ValueError):secondary_record(html(person,url+'9'),old,url,'hash',NOW)

    def test_secondary_fallback_runs_after_blank_primary_without_waiting_a_week(self):
        old={**self.old,'height_cm':None}
        save(self.data/'heights.json.gz',{'123':old})
        save(self.data/'identity-registry.json.gz',{'schema_version':1,'release':'test','entities':{
            'fotmob|person|123':{'status':'linked','reep_id':'x','targets':{'opta|person_numeric|':{'status':'linked','id':'608227'}}}}})
        primary=Mock(return_value=(profile(height=None),'primary'))
        secondary=Mock(return_value=('<link rel="canonical" href="https://sport.sky.it/calcio/atleti/elliot-stroud/608227"/>'
            '<script type="application/ld+json">[{"@type":"Person","name":"Elliot Stroud","birthDate":"2002-06-22","height":"185 cm"}]</script>','secondary'))
        report=recover(self.root,{},NOW,primary,secondary_fetch=secondary)
        self.assertEqual(report['recovered'],['123'])
        recover(self.root,{},NOW,primary,secondary_fetch=secondary)
        self.assertEqual(primary.call_count,1)
        self.assertEqual(secondary.call_count,1)

    def test_new_starter_prioritised_and_stale_lineups_rejected(self):
        row=dict(id='7',date='2026-10-25T13:00:00Z',league='League',season='2026/2027',home='A',away='B',
                 home_id='10',away_id='20',match_url='https://www.fotmob.com/matches/a#7',disposition='not_completed')
        line=dict(fotmob_match_id=7,kickoff_utc=row['date'],lineup_type='standard',observed_at=NOW.isoformat())
        for side,base in [('home',10),('away',20)]:
            line[side+'_fotmob_team_id']=str(base)
            line[side+'_starters']=[dict(player_id=str(base*100+i),name='Elliot Stroud',line_index=-1 if i==0 else 0,line_size=1 if i==0 else 4) for i in range(11)]
        file=self.root/'data/goalscorer/epl-confirmed-lineups.json'
        save(file,{'fixtures':[line]})
        save(self.data/'heights.json.gz',{'1':{'id':'1','name':'Other','height_cm':None}})
        fetch=Mock(side_effect=lambda url:(profile(url.rsplit('/',1)[1]),'h'))
        report=recover(self.root,{'fixtures':[row]},NOW,fetch,max_per_run=1)
        self.assertEqual(report['attempted'],['1001'])
        self.assertEqual(read(self.data/'heights.json.gz')['1001']['lineup_membership']['team_id'],'10')
        line['observed_at']='2026-10-25T08:00:00Z';save(file,{'fixtures':[line]})
        self.assertEqual(lineup_targets(self.root,{'fixtures':[row]}, {},NOW)[0],{})
        line['observed_at']=NOW.isoformat();line['home_fotmob_team_id']='999';save(file,{'fixtures':[line]})
        targets,errors=lineup_targets(self.root,{'fixtures':[row]}, {},NOW)
        self.assertEqual(targets,{})
        self.assertEqual(len(errors),1)

    def test_large_cross_source_disagreement_is_held_not_auto_selected(self):
        save(self.data/'heights.json.gz',{'123':{**self.old,'height_cm':None}})
        save(self.data/'identity-registry.json.gz',{'schema_version':1,'release':'test','entities':{
            'fotmob|person|123':{'status':'linked','reep_id':'x','targets':{'opta|person_numeric|':{'status':'linked','id':'608227'}}}}})
        secondary=Mock(return_value=('<link rel="canonical" href="https://sport.sky.it/calcio/atleti/elliot-stroud/608227"/>'
            '<script type="application/ld+json">[{"@type":"Person","name":"Elliot Stroud","birthDate":"2002-06-22","height":"194 cm"}]</script>','h'))
        report=recover(self.root,{},NOW,Mock(return_value=(profile(height=177),'h')),secondary_fetch=secondary)
        self.assertEqual(report['recovered'],[])
        row=read(self.data/'heights.json.gz')['123']
        self.assertEqual(row['status'],'held')
        self.assertIsNone(row['height_cm'])
        self.assertEqual(row['height_conflict']['primary_cm'],177)


if __name__ == '__main__':
    unittest.main()
