import importlib.util,json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch,Mock
S=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('refresh_safety',S/'refresh-return-atlas.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class AuthTests(unittest.TestCase):
 def test_environment_token_is_not_put_in_args(self):
  with patch.object(M.subprocess,'run') as call:
   args=M.publication_auth_args(['vercel','api','/test'],{'VERCEL_TOKEN':'test-secret'})
  call.assert_not_called();self.assertNotIn('test-secret',str(args))
 def test_missing_auth_never_launches_vercel(self):
  with patch.object(M.shutil,'which',return_value='node'),patch.object(M.Path,'is_file',return_value=True),patch.dict(M.os.environ,{},clear=True),patch.object(M.subprocess,'run',return_value=Mock(returncode=0,stdout='{"path":"config","configured":false}')) as run:
   with self.assertRaises(M.PublicationAuthRequired):M.run(['vercel.cmd','api','/test'])
  self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[0][0],'node');self.assertNotIn('login',run.call_args.args[0])
 def test_existing_auth_pins_resolved_directory(self):
  with patch.object(M.shutil,'which',return_value='node'),patch.object(M.Path,'is_file',return_value=True),patch.object(M.subprocess,'run',return_value=Mock(returncode=0,stdout='{"path":"known-store","configured":true}')):
   args=M.publication_auth_args(['vercel.cmd','api','/test'],{})
  self.assertEqual(args[-2:],['--global-config','known-store'])
 def test_unreadable_auth_metadata_fails_closed(self):
  with patch.object(M.shutil,'which',return_value='node'),patch.object(M.Path,'is_file',return_value=True),patch.object(M.subprocess,'run',return_value=Mock(returncode=0,stdout='invalid')):
   with self.assertRaises(M.PublicationAuthRequired):M.publication_auth_args(['vercel.cmd','api','/test'],{})

class ProductionSafetyTests(unittest.TestCase):
 def test_ui_or_unrelated_content_cannot_enter_data_release(self):
  with patch.object(M,'run',return_value='src/app/page.tsx\n'):
   with self.assertRaisesRegex(RuntimeError,'unrelated'):M.validate_release_diff('a'*40,Path('.'),[Path('public/return-atlas/data/v')])
 def test_only_exact_version_data_and_pointer_allowed(self):
  allowed=[Path('src/data/return-atlas-release.json'),Path('public/return-atlas/data/20261107-aaaaaaaaaaaa')]
  with patch.object(M,'run',return_value='src/data/return-atlas-release.json\npublic/return-atlas/data/20261107-aaaaaaaaaaaa/index.json\n'):
   self.assertEqual(len(M.validate_release_diff('a'*40,Path('.'),allowed)),2)
  with patch.object(M,'run',return_value='public/return-atlas/data/20261107-aaaaaaaaaaaa-escape/index.json'):
   with self.assertRaises(RuntimeError):M.validate_release_diff('a'*40,Path('.'),allowed)
 def test_missing_production_sha_stops_before_git_or_copy(self):
  with patch.object(M,'run') as run:
   with self.assertRaises(RuntimeError):M.stage_on_production(Path('.'),'.',{'meta':{}})
  run.assert_not_called()
 def test_manifest_path_traversal_is_rejected(self):
  with patch.object(M,'read_json',return_value={'version':'20261107-aaaaaaaaaaaa','indexUrl':'/other/index.json'}):
   with self.assertRaises(RuntimeError):M.data_release_paths(Path('.'))

class DataReleaseIntegration(unittest.TestCase):
 def test_diverged_ui_is_preserved_and_retry_reuses_commit(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);remote=root/'remote.git';source=root/'source';source.mkdir()
   def git(*args,cwd=source):
    return subprocess.run(['git',*map(str,args)],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
   git('init','--bare',remote);git('init');git('config','user.name','test');git('config','user.email','test@example.invalid')
   git('remote','add','origin',remote)
   def archive(version):
    for route,pointer in [('return-atlas','return-atlas-release.json'),('tennis-matchup','tennis-matchup-release.json')]:
     data=source/'public'/route/'data'/version;data.mkdir(parents=True,exist_ok=True);(data/'index.json').write_text('{}')
     release=source/'src/data'/pointer;release.parent.mkdir(parents=True,exist_ok=True)
     release.write_text(json.dumps({'version':version,'indexUrl':f'/{route}/data/{version}/index.json'}))
   archive('20261106-aaaaaaaaaaaa');(source/'homepage.txt').write_text('current live design')
   git('add','.');git('commit','-m','live');base=git('rev-parse','HEAD');git('push','origin','HEAD:live')
   (source/'homepage.txt').write_text('outdated publisher design');archive('20261107-bbbbbbbbbbbb')
   git('add','.');git('commit','-m','diverged data branch')
   deployment={'meta':{'githubCommitSha':base}}
   with patch.object(M,'validate_live_history') as validate:
    dest,branch,prior,commit=M.stage_on_production(source,root/'state',deployment)
    again=M.stage_on_production(source,root/'state',deployment)
   self.assertEqual((dest/'homepage.txt').read_text(),'current live design')
   self.assertEqual(prior,base);self.assertEqual(again[-1],commit);self.assertEqual(validate.call_count,2)
   self.assertEqual(git('show',f'{commit}:homepage.txt'),'current live design')
   self.assertTrue((dest/'public/return-atlas/data/20261106-aaaaaaaaaaaa/index.json').exists())
   self.assertIn('20261107-bbbbbbbbbbbb',(dest/'src/data/return-atlas-release.json').read_text())

if __name__=='__main__':unittest.main()
