import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).parents[2];sys.path.insert(0,str(ROOT/'scripts'))
import football_atlas_weekly as w
import atlas_production_release as release

class Tests(unittest.TestCase):
 def transport(self):
  helper=SimpleNamespace(run=Mock(),TEAM='team-test',PROJECT='project-test',validate_deployment_identity=Mock(),check_static_budget=Mock())
  response=Mock();response.json.return_value={'deploymentId':'live-id'}
  with patch.dict(os.environ,{'VERCEL_TOKEN':'test-only-not-a-key'}),patch.object(w.legacy,'load_module',return_value=helper),patch.object(w.requests,'get',return_value=response),patch.object(release,'stage_football',return_value=(Path('.'),'release','a'*40,'b'*40)),patch.object(w.legacy,'publish'):
   w.publish(Path('.'),{'version':'new','indexUrl':'/football-atlas/test.json'},{})
  return helper.project_scoped_api
 def test_get_and_post_use_exact_provider_and_team_without_cli_user_lookup(self):
  api=self.transport();response=Mock(status_code=200,content=b'{}');response.json.return_value={'ok':True}
  with patch.object(w.requests,'request',return_value=response) as request:
   self.assertEqual(api('/v4/aliases/ilmargine.bet'),{'ok':True})
   api('/v13/deployments',{'project':'project-test'})
   self.assertEqual([c.args[0] for c in request.call_args_list],['GET','POST'])
   for call in request.call_args_list:
    self.assertTrue(call.args[1].startswith('https://api.vercel.com/'))
    self.assertEqual(call.kwargs['params'],{'teamId':'team-test'})
    self.assertFalse(call.kwargs['allow_redirects'])
 def test_credential_bearing_redirects_and_errors_never_follow_or_leak(self):
  api=self.transport()
  for status in [302,401,403,500]:
   with patch.object(w.requests,'request',return_value=Mock(status_code=status)):
    with self.assertRaisesRegex(RuntimeError,f'HTTP {status}'):api('/v13/deployments')
  with patch.object(w.requests,'request',side_effect=w.requests.RequestException('test-only-not-a-key')):
   with self.assertRaises(RuntimeError) as exc:api('/v13/deployments')
   self.assertNotIn('test-only-not-a-key',str(exc.exception))
 def test_foreign_destinations_are_rejected_before_request(self):
  api=self.transport()
  with patch.object(w.requests,'request') as request:
   for route in ['https://other.invalid','//other.invalid','other.invalid']:
    with self.assertRaises(ValueError):api(route)
   request.assert_not_called()

if __name__=='__main__':unittest.main()
