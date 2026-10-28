import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sisal_capture_handoff as H


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.quotes=self.root/'prices.csv'
        self.runner=Mock(return_value=SimpleNamespace(returncode=0))

    def install(self):
        for name in ('data/tennis-props/shadow/sisal-5050-v1/registration.json',
            'data/tennis-props/models/v3-atp-aces-live.txt','data/tennis-props/shadow/aces-v3-projection-board.csv',
            'data/oncourt/today_atp.csv','scripts/tennis_sisal_5050.py','prices.csv'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')

    def test_capture_host_cannot_install_a_new_trial(self):
        self.assertEqual(H.run(self.root,self.quotes,runner=self.runner)['state'],'NOT_INSTALLED')
        self.runner.assert_not_called()

    def test_missing_board_does_not_fall_back_to_another_model(self):
        self.install();(self.root/'data/tennis-props/shadow/aces-v3-projection-board.csv').unlink()
        self.assertEqual(H.run(self.root,self.quotes,runner=self.runner)['state'],'MISSING_RUNTIME_INPUTS')
        self.runner.assert_not_called()

    def test_current_prices_reach_paper_tracker_without_alert_command(self):
        self.install();r=H.run(self.root,self.quotes,runner=self.runner)
        self.assertEqual(r['state'],'COMPLETED')
        command=self.runner.call_args.args[0]
        self.assertEqual(command[-2:],['--quotes',str(self.quotes)])
        self.assertIn('tennis_sisal_5050.py',command[1]);self.assertNotIn('--send',command)
        self.assertEqual(self.runner.call_args.kwargs['timeout'],240)

    def test_failures_visible_without_losing_price_file(self):
        self.install()
        for error,state in ((subprocess.TimeoutExpired('paper',240),'TRACKER_TIMEOUT'),(OSError('test'),'TRACKER_LAUNCH_FAILED')):
            self.runner.side_effect=error
            self.assertEqual(H.run(self.root,self.quotes,runner=self.runner)['state'],state)
            self.assertTrue(self.quotes.exists())

if __name__=='__main__':unittest.main()
