import copy
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import moviodds_prices as adapter
import moviodds_gk_verification as verify
import goalkeeper_quote_integrity as gate
import goalkeeper_price_selection as prices

def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class AtomicGk(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((SCRIPTS/'tests/fixtures/moviodds-gk-atomic.json').read_text())
        self.now=datetime(2026,11,6,17,16,20,tzinfo=timezone.utc)
        self.targets=[{'id':m['id'],'home':m['home'],'away':m['away'],'date':m['kickoff_utc'],
                      'league':{'slug':adapter.LEAGUES[m['league']]}} for m in self.raw['board']['matches']]

    def verified(self):
        def read(url,params,get):return copy.deepcopy(self.raw['live'][params['fi']])
        with patch.object(adapter,'download_response',side_effect=read):
            return verify.verify_board(self.raw['board'],self.targets,now=self.now)

    def rows(self):
        data,receipt,_=self.verified()
        events,_=adapter.normalize(data,'soccer',self.now,targets=self.targets)
        rows=load('goalkeeper-saves-capture').extract_rows(events,{},bookmaker_name='Bet365',captured_at='unused',capture_mode='publication')
        return rows,receipt

    def noll(self):
        row=next(r for r in self.rows()[0] if r['player']=='Nahuel Noll' and r['line']=='3.5')
        return {**row,'goalkeeper':row['player'],'candidate_status':'eligible_shadow','blockers':'',
                'contract_scope':'named_player','edge':'.1','fair_odds':'2.04','strongest_for_fixture':'yes',
                'created_at':self.now.isoformat(),'generated_at':self.now.isoformat(),'status':'pending',
                'selection_policy':'near_even_value_v2','signal_id':'fixture-noll-over-3.5'}

    def test_real_two_fixture_ladders_keep_only_full_contract_and_price_agreement(self):
        before=copy.deepcopy(self.raw)
        rows,receipt=self.rows()
        self.assertEqual(len(rows),17);self.assertEqual(receipt['requests'],2)
        noll=next(r for r in rows if r['player']=='Nahuel Noll' and r['odds_decimal']=='2.2500')
        self.assertEqual(noll['line'],'3.5');self.assertTrue(gate.verified_quote(noll))
        stank=next(r for r in rows if r['player']=='Filip Stankovic' and r['line']=='3.5')
        self.assertEqual(stank['odds_decimal'],'2.3750')
        self.assertFalse(any(r['player']=='Filip Stankovic' and r['line']=='2.5' for r in rows))
        self.assertEqual(self.raw,before)

    def test_reused_noll_selection_id_cannot_attach_4plus_price_to_3plus(self):
        m=next(m for m in self.raw['board']['matches'] if m['id']=='202802349')
        q=next(q for q in m['quotes'] if q['sel_id']=='383209880');q.update(handicap='2.5',side='3+')
        rows,receipt=self.rows()
        self.assertFalse(any(r['player']=='Nahuel Noll' and r['odds_decimal']=='2.2500' for r in rows))
        self.assertEqual(next(r for r in receipt['fixtures'] if r['fixture_id']=='202802349')['excluded']['selection_contract_changed'],1)

    def test_original_stankovic_wrong_price_is_rejected_without_relabelling(self):
        m=next(m for m in self.raw['board']['matches'] if m['id']=='202802859')
        q=next(q for q in m['quotes'] if q['sel_id']=='383711098');q.update(odds_dec=2.25,odds_frac='5/4')
        rows,_=self.rows()
        self.assertFalse(any(r['player']=='Filip Stankovic' and r['odds_decimal']=='2.2500' for r in rows))
        self.assertEqual(q['side'],'3+');self.assertEqual(q['odds_dec'],2.25)

    def test_bad_full_response_fails_only_its_fixture(self):
        for change in ({'site':'com.au'},{'source':'cached'},{'fixture':'wrong'}, {'server_time':'2026-11-06T15:00:00Z'}, {'group_status':{}}):
            with self.subTest(change=change):
                original=copy.deepcopy(self.raw['live']['202802349']);self.raw['live']['202802349'].update(change)
                rows,_=self.rows();self.assertTrue(rows);self.assertFalse(any(r['player']=='Nahuel Noll' for r in rows))
                self.raw['live']['202802349']=original

    def test_duplicate_or_suspended_live_selection_does_not_verify(self):
        live=self.raw['live']['202802349'];q=next(q for q in live['quotes'] if q['sel_id']=='383209880')
        live['quotes'].append(copy.deepcopy(q))
        self.assertFalse(any(r['player']=='Nahuel Noll' and r['line']=='3.5' for r in self.rows()[0]))
        live['quotes'].pop();q['suspended']=True
        self.assertFalse(any(r['player']=='Nahuel Noll' and r['line']=='3.5' for r in self.rows()[0]))

    def test_timeout_keeps_other_fixture_and_original_bookmaker(self):
        data,receipt,_=self.verified()
        def read(url,params,get):
            if params['fi']=='202802349':raise TimeoutError()
            return copy.deepcopy(self.raw['live'][params['fi']])
        with patch.object(adapter,'download_response',side_effect=read):
            _,receipt,_=verify.verify_board(self.raw['board'],self.targets,now=self.now)
        self.assertEqual(receipt['verified_quotes'],7)
        self.assertEqual(next(r for r in receipt['fixtures'] if r['fixture_id']=='202802349')['error'],'TimeoutError')
        original=[{'id':'202802859','bookmakers':{'Grosvenor':[{'name':'existing','odds':[]}]}}]
        with patch.object(adapter,'capture',return_value=([],receipt)):
            merged,_=adapter.merge_football(original,self.targets)
        self.assertEqual(merged,original)

    def test_capture_reports_partial_verification_and_keeps_compact_raw_evidence(self):
        def read(url,params,get):return copy.deepcopy(self.raw['live'][params['fi']])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'raw.gz'
            with patch.object(adapter,'download',return_value=self.raw['board']),patch.object(adapter,'download_response',side_effect=read),patch.object(adapter,'datetime',wraps=datetime) as clock,patch.object(verify,'datetime',wraps=datetime) as other_clock:
                clock.now.return_value=self.now;other_clock.now.return_value=self.now
                events,receipt=adapter.capture('soccer',targets=self.targets,force=True,verify_goalkeepers=True,raw_path=path)
            self.assertTrue(events);self.assertNotIn('goalkeeper_source_hold',receipt)
            self.assertEqual(receipt['goalkeeper_coverage_status'],'INCOMPLETE')
            self.assertEqual(receipt['goalkeeper_fixture_coverage'][0]['status'],'PARTIALLY_VERIFIED')
            import gzip
            evidence=json.loads(gzip.decompress(path.read_bytes()))
            for response in evidence['goalkeeper_live_responses'].values():
                self.assertEqual(response['evidence_scope'],'goalkeeper_saves_only')
                self.assertTrue(all(q['group_id']=='177703' for q in response['quotes']))

    def test_proof_cannot_be_reused_for_another_contract_price_or_capture(self):
        row=self.noll();self.assertIsNone(gate.current_quote_issue(row));self.assertIsNone(gate.recorded_quote_issue(row))
        for change in ({'line':'2.5'},{'odds_decimal':'2.5'},{'player':'Someone else'}, {'event_id':'other'}, {'side':'under'}, {'captured_at':self.now.isoformat()}, {'quote_verification':''}):
            with self.subTest(change=change):self.assertIsNotNone(gate.current_quote_issue({**row,**change}))
        historical={**row,'quote_verification':'','captured_at':'2026-11-06T15:58:29Z'}
        self.assertIsNotNone(gate.recorded_quote_issue(historical))

    def test_verified_name_survives_exact_fixture_lineup_resolution(self):
        row=self.noll()
        for source_name,canonical in [('Lukasz Skorupski','Łukasz Skorupski'),('Daniel Fernandes','Daniel Heuer Fernandes'),('Odisseas Vlachodimos','Odysseas Vlachodimos')]:
            proof=json.loads(row['quote_verification']);proof['player']=source_name
            source={**row,'player':source_name,'quote_verification':json.dumps(proof)}
            bound=gate.bind_resolved_keeper(source,canonical)
            candidate={**source,'goalkeeper':canonical,'quote_verification':bound};candidate.pop('player')
            self.assertTrue(gate.verified_quote(candidate))
            self.assertFalse(gate.verified_quote({**candidate,'goalkeeper':'Different keeper'}))
            other={**candidate,'bookmaker':'Grosvenor','source':'grosvenor_direct','quote_verification':'','odds_decimal':'2.1'}
            self.assertEqual(prices.best_offers([candidate,other],self.now),[candidate])
            shadow=load('goalkeeper-saves-shadow')
            fixture={'lineup_type':'predicted','home_starters':[{'name':canonical,'role_group':'GK'}],'away_starters':[]}
            key=(source['match_date'],shadow.football_form_team_key(source['home_team']),shadow.football_form_team_key(source['away_team']))
            with patch.object(shadow,'build_features',return_value=(tuple(range(9)),[])),patch.object(shadow,'predict_mean',return_value=4),patch.object(shadow,'price_side',return_value={'edge':.1,'model_probability':.55,'push_probability':0,'fair_odds':1.818}):
                built=shadow.build_candidates([source],{}, {'alpha':.2},{key:fixture},self.now.isoformat())
            self.assertEqual(len(built),1);self.assertTrue(gate.verified_quote(built[0]),source_name)
        broken={**source,'line':'9.5'}
        self.assertEqual(gate.bind_resolved_keeper(broken,canonical),broken['quote_verification'])

    def test_verified_bet365_competes_with_grosvenor_only_on_same_line(self):
        row=self.noll();other={**row,'bookmaker':'Grosvenor','source':'grosvenor_direct','odds_decimal':'2.1','quote_verification':'','captured_at':self.now.isoformat()}
        self.assertEqual(prices.best_offers([row,other],self.now),[row])
        reason,comparison=prices.alert_price_check(row,[row,other],self.now)
        self.assertIsNone(reason);self.assertEqual([r['bookmaker'] for r in comparison],['Bet365','Grosvenor'])
        other['odds_decimal']='2.5';self.assertEqual(prices.best_offers([row,other],self.now),[other])
        other['line']='2.5';self.assertEqual(len(prices.best_offers([row,other],self.now)),2)
        self.assertEqual(prices.current_offers([row],self.now+timedelta(minutes=11)),[])

    def test_capture_evidence_survives_ledger_and_alert_gate_without_duplicate(self):
        row=self.noll();shadow=load('goalkeeper-saves-shadow');alerts=load('goalkeeper-saves-alerts')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'signals.csv'
            count,records=shadow.append_signals(path,[row],self.now.isoformat());self.assertEqual(count,1)
            self.assertTrue(gate.verified_quote(records[0]));self.assertTrue(alerts.eligible(records[0],self.now))
            second,after=shadow.append_signals(path,[row],self.now.isoformat());self.assertEqual(second,0)
            self.assertEqual(after[0]['quote_verification'],records[0]['quote_verification'])
            self.assertEqual(shadow.report_payload([],after,self.now.isoformat(),0)['evidence']['quote_quarantined'],0)

    def test_history_schema_extension_preserves_all_old_values_and_unknown_columns(self):
        capture=load('goalkeeper-saves-capture');row=self.noll()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'history.csv'
            path.write_text('captured_at,event_id,bookmaker,player,line,side,odds_decimal,legacy_note\n2026-11-05T12:00:00Z,old,Bet365,Original,2.5,over,2.25,retain me\n')
            with path.open(newline='') as f:old=list(csv.DictReader(f))[0]
            self.assertEqual(capture.append_rows(path,[row]),1)
            self.assertEqual(capture.append_rows(path,[row]),0)
            with path.open(newline='') as f:after=list(csv.DictReader(f))
            self.assertEqual({k:after[0][k] for k in old},old)
            self.assertTrue(gate.verified_quote(after[1]))

if __name__=='__main__':unittest.main()
