import json, subprocess, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from atlas_production_release import production_commit, football_paths, preserve_history, stage_football

class MetadataTests(unittest.TestCase):
 def test_all_supported_exact_sources(self):
  for d in ({'meta':{'gitCommitSha':'a'*40}}, {'meta':{'githubCommitSha':'a'*40}}, {'gitSource':{'sha':'a'*40}}, {'meta':{'gitCommitSha':'a'*40,'githubCommitSha':'a'*40},'gitSource':{'sha':'a'*40}}):
   self.assertEqual(production_commit(d),'a'*40)
 def test_missing_invalid_conflicting_all_fail_closed(self):
  for d in ({},{'meta':{'gitCommitSha':'main'}},{'meta':{'gitCommitSha':'b'*40,'githubCommitSha':'a'*40}},{'meta':{'gitCommitSha':'a'*40},'gitSource':{'sha':'b'*40}}):
   with self.assertRaises(RuntimeError):production_commit(d)

def write(root,path,data):
 p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data),encoding='utf-8')

def fixture(root,version,rows):
 for route,key in [('football-atlas','fixtures'),('manager-atlas','rows')]:
  write(root,f'src/data/{route}-release.json',{'version':version,'indexUrl':f'/{route}/index-{version}.json'})
  write(root,f'public/{route}/index-{version}.json',{key:rows,'teams':['A','B']})
 write(root,'src/data/atlas-fixtures.json',{'version':version,'evidenceUrl':f'/football-atlas/fixtures/evidence-{version}.json'})
 write(root,f'public/football-atlas/fixtures/evidence-{version}.json',{'fixtures':[]})
 write(root,'src/data/covered-leagues-release.json',{'baseBoardVersion':version,'historyUrl':f'/football-atlas/covered/history-{version}.json','boardUrl':f'/football-atlas/covered/board-{version}.json'})
 write(root,f'public/football-atlas/covered/history-{version}.json',{'matches':[]})
 write(root,f'public/football-atlas/covered/board-{version}.json',{'evidenceUrl':f'/football-atlas/covered/evidence-{version}.json'})
 write(root,f'public/football-atlas/covered/evidence-{version}.json',{})

class HistoryTests(unittest.TestCase):
 def test_hold_metadata_is_staged_but_private_hold_ledger_is_not(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fixture(root,'same',[[1,2]])
   manifest=root/'src/data/football-atlas-release.json'
   value=json.loads(manifest.read_text());value['historyHolds']={'held':1,'matches':[{'league':'serie-a','date':'2026-11-01','home':'A','away':'B','state':'held'}]}
   manifest.write_text(json.dumps(value))
   write(root,'state/club-history-holds.json',{'holds':[{'code':'private'}]})
   paths=football_paths(root)
   self.assertIn(Path('src/data/football-atlas-release.json'),paths)
   self.assertNotIn(Path('state/club-history-holds.json'),paths)
   self.assertEqual(json.loads(manifest.read_text())['historyHolds']['held'],1)
 def test_regression_or_reordered_identities_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   a=Path(td)/'a'; b=Path(td)/'b';fixture(a,'old',[[1,2]]);fixture(b,'new',[[1,2],[3,4]])
   preserve_history(a,b)
   fixture(b,'new',[[1,9]])
   with self.assertRaises(RuntimeError):preserve_history(a,b)
   fixture(b,'new',[[1,2]])
   write(b,'public/football-atlas/index-new.json',{'fixtures':[[1,2]],'teams':['B','A']})
   with self.assertRaises(RuntimeError):preserve_history(a,b)
 def test_invalid_paths_and_mixed_board_are_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);fixture(p,'ok',[]);self.assertEqual(len(football_paths(p)),10)
   write(p,'src/data/covered-leagues-release.json',{'baseBoardVersion':'old'})
   with self.assertRaises(RuntimeError):football_paths(p)
   (p/'src/data/covered-leagues-release.json').unlink()
   write(p,'src/data/football-atlas-release.json',{'indexUrl':'/football-atlas/../../secret.json'})
   with self.assertRaises(RuntimeError):football_paths(p)

class ReleaseIntegration(unittest.TestCase):
 def test_cli_release_retains_newer_ui_tennis_and_retry_commit(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'source';source.mkdir();remote=root/'remote.git'
   def run(args,cwd=None,**kw):
    return subprocess.run(list(map(str,args)),cwd=cwd or source,check=True,capture_output=True,text=True).stdout
   run(['git','init','--bare',remote]);run(['git','init']);run(['git','config','user.name','test']);run(['git','config','user.email','test@example.invalid']);run(['git','remote','add','origin',remote])
   fixture(source,'old',[[1,2]]);write(source,'src/ui.json',{'design':'current'});write(source,'src/tennis.json',{'version':'latest'})
   run(['git','add','.']);run(['git','commit','-m','live']);base=run(['git','rev-parse','HEAD']).strip();run(['git','push','origin','HEAD:live'])
   fixture(source,'new',[[1,2],[3,4]]);write(source,'src/ui.json',{'design':'obsolete'});write(source,'src/tennis.json',{'version':'obsolete'})
   run(['git','add','.']);run(['git','commit','-m','publisher'])
   deployment={'meta':{'gitCommitSha':base}}
   target,branch,prior,sha=stage_football(source,root/'state',deployment,run)
   self.assertEqual(prior,base);self.assertEqual(json.loads((target/'src/ui.json').read_text()),{'design':'current'});self.assertEqual(json.loads((target/'src/tennis.json').read_text()),{'version':'latest'})
   self.assertEqual(stage_football(source,root/'state',deployment,run)[-1],sha)
   self.assertEqual(run(['git','rev-parse',sha+'^'],target).strip(),base)
   self.assertTrue((source/'public/football-atlas/index-old.json').exists())

if __name__=='__main__':unittest.main()
