from pathlib import Path
import sys, tempfile, unittest, json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aerial_market_capture import retain_headed_markets

class Capture(unittest.TestCase):
    def test_exact_prices_bookmaker_and_market_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'prices.json'
            market={'name':'Player Headed Shots on Target','odds':[{'label':'Example','hdp':0.5,'over':'4.50'}]}
            payload=[{'id':12,'bookmakers':{'Bet365':[market,{'name':'Goal Method','odds':[]},{'name':'Player Shots','odds':[]}], 'Other':[{'name':'Headed Goals','odds':[]}]}}]
            self.assertEqual(retain_headed_markets(p,payload,{'12':{'home':'Home','away':'Away'}},'2026-10-18T12:00:00Z'),2)
            e=json.loads(p.read_text())['events'][0]
            self.assertEqual(e['markets'][0],market)
            self.assertEqual(e['home'],'Home')
            retain_headed_markets(p,[{'id':12,'bookmakers':{}}],{},'2026-10-18T13:00:00Z')
            self.assertEqual(len(json.loads(p.read_text())['events'][0]['markets']),2)
            retain_headed_markets(p,[{'id':12,'bookmakers':{'Bet365':[]}}],{},'2026-10-18T14:00:00Z')
            self.assertEqual(json.loads(p.read_text())['events'][0]['markets'],[])
            retain_headed_markets(p,[],{},'2026-10-21T12:00:00Z')
            self.assertEqual(json.loads(p.read_text())['events'],[])
