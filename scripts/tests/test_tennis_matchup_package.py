import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package_matchup', Path(__file__).resolve().parents[1] / 'package-tennis-matchup.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PublicSnapshotTests(unittest.TestCase):
    def sample(self):
        return {'schema':1, 'asOf':'2026-09-26', 'through':'2026-09-25', 'countries':[],
                'players':[{'name':'A'}, {'name':'B'}, {'name':'C'}], 'portraits':{},
                'audit':{'privateSource':'private/table.csv'},
                'matches':[{'id':'m1','date':'2026-09-25','p1':0,'p2':1,'winner':0,'o1':1.8,'o2':2.2,'source':'private source'},
                           {'id':'m2','date':'2026-09-24','p1':1,'p2':2,'winner':1,'o1':1.7,'o2':2.3}]}

    def publish(self, root, data):
        source=Path(root)/'private.json'
        source.write_text(json.dumps(data),encoding='utf-8')
        return module.package(source,Path(root))

    def test_two_player_union_preserves_complete_record_and_h2h_deduplicates(self):
        with tempfile.TemporaryDirectory() as root:
            release=self.publish(root,self.sample())
            target=Path(root)/'public'/release['indexUrl'].lstrip('/')
            index=json.loads(target.read_text())
            self.assertEqual(index['totalMatches'],2)
            shards=[json.loads((target.parent/f'{i}.json').read_text()) for i in range(3)]
            self.assertEqual([len(s['matches']) for s in shards],[1,2,1])
            self.assertEqual(len({r['id'] for s in shards[:2] for r in s['matches']}),2)
            self.assertEqual(shards[0]['matches'][0],shards[1]['matches'][0])
            self.assertNotIn('audit',index)
            self.assertNotIn('source',shards[0]['matches'][0])

    def test_rejects_same_day_or_invalid_odds(self):
        for field,value in [('date','2026-09-26'),('o1',0),('p1',8)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                data=self.sample();data['matches'][0][field]=value
                with self.assertRaises(ValueError):self.publish(root,data)

    def test_version_changes_when_statistics_change(self):
        with tempfile.TemporaryDirectory() as root:
            data=self.sample();one=self.publish(root,data)
            data['matches'][0]['stats1']={'aces':[5,80]}
            two=self.publish(root,data)
            self.assertNotEqual(one['version'],two['version'])

if __name__=='__main__':unittest.main()
