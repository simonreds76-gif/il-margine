"""Publisher contract checks, including the real Blob 0.5 SDK when installed."""
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'upload-fair-odds-lab-blob.py'
spec = importlib.util.spec_from_file_location('lab_blob_upload', SCRIPT)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def test_modern_api_preserves_stable_public_path_and_overwrite(self):
        put = Mock(return_value=SimpleNamespace(url='https://example.test/signals.json'))
        package = ModuleType('vercel')
        package.blob = SimpleNamespace(sync=SimpleNamespace(put_blob=put))
        with patch.dict(sys.modules, {'vercel': package}), patch.object(Path, 'read_bytes', return_value=b'{}'):
            client = publisher.load_blob_client()
            publisher.upload_file(client, 'signals', publisher.DEFAULT_ARTIFACTS[1][1], 'fair-odds-lab/signals.json', 60)
        put.assert_called_once_with('fair-odds-lab/signals.json', b'{}', access='public',
            content_type='application/json', allow_overwrite=True, add_random_suffix=False,
            cache_control_max_age=60)

    def test_legacy_local_sdk_supported(self):
        factory = Mock()
        package = ModuleType('vercel')
        package.blob = SimpleNamespace(BlobClient=factory)
        with patch.dict(sys.modules, {'vercel': package}):
            self.assertIs(publisher.load_blob_client(), factory.return_value)

    def test_unknown_api_is_not_reported_as_missing_package(self):
        package = ModuleType('vercel')
        package.blob = SimpleNamespace()
        with patch.dict(sys.modules, {'vercel': package}), self.assertRaisesRegex(SystemExit, 'Unsupported'):
            publisher.load_blob_client()

    def test_invalid_json_never_uploads(self):
        client = Mock()
        with patch.object(Path, 'read_bytes', return_value=b'not json'), self.assertRaises(json.JSONDecodeError):
            publisher.upload_file(client, 'signals', publisher.DEFAULT_ARTIFACTS[1][1], 'signals.json', 60)
        client.put.assert_not_called()

    def test_missing_token_skips_without_loading_sdk(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'argv', [str(SCRIPT)]), patch.object(publisher, 'load_blob_client') as loader:
            publisher.main()
        loader.assert_not_called()

    def test_real_sdk_wire_contract(self):
        try:
            from vercel.blob import sync
            from vercel._internal.core.session import session
            import httpx2
        except ImportError:
            self.skipTest('Install vercel-blob==0.5.0 for the real SDK contract test')
        seen = []

        def respond(request):
            seen.append(request)
            return httpx2.Response(200, json={
                'url': 'https://test.public.blob.vercel-storage.com/fair-odds-lab/signals.json',
                'downloadUrl': 'https://test.public.blob.vercel-storage.com/fair-odds-lab/signals.json?download=1',
                'pathname': 'fair-odds-lab/signals.json', 'contentType': 'application/json',
                'contentDisposition': 'inline', 'etag': 'test-etag'})

        with patch.dict(os.environ, {'BLOB_READ_WRITE_TOKEN': 'vercel_blob_rw_test_dummy'}):
            with session(httpx_client_factory=lambda: httpx2.Client(transport=httpx2.MockTransport(respond))):
                result = publisher.load_blob_client().put('fair-odds-lab/signals.json', b'{}',
                    access='public', content_type='application/json', overwrite=True, cache_control_max_age=60)
        self.assertEqual(result.pathname, 'fair-odds-lab/signals.json')
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].method, 'PUT')
        self.assertEqual(seen[0].headers['x-allow-overwrite'], '1')
        self.assertEqual(seen[0].headers['x-add-random-suffix'], '0')
        self.assertEqual(seen[0].headers['x-cache-control-max-age'], '60')
        self.assertEqual(seen[0].content, b'{}')


if __name__ == '__main__':
    unittest.main()
