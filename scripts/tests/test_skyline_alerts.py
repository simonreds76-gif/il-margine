import copy
from datetime import datetime,timezone,timedelta
import pathlib
import sys
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from skyline_alerts import eligible,message,run
from skyline_paper import summarize

NOW=datetime(2026,10,18,14,tzinfo=timezone.utc)

def fixture():
    r=dict(key='a'*64,version='skyline-v1',cohort='prospective_paper',lineup='confirmed',
        selections={'baseline':True,'height':True},predictions={'baseline':.2,'height':.22},
        captured_at=NOW.isoformat(),lineup_observed_at=NOW.isoformat(),
        quote={'captured_at':NOW.isoformat(),'bookmaker':'Bet365'},kickoff=(NOW+timedelta(minutes=50)).isoformat(),
        odds=6,model_sha256='frozen',player='Test Player',match='Home v Away',fixture_id='1')
    state={'version':'skyline-v1','forecasts':{r['key']:r},'outcomes':{},
        'report':{'status':'CAPTURING','generated_at':NOW.isoformat(),'model_sha256':'frozen'}}
    state['report']['stats']={'baseline':summarize([r],{},'baseline',NOW)}
    state['report']['board']=[{'key':r['key'],'lineup':'confirmed'}]
    return r,state

class Alerts(unittest.TestCase):
    def test_paper_message_and_zero_results(self):
        r,s=fixture();text=message(r,s,NOW)
        for value in ['PAPER ONLY','Bet365 recorded odds: 6.00','fair odds: 5.00','EV: +20.0%',
            'CONFIRMED XI','No settled selections yet','zero real stake','1 pending']:
            self.assertIn(value,text)

    def test_correct_variant_full_record_roi(self):
        r,s=fixture()
        for key,odds,outcome,selected in [('b',4,'win',True),('c',3,'loss',True),('d',9,'void',True),('e',20,'win',False)]:
            prior=copy.deepcopy(r);prior.update(key=key,odds=odds,selections={'baseline':selected,'height':True})
            s['forecasts'][key]=prior;s['outcomes'][key]={'status':outcome}
        s['report']['stats']={'baseline':summarize(list(s['forecasts'].values()),s['outcomes'],'baseline',NOW)}
        text=message(r,s,NOW)
        self.assertIn('ROI: +100.0% | Profit: +2.00u',text)
        self.assertIn('1W / 1L | 2 settled | 2u staked',text)
        self.assertIn('1 pending | 1 void',text)

    def test_gates(self):
        r,s=fixture();self.assertTrue(eligible(r,s,NOW))
        changes=[{'lineup':'expected'},{'cohort':'preview'},{'version':'skyline-v2'},
            {'selections':{'baseline':False,'height':True}}, {'model_sha256':'changed'},
            {'kickoff':NOW.isoformat()}, {'captured_at':(NOW-timedelta(hours=3)).isoformat()},
            {'quote':{'captured_at':(NOW-timedelta(hours=3)).isoformat()}},
            {'quote':{'captured_at':NOW.isoformat(),'bookmaker':'Other'}},
            {'lineup_observed_at':(NOW+timedelta(minutes=1)).isoformat()}]
        for change in changes:self.assertFalse(eligible({**r,**change},s,NOW),change)
        for status in ['sent','reserved','delivery_uncertain']:
            self.assertFalse(eligible(r,{**s,'alerts':{r['key']:{'status':status}}},NOW))
        self.assertFalse(eligible(r,{**s,'outcomes':{r['key']:{'status':'review'}}},NOW))
        self.assertFalse(eligible(r,{**s,'report':{**s['report'],'status':'FAILED'}},NOW))
        self.assertFalse(eligible(r,{**s,'report':{**s['report'],'board':[]}},NOW))

    def run_state(self,state,sender):
        def writer(root,fn):
            changed=copy.deepcopy(state)
            if fn(changed) is False:return False
            state.clear();state.update(changed);return True
        with patch.dict('os.environ',{'OPS_ALERT_TELEGRAM_BOT_TOKEN':'test','OPS_ALERT_TELEGRAM_CHAT_ID':'private'}):
            return run(None,now=NOW,transmit=True,sender=sender,reader=lambda root:{'payload':state},writer=writer)

    def test_duplicate_and_uncertain_are_never_resent(self):
        for receipt,status in [(123,'sent'),(None,'delivery_uncertain')]:
            r,s=fixture();sender=Mock(return_value=receipt)
            result=self.run_state(s,sender)
            self.assertEqual(result['status'],status)
            self.assertEqual(s['alerts'][r['key']]['status'],status)
            self.assertEqual(self.run_state(s,sender)['eligible'],0)
            sender.assert_called_once()

    def test_failed_claim_cannot_send(self):
        r,s=fixture();sender=Mock()
        with patch.dict('os.environ',{'OPS_ALERT_TELEGRAM_BOT_TOKEN':'test','OPS_ALERT_TELEGRAM_CHAT_ID':'private'}):
            result=run(None,now=NOW,transmit=True,sender=sender,reader=lambda root:{'payload':s},writer=lambda root,fn:False)
        sender.assert_not_called();self.assertEqual(result['sent'],0)

if __name__=='__main__':unittest.main()
