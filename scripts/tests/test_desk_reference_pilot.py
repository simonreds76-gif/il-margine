import base64
import gzip
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import desk_reference_pilot as pilot
from desk_reference_compare import pair_prices


class Memory:
    def __init__(self):
        self.objects = {}

    def get(self, path):
        return self.objects.get(path)

    def put(self, path, data):
        if path in self.objects:
            return False
        self.objects[path] = data
        return True


class PrivatePilotTests(unittest.TestCase):
    def test_qualifying_exact_upcoming_games(self):
        at = datetime(2026, 11, 22, tzinfo=timezone.utc)
        base = dict(league="Challenger Test (Qualifiers)", start=(at+timedelta(hours=2)).isoformat(),
                    fixture="fixture", contracts={"totals:22.5":{}})
        snap = {"events":{"a":dict(base,id=1), "b":dict(base,id=2,league="ATP Test"),
                          "c":dict(base,id=3,fixture="live"), "d":dict(base,id=4,contracts={}),
                          "e":dict(base,id=5,start=at.isoformat())}, "in_play_fixtures":["live"]}
        self.assertEqual(pilot.available(snap, at, True), {"1"})
        self.assertEqual(pilot.available(snap, at, False), {"1","2"})

    def test_signed_handicap_reversal_and_suspension(self):
        market = {"key":"s;0;s;-2.5", "period":0, "type":"spread", "status":"open",
                  "prices":[{"designation":"home","points":-2.5,"price":125},
                            {"designation":"away","points":2.5,"price":-135}]}
        sides = {"home":"Z","away":"A"}
        self.assertEqual(pair_prices(market, sides), ("spreads:2.5", [-135,125]))
        self.assertEqual(pair_prices(dict(market,status="closed"), sides), ("spreads:2.5", [None,None]))
        self.assertIsNone(pair_prices(dict(market, period=1), sides))

    def test_stale_or_mismatched_primary_snapshot_is_rejected(self):
        store = Memory()
        at = datetime(2026,11,22,1,tzinfo=timezone.utc)
        add = lambda mins:(at-timedelta(minutes=mins)).isoformat()
        store.put("presentation/desk-tapes/2026-11-22.json", {"slots":{"0030.json":add(31),"0050.json":add(10)}})
        store.put("snapshots/2026/11/22/0050.json", {"observed":add(11)})
        self.assertIsNone(pilot.recent(store, at))

    def test_retry_preserves_raw_and_hash(self):
        store = Memory()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "tape"
            raw = b"x" * 1050000
            path.write_bytes(raw)
            pilot.persist_raw(store, "pilot", path)
            packed = [store.get(f"pilot/raw-{i:04}.json") for i in range(2)]
            restored = b"".join(gzip.decompress(base64.b64decode(c["gzip_base64"])) for c in packed)
            self.assertEqual(restored, raw)
            self.assertEqual(store.get("pilot/manifest.json")["sha256"], hashlib.sha256(raw).hexdigest())
            with self.assertRaises(RuntimeError):
                pilot.persist_raw(store, "pilot", path)
