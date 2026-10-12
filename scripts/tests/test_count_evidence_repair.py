import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from football_count_results import paired_result_rows,snapshot_index,identity
from settlement_utils import normalize_team_name
from football_team_names import football_form_team_key

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
P=load('paired_repair_test','team-shots-paired-reference.py')
I=load('input_repair_test','refresh-football-count-inputs.py')
NOW=datetime(2026,10,12,12,tzinfo=timezone.utc)

class EvidenceTests(unittest.TestCase):
    def forecast(self):
        return dict(contract_id='original',match_date='2026-10-11',kickoff_utc='2026-10-11T18:45:00Z',league='ligue-1',home_team='ESTAC Troyes',away_team='Olympique Marseille',team='Olympique Marseille',line=15.5,odds={'over':2.,'under':1.75},models={m:dict(p_over=.6,mean=17,selected_side='over') for m in P.MODELS})
    def evidence(self):
        return dict(home_shots=9,away_shots=17,source='fotmob',observed_at=NOW.isoformat(),evidence_path='snapshot.json')
    def test_exact_settlement_keeps_original_prices_and_forecasts(self):
        row=self.forecast();before=copy.deepcopy(row)
        base,audit=paired_result_rows([row],[],{identity(row):self.evidence()},NOW)
        status=P.summarize([row],base,NOW)
        record=status['models']['v4']['hypothetical_selections']
        self.assertEqual((record['wins'],record['pnl_units'],record['roi']),(1,1.,1.))
        self.assertEqual(row,before);self.assertEqual(len(audit),1)
    def test_wrong_day_league_or_opponent_does_not_settle(self):
        row=self.forecast()
        for field,value in [('match_date','2026-10-10'),('league','cup'),('away_team','Lyon')]:
            other=dict(row,**{field:value})
            base,_=paired_result_rows([row],[],{identity(other):self.evidence()},NOW)
            self.assertEqual(P.summarize([row],base,NOW)['settled_contracts'],0)
    def test_early_or_invalid_count_is_held(self):
        row=self.forecast()
        for change in [dict(observed_at='2026-10-11T20:00:00Z'),dict(away_shots=-1),dict(away_shots=2.5),dict(away_shots=None)]:
            base,_=paired_result_rows([row],[],{identity(row):dict(self.evidence(),**change)},NOW)
            self.assertEqual(base,[])
    def test_conflicting_counts_remain_explicit(self):
        row=self.forecast();base=[dict(date=row['match_date'],league=row['league'],home_team=row['home_team'],away_team=row['away_team'],team=row['team'],shots_for=15)]
        merged,_=paired_result_rows([row],base,{identity(row):self.evidence()},NOW)
        self.assertEqual(P.summarize([row],merged,NOW)['conflicting_results'],1)
    def test_latest_observed_correction_wins_not_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'data/results-snapshot';p.mkdir(parents=True)
            fixture=dict(self.evidence(),home_team='Troyes',away_team='Marseille')
            for name,observed,value in [('2026-10-10',NOW,17),('2026-10-11',NOW-timedelta(hours=1),16),('2026-10-12',NOW+timedelta(hours=1),18)]:
                (p/(name+'.json')).write_text(json.dumps(dict(fetched_at=observed.isoformat(),leagues={'ligue-1':{'fixtures':{'2026-10-11|troyes|marseille':dict(fixture,away_shots=value)}}})))
            index=snapshot_index(root,NOW)
            self.assertEqual(index[identity(self.forecast())]['away_shots'],17)
    def test_troyes_settlement_alias_matches_existing_inference_alias(self):
        self.assertEqual(normalize_team_name('ESTAC Troyes'),'troyes')
        self.assertEqual(football_form_team_key('ESTAC Troyes'),'troyes')

class InputTests(unittest.TestCase):
    def packet(self):
        fixture=dict(datetime='2026-10-11 12:00:00',isResult=True,h={'title':'Troyes'},a={'title':'Marseille'},goals={'h':'1','a':'2'},xG={'h':'0.9','a':'2.1'})
        match=dict(home={'name':'Troyes','score':1},away={'name':'Marseille','score':2},status={'finished':True,'utcTime':'2026-10-11T12:00:00Z'})
        props=dict(general={'matchTimeUTCDate':'2026-10-11T12:00:00Z','homeTeam':{'name':'Troyes'},'awayTeam':{'name':'Marseille'}},content={'stats':{'Periods':{'All':{'stats':[{'stats':[{'key':k,'stats':v} for k,v in [('total_shots',[9,17]),('ShotsOnTarget',[3,5]),('corners',[2,6])]]}]}}}})
        return fixture,match,props
    def test_verified_inputs_preserve_zero_missing_odds_and_real_xg(self):
        f,m,p=self.packet();rows=I.verified_rows('ligue-1',f,m,p,NOW)
        self.assertEqual(rows[1]['shots_for'],17);self.assertEqual(rows[1]['xg_for'],2.1)
        self.assertEqual(rows[1]['b365h'],'');self.assertEqual(rows[1]['market_team_win_prob'],'')
        self.assertEqual(rows[0]['match_source'],'fotmob_verified_fulltime')
    def test_unfinished_identity_conflict_or_missing_stats_cannot_enter_form(self):
        for defect in ('not_finished','goals','date','identity','corners'):
            f,m,p=self.packet()
            if defect=='not_finished':m['status']['finished']=False
            if defect=='goals':m['home']['score']=3
            if defect=='date':p['general']['matchTimeUTCDate']='2026-10-10'
            if defect=='identity':p['general']['homeTeam']['name']='Lens'
            if defect=='corners':p['content']['stats']['Periods']['All']['stats'][0]['stats'].pop()
            self.assertIsNone(I.verified_rows('ligue-1',f,m,p,NOW),defect)
    def test_primary_rows_unchanged_and_no_duplicate_on_reapplication(self):
        f,m,p=self.packet();rows=I.verified_rows('ligue-1',f,m,p,NOW)
        fid=I.fixture_id('2026-10-11','ligue-1','Troyes','Marseille')
        first,n=I.merge_supplements([],{fid:dict(rows=rows)})
        second,n2=I.merge_supplements(first,{fid:dict(rows=rows)})
        self.assertEqual((n,n2,len(second)),(1,0,2));self.assertEqual(first,second)

    def test_fractional_or_conflicting_raw_count_is_rejected(self):
        for defect in ('fractional','conflict'):
            f,m,p=self.packet()
            stats=p['content']['stats']['Periods']['All']['stats'][0]['stats']
            if defect=='fractional':stats[0]['stats'][0]=9.5
            else:stats.append({'key':'total_shots','stats':[8,17]})
            self.assertIsNone(I.verified_rows('ligue-1',f,m,p,NOW),defect)

if __name__=='__main__':unittest.main()
