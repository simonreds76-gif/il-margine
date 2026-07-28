from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "oncourt-compute-fair-odds.py"
SPEC = importlib.util.spec_from_file_location("oncourt_compute_fair_odds", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TransientRequestError(Exception):
    pass


class Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


class FairOddsHttpRetryTests(unittest.TestCase):
    def call(self, request_func, method: str):
        sleeps: list[float] = []
        response = MODULE._http_request_with_retry(
            request_func,
            TransientRequestError,
            method,
            "https://example.test/rest/v1/daily_fair_odds",
            retries=4,
            retry_base_sleep=1.5,
            retry_status={408, 425, 429, 500, 502, 503, 504},
            timeout=45,
            sleep_func=sleeps.append,
        )
        return response, sleeps

    def test_patch_retries_transient_connection_error(self):
        calls: list[str] = []

        def request(method, _url, **_kwargs):
            calls.append(method)
            if len(calls) == 1:
                raise TransientRequestError("TLS connection closed")
            return Response(204)

        response, sleeps = self.call(request, "PATCH")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(calls, ["PATCH", "PATCH"])
        self.assertEqual(sleeps, [1.5])

    def test_post_retries_503_and_returns_conflict_for_existing_recovery(self):
        responses = iter((Response(503), Response(409)))

        response, sleeps = self.call(lambda *_args, **_kwargs: next(responses), "POST")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(sleeps, [1.5])

    def test_non_transient_status_is_not_retried(self):
        calls = 0

        def request(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return Response(400)

        response, sleeps = self.call(request, "DELETE")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(calls, 1)
        self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
