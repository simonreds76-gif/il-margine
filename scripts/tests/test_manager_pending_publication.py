import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
S=Path(__file__).parents[1];s=importlib.util.spec_from_file_location('mgr_pending',S/'manager_atlas_weekly.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def fixture(self,p):
  def write(path,d):
   dest=p/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(d),encoding='utf-8')
  write('config/manager-atlas-activity.json',[]);write('public/manager-atlas/activity.json',[])
  write('src/data/manager-atlas-release.json',{'version':'old','indexUrl':'/manager-atlas/old.json'})
  write('src/data/football-atlas-release.json',{'version':'new_clubs'})
  write('public/manager-atlas/old.json',{})
 def exercise(self,failures,version='new_clubs',pending=True,reason='No unique exact fixture match'):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);self.fixture(p)
   def fail(*a,**kw):
    (p/'state/managers/refresh-report.json').write_text(json.dumps({'failures':failures,'atlasVersion':version,'candidates':1,'added':0,'pending':[{'id':'unknown','reason':reason}] if pending else []}))
    raise subprocess.CalledProcessError(1,'manager')
   with patch.object(m,'ROOT',p),patch.object(m.package,'unpack',return_value={'fixtures':[]}),patch.object(m.package,'package') as publish,patch.object(m.subprocess,'run',side_effect=fail):
    if failures==['Manager verification incomplete: 1 eligible fixtures require review'] and version=='new_clubs' and pending and reason=='No unique exact fixture match':
     r=m.refresh(p/'state');self.assertFalse(r['changed']);self.assertEqual(r['manifest']['version'],'old');self.assertEqual(len(r['pending']),1)
    else:
     with self.assertRaises(subprocess.CalledProcessError):m.refresh(p/'state')
    publish.assert_not_called()
 def test_pending_manager_keeps_previous_archive(self):self.exercise(['Manager verification incomplete: 1 eligible fixtures require review'])
 def test_score_conflict_remains_failure(self):self.exercise(['Manager verification incomplete: 1 eligible fixtures require review'],reason='Match date/teams/score conflict')
 def test_request_failure_remains_failure(self):self.exercise(['Manager verification incomplete: 1 eligible fixtures require review'],reason='Request failed')
 def test_other_failure_remains_failure(self):self.exercise(['source mismatch'])
 def test_stale_report_not_accepted(self):self.exercise(['Manager verification incomplete: 1 eligible fixtures require review'],version='old')
 def test_missing_pending_not_accepted(self):self.exercise(['Manager verification incomplete: 1 eligible fixtures require review'],pending=False)
if __name__=='__main__':unittest.main()
