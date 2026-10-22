from pathlib import Path
import sys, tempfile, unittest, json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aerial_market_capture import retain_headed_markets, quoted_markets
from datetime import datetime, timezone
import copy

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

class Quotes(unittest.TestCase):
    def test_market_identity_price_mapping_and_ambiguity(self):
        now=datetime(2026,10,18,12,30,tzinfo=timezone.utc)
        fixture={'kickoff':'2026-10-18T13:00:00Z','teams':[{'id':'1','name':'Home','players':[{'name':'Example Player'}]},{'id':'2','name':'Away','players':[]}]}
        candidate={'team_id':'1','player':'Example Player','markets_to_check':['1+ headed shot on target','headed goal']}
        event={'event_id':'123','home':'Home','away':'Away','kickoff':fixture['kickoff'],'bookmaker':'Bet365','captured_at':'2026-10-18T12:00:00Z','source':'odds-api.io/v3/odds/multi','markets':[
          {'name':'Player Headed Shots on Target','odds':[{'label':'Example Player (1)','hdp':0.5,'over':'4.500'},{'label':'Example Player (1)','hdp':1.5,'over':'23.00'},{'label':'Example Player (2)','hdp':0.5,'over':'9.00'}]},
          {'name':'Goal Method','odds':[{'label':'Example Player (Header) (1)','under':'15.00'},{'label':'Example Player (Outside the Box) (1)','under':'8.00'}]}]}
        snapshot={'events':[event]}
        quotes=quoted_markets(fixture,candidate,snapshot,now)
        self.assertEqual([(q['market'],q['odds']) for q in quotes],[('1+ headed shot on target',4.5),('headed goal',15.0)])
        self.assertEqual(quotes[1]['source_price_field'],'under')
        for key,value in [('captured_at','2026-10-18T09:00:00Z'),('kickoff','2026-10-18T14:00:00Z'),('home','Other'),('bookmaker','Other')]:
            bad=copy.deepcopy(event);bad[key]=value
            self.assertEqual(quoted_markets(fixture,candidate,{'events':[bad]},now),[])
        self.assertEqual(quoted_markets(fixture,candidate,{'events':[event,event]},now),[])
        bad=copy.deepcopy(event);bad['markets'][0]['odds'].append({'label':'Example Player (1)','hdp':0.5,'over':'3.00'})
        self.assertEqual([q['market'] for q in quoted_markets(fixture,candidate,{'events':[bad]},now)],['headed goal'])
        bad=copy.deepcopy(event);bad['markets'][1]['odds'][0]['over']='1.10'
        self.assertEqual([q['market'] for q in quoted_markets(fixture,candidate,{'events':[bad]},now)],['1+ headed shot on target'])
