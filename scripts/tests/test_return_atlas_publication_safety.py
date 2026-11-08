import importlib.util,json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch,Mock
S=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('refresh_safety',S/'refresh-return-atlas.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class AuthTests(unittest.TestCase):
 def test_token_stays_in_child_environment_and_curl_args_stay_intact(self):
  env={}
  args=['vercel.cmd','curl','/return-atlas','--','--fail','--silent']
  with patch.object(M,'prepare_environment',return_value={'VERCEL_TOKEN':'test-secret'}):
   actual=M.publication_auth_args(args,env)
  self.assertEqual(actual,args);self.assertEqual(env['VERCEL_TOKEN'],'test-secret')
  self.assertEqual(env['VERCEL_ORG_ID'],M.TEAM);self.assertEqual(env['VERCEL_PROJECT_ID'],M.PROJECT)
  self.assertNotIn('test-secret',str(actual));self.assertNotIn('--global-config',actual)
 def test_missing_auth_never_launches_vercel(self):
  with patch.object(M,'prepare_environment',side_effect=M.PublicationAuthRequired('missing')),patch.object(M.subprocess,'run') as run:
   with self.assertRaises(M.PublicationAuthRequired):M.run(['vercel.cmd','api','/test'])
  run.assert_not_called()
 def test_cli_errors_cannot_echo_the_child_token(self):
  with patch.object(M,'prepare_environment',return_value={'VERCEL_TOKEN':'test-secret'}),patch.object(M.subprocess,'run',return_value=Mock(returncode=1,stdout='',stderr='failed test-secret')):
   with self.assertRaises(RuntimeError) as error:M.run(['vercel.cmd','api','/test'])
  self.assertNotIn('test-secret',str(error.exception))

class ScopeTests(unittest.TestCase):
 def test_api_curl_and_promotion_share_explicit_team_without_global_mutation(self):
  for tail in [['api','/v9/projects/p?teamId='+M.TEAM,'--raw'],['promote','dpl_candidate','--yes']]:
   with self.subTest(command=tail[0]),patch.object(M,'prepare_environment',return_value={'VERCEL_TOKEN':'test-secret'}):
    command=M.publication_auth_args(['vercel.cmd',*tail],{})
   self.assertEqual(command,['vercel.cmd','--scope',M.TEAM,*tail])
   self.assertNotIn('--global-config',command)
 def test_curl_never_forwards_scope_and_overrides_wrong_link_environment(self):
  args=['vercel.cmd','curl','/return-atlas','--deployment','https://example.vercel.app','--','--fail','--silent']
  env={'VERCEL_ORG_ID':'wrong','VERCEL_PROJECT_ID':'wrong'}
  with patch.object(M,'prepare_environment',return_value={}):
   self.assertEqual(M.publication_auth_args(args,env),args)
  self.assertEqual(env['VERCEL_ORG_ID'],M.TEAM);self.assertEqual(env['VERCEL_PROJECT_ID'],M.PROJECT)
  with patch.object(M,'prepare_environment',return_value={}):
   with self.assertRaisesRegex(RuntimeError,'curl scope'):
    M.publication_auth_args(['vercel.cmd','curl','/return-atlas','--scope',M.TEAM],{})
 def test_existing_matching_scope_is_not_duplicated(self):
  for option in [['--scope',M.TEAM],['--scope='+M.TEAM],['-S',M.TEAM]]:
   args=['vercel.cmd',*option,'promote','dpl_candidate','--yes']
   with patch.object(M,'prepare_environment',return_value={}):self.assertEqual(M.publication_auth_args(args,{}),args)
 def test_conflicting_or_missing_scope_never_launches_cli(self):
  for option in [['--scope','team_other'],['--scope=team_other'],['-S','team_other'],['--scope']]:
   with self.subTest(option=option),patch.object(M,'prepare_environment',return_value={}),patch.object(M.subprocess,'run') as launch:
    with self.assertRaisesRegex(RuntimeError,'scope'):M.run(['vercel.cmd','promote','dpl_candidate',*option])
   launch.assert_not_called()
 def test_curl_passthrough_does_not_override_cli_scope(self):
  args=['vercel.cmd','curl','/return-atlas','--','--header','--scope=literal-header-value']
  with patch.object(M,'prepare_environment',return_value={}):
   self.assertEqual(M.publication_auth_args(args,{}),args)

class DeploymentIdentityTests(unittest.TestCase):
 def candidate(self):
  return {'id':'dpl_candidate','ownerId':M.TEAM,'team':{'id':M.TEAM},'projectId':M.PROJECT,'target':'production','meta':{'githubCommitSha':'a'*40}}
 def test_exact_candidate_is_accepted(self):
  M.validate_deployment_identity(self.candidate(),expected_sha='a'*40,expected_id='dpl_candidate')
 def test_other_project_team_preview_or_commit_are_rejected(self):
  for field,value in [('projectId','other'),('ownerId','team_other'),('team',{'id':'team_other'}),('target','preview'),('meta',{'githubCommitSha':'b'*40}),('id','dpl_other')]:
   data=self.candidate();data[field]=value
   with self.subTest(field=field),self.assertRaises(RuntimeError):M.validate_deployment_identity(data,expected_sha='a'*40,expected_id='dpl_candidate')
 def test_missing_owner_is_not_inferred_from_slug_or_url(self):
  data=self.candidate();data.pop('ownerId');data.pop('team')
  with self.assertRaisesRegex(RuntimeError,'project/team'):M.validate_deployment_identity(data)

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
   portrait=source/M.CATALOGUE;portrait.parent.mkdir(parents=True,exist_ok=True);portrait.write_text('[{"name":"Known Player","src":"/portrait.jpg"}]')
   git('add','.');git('commit','-m','diverged data branch')
   deployment={'meta':{'githubCommitSha':base}}
   with patch.object(M,'validate_live_history') as validate:
    dest,branch,prior,commit=M.stage_on_production(source,root/'state',deployment,worktree_root=root/'worktrees')
    again=M.stage_on_production(source,root/'state',deployment,worktree_root=root/'worktrees')
   self.assertEqual((dest/'homepage.txt').read_text(),'current live design')
   self.assertEqual(prior,base);self.assertEqual(again[-1],commit);self.assertEqual(validate.call_count,2)
   self.assertEqual(git('show',f'{commit}:homepage.txt'),'current live design')
   self.assertEqual((dest/M.CATALOGUE).read_bytes(),portrait.read_bytes())
   portrait.write_text('[{"name":"Known Player","src":"/new.jpg"}]')
   with patch.object(M,'validate_live_history'):
    changed=M.stage_on_production(source,root/'state',deployment,worktree_root=root/'worktrees')
   self.assertNotEqual(changed[1],branch)
   self.assertEqual((changed[0]/M.CATALOGUE).read_bytes(),portrait.read_bytes())
   self.assertTrue((dest/'public/return-atlas/data/20261106-aaaaaaaaaaaa/index.json').exists())
   self.assertIn('20261107-bbbbbbbbbbbb',(dest/'src/data/return-atlas-release.json').read_text())

if __name__=='__main__':unittest.main()
