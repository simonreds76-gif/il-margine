import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import urllib.error

S = Path(__file__).parents[1]
sys.path.insert(0, str(S))
import vercel_publisher_auth as A


class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.original = {'token':'old-access', 'refreshToken':'old-refresh', 'expiresAt':100, 'userId':'user'}
        self.store = deepcopy(self.original)
        self.writes = []
        self.metadata = {}
        self.tokens = {'access_token':'new-access','refresh_token':'rotated-refresh','token_type':'Bearer','expires_in':28800}
        def save(path, auth, *args):
            self.writes.append(deepcopy(auth)); self.store=deepcopy(auth)
        for method, value in [('cli_store',Mock(return_value=(Path('auth.json'),'node','module'))),
                              ('renewal_lock',Mock(side_effect=lambda *a:contextlib.nullcontext())),
                              ('read_auth',Mock(side_effect=lambda p:deepcopy(self.store))),
                              ('save_auth',Mock(side_effect=save)),
                              ('exchange',Mock(return_value=self.tokens))]:
            p=patch.object(A,method,value);p.start();self.addCleanup(p.stop)
        p=patch.object(A.time,'time',return_value=1000);p.start();self.addCleanup(p.stop)

    def run_auth(self, **kwargs):
        return A.prepare_environment('vercel', {'CI':'1'}, metadata=self.metadata, **kwargs)

    def test_expired_login_renews_and_saves_rotation_before_exposing_access(self):
        env=self.run_auth()
        self.assertEqual(env['VERCEL_TOKEN'],'new-access')
        self.assertEqual(self.store['refreshToken'],'rotated-refresh')
        self.assertEqual(self.store['expiresAt'],29800)
        self.assertEqual(self.store['userId'],'user')
        self.assertTrue(self.metadata['renewed'])
        self.assertNotIn('access',json.dumps(self.metadata))

    def test_fresh_access_reuses_store_without_exchange(self):
        self.store['expiresAt']=10000
        self.assertEqual(self.run_auth()['VERCEL_TOKEN'],'old-access')
        A.exchange.assert_not_called();self.assertEqual(self.writes,[])

    def test_renewal_is_proactive_near_expiry(self):
        self.store['expiresAt']=1500
        self.run_auth();A.exchange.assert_called_once()

    def test_waiter_reads_rotated_token_and_does_not_exchange_again(self):
        self.run_auth();self.run_auth()
        A.exchange.assert_called_once_with('old-refresh');self.assertEqual(len(self.writes),1)

    def test_explicit_environment_token_does_not_read_or_modify_store(self):
        self.assertEqual(A.prepare_environment('vercel',{'VERCEL_TOKEN':'explicit'}),{'VERCEL_TOKEN':'explicit'})
        A.cli_store.assert_not_called();A.exchange.assert_not_called()

    def test_force_verification_renews_a_fresh_saved_token(self):
        self.store['expiresAt']=10000
        self.run_auth(force_refresh=True);A.exchange.assert_called_once()

    def test_missing_renewal_credential_preserves_access(self):
        del self.store['refreshToken']
        before=deepcopy(self.store)
        with self.assertRaises(A.PublicationAuthRequired): self.run_auth()
        self.assertEqual(self.store,before);self.assertEqual(self.writes,[])

    def test_transport_failure_preserves_credentials(self):
        A.exchange.side_effect=A.PublicationAuthUnavailable('unavailable')
        with self.assertRaises(A.PublicationAuthUnavailable): self.run_auth()
        self.assertEqual(self.store,self.original);self.assertEqual(self.writes,[])

    def test_rejection_preserves_credentials_and_does_not_launch_login(self):
        A.exchange.side_effect=A.PublicationAuthRequired('rejected')
        with self.assertRaises(A.PublicationAuthRequired):self.run_auth()
        self.assertEqual(self.store,self.original);self.assertEqual(self.writes,[])

    def test_concurrent_interactive_login_is_not_overwritten(self):
        newer={**self.original,'token':'interactive-access','refreshToken':'interactive-refresh','expiresAt':10000}
        A.read_auth.side_effect=[self.original,newer]
        self.assertEqual(self.run_auth()['VERCEL_TOKEN'],'interactive-access')
        self.assertEqual(self.writes,[])

    def test_unusable_concurrent_login_is_not_overwritten(self):
        A.read_auth.side_effect=[self.original,{}]
        with self.assertRaises(A.PublicationAuthUnavailable):self.run_auth()
        self.assertEqual(self.writes,[])

    def test_unverified_persistence_stops_before_use_of_new_access(self):
        A.save_auth.side_effect=A.PublicationAuthUnavailable('save failed')
        with self.assertRaises(A.PublicationAuthUnavailable):self.run_auth()


class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.opener=Mock();p=patch.object(A.urllib.request,'build_opener',return_value=self.opener);p.start();self.addCleanup(p.stop)
        p=patch.object(A.time,'sleep');p.start();self.addCleanup(p.stop)
    def response(self, data):
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps(data).encode();return response
    def test_token_goes_only_to_exact_provider_with_no_redirects(self):
        data={'access_token':'synthetic','token_type':'Bearer','expires_in':28800}
        self.opener.open.return_value=self.response(data)
        self.assertEqual(A.exchange('synthetic-refresh'),data)
        request=self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.vercel.com/login/oauth/token')
        self.assertNotIn('synthetic',request.full_url)
        self.assertEqual(self.opener.open.call_args.kwargs['timeout'],8)
        self.assertIsNone(A.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_transient_then_success_is_bounded(self):
        self.opener.open.side_effect=[urllib.error.HTTPError('provider',503,'temporary',{},io.BytesIO(b'secret body')), self.response({'access_token':'test','token_type':'Bearer','expires_in':28800})]
        A.exchange('synthetic');self.assertEqual(self.opener.open.call_count,2)
    def test_invalid_grant_never_retries_or_prints_body(self):
        self.opener.open.side_effect=urllib.error.HTTPError('provider',400,'secret',{},io.BytesIO(b'secret'))
        with self.assertRaises(A.PublicationAuthRequired) as error:A.exchange('secret')
        self.assertNotIn('secret',str(error.exception));self.assertEqual(self.opener.open.call_count,1)
    def test_network_timeout_is_bounded_and_does_not_expose_url(self):
        self.opener.open.side_effect=TimeoutError('secret')
        with self.assertRaises(A.PublicationAuthUnavailable) as error:A.exchange('secret')
        self.assertNotIn('secret',str(error.exception));self.assertEqual(self.opener.open.call_count,2)
    def test_malformed_success_is_rejected(self):
        self.opener.open.return_value=self.response({'access_token':'test'})
        with self.assertRaises(A.PublicationAuthUnavailable):A.exchange('synthetic')
        self.assertEqual(self.opener.open.call_count,1)


@unittest.skipUnless(os.name=='nt','Windows scheduled publisher')
class MutexTests(unittest.TestCase):
    def test_other_process_waits_then_acquires_without_stale_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'acquired'; path=Path(directory)/'auth.json'
            code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from vercel_publisher_auth import renewal_lock\nwith renewal_lock(Path(sys.argv[2])): Path(sys.argv[3]).write_text('acquired')"
            with A.renewal_lock(path):
                child=subprocess.Popen([sys.executable,'-c',code,str(S),str(path),str(marker)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                time.sleep(.3);self.assertFalse(marker.exists())
            out,err=child.communicate(timeout=5)
            self.assertEqual(child.returncode,0,err.decode());self.assertTrue(marker.exists())


if __name__=='__main__':unittest.main()
