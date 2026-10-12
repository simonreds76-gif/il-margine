import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class SuspensionTests(unittest.TestCase):
    def test_suspended_capture_cannot_load_credentials_or_request_any_bookmaker(self):
        capture = load('tennis-most-aces-capture')
        with patch.object(capture, 'load_common') as common, patch('sys.argv', ['capture', '--bookmakers', 'Bet365,Kambi']):
            self.assertEqual(capture.main(), 0)
            common.assert_not_called()

    def test_suspended_forecast_keeps_settlement_and_never_registers(self):
        forecast = load('tennis-most-aces-forecast')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with patch('sys.argv', ['forecast', '--ledger', str(folder/'ledger.csv'), '--report', str(folder/'report.txt'), '--json', str(folder/'report.json')]), patch.object(forecast, 'register') as register, patch.object(forecast, 'settle', return_value=0) as settle:
                self.assertEqual(forecast.main(), 0)
                register.assert_not_called()
                settle.assert_called_once()
                self.assertEqual(json.loads((folder/'report.json').read_text())['status'], 'SUSPENDED_NO_PRICES')

    def test_suspended_priced_shadow_keeps_settlement(self):
        shadow = load('tennis-most-aces-shadow')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with patch('sys.argv', ['shadow', '--ledger', str(folder/'ledger.csv'), '--report', str(folder/'report.txt')]), patch.object(shadow, 'register') as register, patch.object(shadow, 'settle', return_value=0) as settle, patch.object(shadow, 'sackmann_matches', return_value=[]):
                self.assertEqual(shadow.main(), 0)
                register.assert_not_called()
                settle.assert_called_once()

    def test_daily_ordinary_ace_board_continues_without_most_aces_builds(self):
        daily = load('run-tennis-props-daily')
        with patch.object(daily, 'run') as run:
            daily.refresh_derived_ace_boards('2026-10-12')
            self.assertEqual(run.call_count, 1)
            self.assertIn('tennis-props-v3-live.py', run.call_args.args[0][1])

if __name__ == '__main__':
    unittest.main()
