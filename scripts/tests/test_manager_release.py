import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('pack',Path(__file__).parents[1]/'package-manager-release.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)

class ReleaseTests(unittest.TestCase):
    def archive(self):
        return {'fromDate':'2026-09-20','through':'2026-09-20','atlasVersion':'abc','managers':[{'id':'a','name':'A'},{'id':'b','name':'B'}],'coverage':{'privateSource':'must-not-leak'},'fixtures':[{'id':'fixture','date':'2026-09-20','league':'premier-league','season':'2026-2027','home':'Home','away':'Away','hg':2,'ag':1,'odds':[2.5,3.2,3.1],'basis':'closing','homeManager':'a','awayManager':'b'}]}
    def test_roundtrip_preserves_prices_and_manager_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=self.archive();manifest,path=pack.package(data,Path(tmp));raw=(Path(tmp)/path).read_text(encoding='utf-8')
            self.assertEqual(pack.unpack(json.loads(raw))['fixtures'],data['fixtures'])
            self.assertNotIn('privateSource',raw)
            self.assertEqual(manifest['version'],pack.package(data,Path(tmp))[0]['version'])
    def test_bad_fixtures_cannot_publish(self):
        for field,value in [('odds',[2,0,4]),('basis','unknown'),('homeManager','b'),('awayManager','missing'),('hg',None)]:
            data=self.archive();data['fixtures'][0][field]=value
            with self.assertRaises(ValueError):pack.validate(data)
        data=self.archive();data['fixtures']*=2
        with self.assertRaises(ValueError):pack.validate(data)
    def test_stale_latest_date_cannot_publish(self):
        data=self.archive();data['through']='2026-09-27'
        with self.assertRaises(ValueError):pack.validate(data)

if __name__=='__main__':unittest.main()
