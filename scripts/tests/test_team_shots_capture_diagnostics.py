import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('capture_diagnostics', SCRIPTS/'team-shots-scrape-odds.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class CaptureDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        capture.configure_odds_api_http_budget(9)

    def test_shared_discovery_covers_all_leagues_inside_existing_request_budget(self):
        kickoff=(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat()
        events=[{'id':i,'date':kickoff,'home':'Home FC','away':'Away FC',
                 'league':{'slug':config['slug']}}
                for i,config in enumerate(capture.LEAGUE_CONFIGS.values(),1)]
        discovery=Mock(); discovery.json.return_value=events
        def response(url, **kwargs):
            if url.endswith('/events'): return discovery
            ids=kwargs['params']['eventIds'].split(',')
            odds=Mock(status_code=200)
            odds.json.return_value=[{**e,'bookmakers':{'Bet365':[{
                'name':'Total Shots Home','odds':[{'hdp':12.5,'over':'1.9','under':'1.9'}]
            }]}} for e in events if str(e['id']) in ids]
            return odds
        with patch.object(capture.requests,'get',side_effect=response) as get:
            rows=[]
            for league in capture.LEAGUE_CONFIGS:
                found,_,_=capture.scrape_odds_api('test',league,'Bet365',days_ahead=2,kickoff_within_minutes=1440)
                rows.extend(found)
            self.assertEqual(len(rows),10)
            self.assertEqual(get.call_count,6)
            self.assertEqual(capture._ODDS_API_HTTP_REQUEST_COUNT,6)
            capture.configure_odds_api_http_budget(9)
            capture.discover_odds_api_events('test',2)
            self.assertEqual(get.call_count,7)

    def test_upcoming_fixture_outside_close_window_is_not_missing_feed(self):
        response = Mock()
        response.json.return_value = [{'id':1, 'date':(datetime.now(timezone.utc)+timedelta(hours=5)).isoformat(), 'league':{'slug':'spain-la-liga'}}]
        diagnostics=[]
        with patch.object(capture,'odds_api_get',return_value=response) as get:
            rows, selected, errors=capture.scrape_odds_api('test','la-liga','Bet365',kickoff_within_minutes=90,discovery_diagnostics=diagnostics)
        self.assertEqual((rows,selected,errors),([],0,[]))
        self.assertEqual(diagnostics[0]['league_events'],1)
        self.assertEqual(diagnostics[0]['state'],'NO_EVENTS_IN_KICKOFF_WINDOW')
        self.assertEqual(get.call_count,1)

    def test_invalid_success_payload_is_an_error_not_zero_events(self):
        response=Mock();response.json.return_value={'error':'quota exhausted'}
        with patch.object(capture,'odds_api_get',return_value=response):
            with self.assertRaisesRegex(ValueError,'invalid event list'):
                capture.scrape_odds_api('test','epl','Bet365')

    def test_no_league_events_is_distinct_from_close_window_filter(self):
        response=Mock();response.json.return_value=[]
        diagnostics=[]
        with patch.object(capture,'odds_api_get',return_value=response):
            capture.scrape_odds_api('test','epl','Bet365',discovery_diagnostics=diagnostics)
        self.assertEqual(diagnostics[0]['state'],'NO_LEAGUE_EVENTS_IN_FEED')

if __name__=='__main__': unittest.main()
