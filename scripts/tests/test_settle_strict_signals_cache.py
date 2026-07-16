from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
MODULE_PATH = SCRIPTS / "settle-strict-signals.py"
SPEC = importlib.util.spec_from_file_location("settle_strict_signals_cache", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LocalGamesWindowCacheTests(unittest.TestCase):
    def test_matching_source_and_covering_window_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "games_atp.csv"
            cache = root / "settlement-cache.json"
            source.write_text("date,winner_id,loser_id,result\n", encoding="utf-8")
            rows = [
                {
                    "winner_id": 1,
                    "loser_id": 2,
                    "date": date(2026, 7, 16),
                    "result": "6-4 6-4",
                }
            ]
            with mock.patch.object(MODULE, "_scan_local_games_window", return_value=rows) as scanner:
                first = MODULE.load_local_games_window(
                    source,
                    date(2026, 7, 15),
                    date(2026, 7, 18),
                    cache_path=cache,
                )
                second = MODULE.load_local_games_window(
                    source,
                    date(2026, 7, 16),
                    date(2026, 7, 17),
                    cache_path=cache,
                )

            self.assertEqual(first, second)
            self.assertEqual(scanner.call_count, 1)
            scan_start = scanner.call_args.args[1]
            scan_end = scanner.call_args.args[2]
            self.assertLess(scan_start, date(2026, 7, 15))
            self.assertGreater(scan_end, date(2026, 7, 18))


if __name__ == "__main__":
    unittest.main()
