import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('bundle',Path('scripts/admin_monitor_bundle.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class BundleTests(unittest.TestCase):
 def test_bounds_missing_and_approval(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'config').mkdir();(root/'data').mkdir();(root/'data/good.json').write_text('{"roi":-2,"pending":3}');(root/'data/bad.json').write_text('{');full=root/'data/tennis-props/shadow/full-refresh-v1';full.mkdir(parents=True);(full/'report.json').write_text('{}');(full/'upload-approval-pending.json').write_text('{}')
   views=[{'id':str(i),'file':f} for i,f in enumerate(['data/good.json','data/bad.json','data/missing.csv','../outside.txt','data/tennis-props/shadow/full-refresh-v1/report.json'])];(root/'config/admin-monitor-catalog.json').write_text(json.dumps(views));result=module.build_admin_bundle(root)
   self.assertEqual(list(result['admin_files']),['0']);self.assertEqual([x['available'] for x in result['admin_manifest']],[True,False,False,False,False]);self.assertEqual(json.loads(result['admin_files']['0'])['roi'],-2);self.assertEqual(len(result['admin_manifest'][0]['sha256']),64)
if __name__=='__main__':unittest.main()
