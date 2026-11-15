import csv
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import tournament_returns_refresh as m


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout, self.candidate = self.root/'checkout', self.root/'candidate'
        m.write(self.checkout/m.EVIDENCE, {'editions': []})
        self.rows = [dict(date='2026-10-01', tour_id='1', round_id='9', winner_id='a', loser_id='b', result='6-4 6-4')]
        self.prices = [dict(id='m1', date='2026-10-01', p1='a', p2='b', winner='a', o1=1.6, o2=2.7,
                            event='Test Open - Test', round='9', score='6-4 6-4', surface='indoor-hard',
                            priceBasis='Pinnacle last recorded pre-match')]

    def source(self):
        c = self.candidate
        def csv_file(name, rows):
            p = c/'oncourt'/name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader(); w.writerows(rows)
        csv_file('games_atp.csv', self.rows)
        csv_file('players_atp.csv', [{'id':'a','name':'One Player'}, {'id':'b','name':'Two Player'}])
        csv_file('tours_atp.csv', [{'id':'1','name':'Test Open - Test','date':'2026-10-01','rank':'2','court_id':'3'}])
        m.write(c/'oncourt/extraction-status.json', {'state':'VERIFIED','completed_at':datetime.now(timezone.utc).isoformat(),
            'exports': {p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (c/'oncourt').glob('*.csv')}})
        p=c/'preview/real-data.mjs'; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(''.join('export const '+k+'='+json.dumps(v)+';\n' for k,v in {
            'metadata':{}, 'players':[{'id':'a','name':'One Player'}, {'id':'b','name':'Two Player'}], 'matches':self.prices}.items()))
        m.write(c/'release/src/data/return-atlas-release.json', {'checkedAt':'2026-11-15', 'through':max(r['date'] for r in self.rows),
            'version':'20261114-aaaaaaaaaaaa','indexUrl':'/return-atlas/data/test/index.json'})
        m.write(c/'release/public/return-atlas/data/test/index.json', {'players':[{'id':'a'},{'id':'b'}],
            'matches':[[r['id'],r['date'],0,1,r['o1'],r['o2'],0 if r['winner']=='a' else 1] for r in self.prices]})

    def refresh(self):
        with redirect_stdout(io.StringIO()): report=m.prepare(self.checkout,self.candidate)
        return report, m.read(self.candidate/'release'/m.DATA)

    def baseline(self):
        self.source(); report,value=self.refresh()
        self.assertEqual(report['status'],'validated')
        m.write(self.checkout/m.DATA,value)
        return value

    def test_new_result_updates_coverage_then_paired_price_updates_roi(self):
        old=self.baseline()
        self.rows.append(dict(date='2026-10-02',tour_id='1',round_id='12',winner_id='b',loser_id='a',result='6-2 6-4'))
        self.source(); report,new=self.refresh(); e=new['families'][0]['editions'][0]
        self.assertEqual((report['completed'],report['paired']),(2,1))
        self.assertEqual(e['noPrice'],1);self.assertEqual(e['coveragePct'],50)
        self.assertEqual(e['favourite'],old['families'][0]['editions'][0]['favourite'])
        self.assertEqual(e['completion']['state'],'completed')
        self.prices.append(dict(self.prices[0],id='m2',date='2026-10-02',round='12',winner='b',score='6-2 6-4'))
        self.source()
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.candidate/'oncourt').glob('*')}
        report,new=self.refresh();e=new['families'][0]['editions'][0]
        self.assertEqual((e['completed'],e['paired'],e['bettable']),(2,2,2))
        self.assertEqual(e['favourite']['roi'],-20);self.assertEqual(e['underdog']['roi'],35)
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        self.assertEqual(m.read(self.checkout/m.DATA),old)

    def test_repeat_check_is_identical_and_does_not_deploy_for_timestamp(self):
        old=self.baseline(); self.source()
        report,new=self.refresh()
        self.assertFalse(report['changed']);self.assertEqual(old,new)

    def test_windows_checkout_line_endings_do_not_create_empty_commit(self):
        old=self.baseline();p=self.checkout/m.DATA
        p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'))
        report,new=self.refresh()
        self.assertFalse(report['changed']);self.assertEqual(new,old)
        self.assertEqual(p.read_bytes(),(self.candidate/'release'/m.DATA).read_bytes())

    def test_result_or_source_hash_failure_retains_only_previous_snapshot(self):
        old=self.baseline()
        with (self.candidate/'oncourt/games_atp.csv').open('a') as f:f.write('corrupt')
        report,new=self.refresh()
        self.assertEqual(report['status'],'retained_previous');self.assertFalse(report['changed']);self.assertEqual(old,new)

    def test_stale_verified_receipt_is_not_fresh(self):
        old=self.baseline();p=self.candidate/'oncourt/extraction-status.json';r=m.read(p)
        r['completed_at']=(datetime.now(timezone.utc)-timedelta(hours=31)).isoformat();m.write(p,r)
        report,new=self.refresh()
        self.assertEqual(report['status'],'retained_previous');self.assertIn('stale',report['error']);self.assertEqual(old,new)

    def test_failed_first_build_cannot_publish_a_leftover_candidate(self):
        self.source();m.write(self.candidate/'release'/m.DATA,{'stale':'bad'})
        report=m.prepare(self.checkout,self.candidate,builder=lambda *a: (_ for _ in ()).throw(ValueError('bad')))
        self.assertEqual(report['status'],'unavailable');self.assertFalse((self.candidate/'release'/m.DATA).exists())

    def test_old_editions_or_outcomes_cannot_disappear(self):
        old=self.baseline()
        for field in ('families','outcome'):
            new=deepcopy(old)
            if field=='families':new['families']=[]
            else:
                e=new['families'][0]['editions'][0]
                e['favourite'].update(wins=0,losses=1,profit=-1,roi=-100)
                e['underdog'].update(wins=1,losses=0,profit=1.7,roi=170)
            with self.assertRaises(ValueError):m.validate(old,new)

    def test_exact_live_version_and_corruption_checks(self):
        old=self.baseline();v=m.expected_version(self.checkout)
        self.assertEqual(m.page_version(f'<main data-tournament-returns-version="{v}">'),v)
        self.assertTrue(m.is_live(self.checkout,'https://example.test',lambda _:f'<main data-tournament-returns-version="{v}">'.encode()))
        self.assertFalse(m.is_live(self.checkout,'https://example.test',lambda _:b'<main>old page'))
        old['through']='2099-01-01';m.write(self.checkout/m.DATA,old)
        with self.assertRaisesRegex(ValueError,'checksum'):m.expected_version(self.checkout)


class PublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('refresh_returns_test',Path(__file__).parents[1]/'refresh-return-atlas.py')
        cls.publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.publisher)

    def test_public_verification_reads_rendered_matchday_not_an_assumed_timestamp(self):
        v='tr-'+'a'*20
        with patch.object(self.publisher,'fetch',return_value=f'<main data-tournament-returns-version="{v}">'.encode()) as fetch:
            self.assertEqual(self.publisher.live_version('tournament-returns',timeout=10),v)
        self.assertEqual(fetch.call_args.args[0],'https://ilmargine.bet/tennis-matchday')

    def test_data_release_allows_snapshot_but_not_generator_or_ui(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for route in ('return-atlas','tennis-matchup'):
                v='20261114-'+'a'*12
                m.write(root/f'src/data/{route}-release.json',{'version':v,'indexUrl':f'/{route}/data/{v}/index.json'})
            value={'schema':1};value['version']=m.version(value);m.write(root/m.DATA,value)
            paths=self.publisher.data_release_paths(root)
            self.assertIn(m.DATA,paths)
            self.assertFalse(any('scripts' in p.parts for p in paths))
            with patch.object(self.publisher,'run',return_value='src/app/tennis-matchday/page.tsx\n'):
                with self.assertRaisesRegex(RuntimeError,'unrelated'):
                    self.publisher.validate_release_diff('old',root,paths)

if __name__=='__main__':unittest.main()
