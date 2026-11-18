"""No secrets or network are used by these provider-contract checks."""
import json,unittest,sys
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import moviodds_auth as auth
import moviodds_prices as prices

class TestMoviOddsAccess(unittest.TestCase):
    def request(self,code,body=None):
        response=Mock(status_code=code)
        response.iter_content.return_value=[json.dumps(body or {}).encode()]
        return response
    def test_auth_goes_only_to_tennis_on_exact_origin_no_redirect(self):
        response=self.request(200,{'site':'com'})
        get=Mock(return_value=response)
        with patch.dict('os.environ',{'MOVIODDS_API_KEY':'dummy-test-key'}):
            prices.download('tennis',get)
            self.assertEqual(get.call_args.kwargs['headers']['X-API-Key'],'dummy-test-key')
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
            self.assertNotIn('key',get.call_args.kwargs['params'])
            self.assertNotIn('X-API-Key',auth.request_headers(prices.URL,{'sport':'soccer'}))
            with self.assertRaises(ValueError):prices.download_response('https://other.invalid/odds',{'sport':'tennis'},get)
            self.assertEqual(get.call_count,1)
    def test_auth_plan_and_http_failures_are_distinct(self):
        for code,key,body,expected in [(401,'',{},'MOVIODDS_KEY_REQUIRED'),
                (401,'dummy',{},'MOVIODDS_KEY_REJECTED'),(403,'dummy',{},'MOVIODDS_ACCESS_DENIED'),
                (429,'dummy',{},'MOVIODDS_RATE_LIMITED'),(302,'dummy',{},'MOVIODDS_REDIRECT_REFUSED'),
                (503,'dummy',{},'MOVIODDS_HTTP_503'),(200,'dummy',{'site':'com','markets':'main'},'MOVIODDS_MAIN_LINES_ONLY')]:
            response=self.request(code,body)
            with self.subTest(expected=expected),patch.dict('os.environ',{'MOVIODDS_API_KEY':key}),patch.object(auth,'windows_credential',return_value=None):
                events,receipt=prices.capture('tennis',get=Mock(return_value=response),force=True)
                self.assertEqual(events,[])
                self.assertEqual((receipt['errors'],receipt['http_status']),([expected],code))
                self.assertNotIn('dummy',str(receipt))
                response.close.assert_called_once()

if __name__=='__main__':unittest.main()
