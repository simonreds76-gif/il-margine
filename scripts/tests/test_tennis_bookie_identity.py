import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tennis_bookmaker_identity as I
import tennis_paper_prices as P
import tennis_most_aces_current as C
import tennis_sisal_5050 as S

NOW=datetime(2026,11,14,10,26,tzinfo=timezone.utc)

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'data/oncourt';self.folder.mkdir(parents=True)
        self.write('players',[dict(id='1',name='Taylor Harry Fritz'),dict(id='2',name='Thiago Agustin Tirante')])
        self.write('tours',[dict(id='77',name='Stockholm',date='2026-11-09')])
        self.fixture=dict(tour_id='77',player1_id='1',player2_id='2',round_id='12',date='2026-11-14',result='',live='')
        self.write('today',[self.fixture])
        self.event=dict(home='Taylor Fritz',away='Thiago Agustin Tirante',date='2026-11-14T12:00:00Z')
    def write(self,name,rows):
        with (self.folder/f'{name}_atp.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        I._tables.cache_clear()
    def resolve(self,label='Stockholm Open',**event):
        return I.event_tournament(self.root,dict(self.event,**event),label,'ATP')
    def test_verified_native_edition_resolves_open_suffix_and_fritz_alias(self):
        self.assertEqual(self.resolve(),'Stockholm')
        self.assertEqual(self.resolve(home=self.event['away'],away=self.event['home']),'Stockholm')
    def test_sponsored_native_name_uses_id_bound_board_label(self):
        self.write('tours',[dict(id='77',name='BNP Paribas Nordic Open - Stockholm',date='2026-11-09')])
        p=self.root/'data/tennis-props/player-props-board.csv';p.parent.mkdir(parents=True)
        row=dict(tour='ATP',tour_id='77',date='2026-11-14',player_id='1',opponent_id='2',
                 player='Taylor Harry Fritz',opponent='Thiago Agustin Tirante',tournament='Stockholm')
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
        self.assertEqual(self.resolve(),'Stockholm')
        row['player_id']='3'
        with p.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
        I._tables.cache_clear()
        self.assertEqual(self.resolve(),'Stockholm Open')

    def test_unknown_event_pair_date_and_level_stay_unresolved(self):
        for update in [dict(home='Fritz'),dict(away='Other Player'),dict(date='2027-11-14T12:00:00Z')]:
            self.assertEqual(self.resolve(**update),'Stockholm Open')
        for label in ['Stockholm Challenger','Stockholm Qualifying','Stockholm 2 Open','Stockholm 2025 Open']:
            self.assertEqual(self.resolve(label),label)
    def test_completed_live_duplicate_round_or_edition_never_bridged(self):
        for change in [dict(result='6-3 6-2'),dict(live='1')]:
            self.write('today',[dict(self.fixture,**change)])
            self.assertEqual(self.resolve(),'Stockholm Open')
        self.write('today',[self.fixture,dict(self.fixture,round_id='10')])
        self.assertEqual(self.resolve(),'Stockholm Open')
    def test_missing_native_data_preserves_provider_label(self):
        self.assertEqual(I.event_tournament(self.root/'missing',self.event,'Stockholm Open','ATP'),'Stockholm Open')

class PriceTests(unittest.TestCase):
    def row(self,book='Sisal IT',price='2.1',**extra):
        return dict(date='2026-11-14',tour='ATP',tournament='Stockholm',player='Taylor Harry Fritz',
                    opponent='Thiago Agustin Tirante',market='aces',line='4.5',over_odds=price,under_odds='1.5',
                    bookmaker=book,capture_ts=(NOW-timedelta(minutes=1)).isoformat(),
                    match_start_utc=(NOW+timedelta(hours=2)).isoformat(),trackable_shadow='true',shadow_side='OVER',**extra)
    def test_player_contract_best_price_is_order_independent(self):
        a=self.row();b=self.row('Bet365','2.5');b['player']='Taylor Fritz'
        for rows in [[a,b],[b,a]]:
            selected=P.best_prop_rows(rows,NOW)
            self.assertEqual(len(selected),1);self.assertEqual(selected[0]['bookmaker'],'Bet365')
    def test_different_player_line_side_and_market_remain_separate(self):
        a=self.row(); variants=[dict(a,player=a['opponent'],opponent=a['player']),dict(a,line='5.5'),
                               dict(a,shadow_side='UNDER'),dict(a,market='double_faults')]
        self.assertEqual(len(P.best_prop_rows([a]+variants,NOW)),5)
    def test_stale_removed_or_started_quote_cannot_win(self):
        a=self.row();old=self.row('Bet365','9');old['capture_ts']=(NOW-timedelta(hours=7)).isoformat()
        self.assertEqual(P.best_prop_rows([a,old],NOW),[a])
        newest=dict(a,capture_ts=NOW.isoformat(),trackable_shadow='false')
        self.assertEqual(P.best_prop_rows([a,newest],NOW),[])
        self.assertEqual(P.best_prop_rows([dict(a,match_start_utc=NOW.isoformat())],NOW),[])
    def report(self,best_eligible=True):
        rows=[]
        for book,price,ev in [('Bet365','2.25','30.957'),('Grosvenor','2.55','48.418')]:
            row=dict(date='2026-11-14',tournament='Stockholm',player1='Taylor Fritz',player2='Thiago Agustin Tirante',
                     bookmaker=book,selected_odds=price,recommended_side='P2',value_player2_pct=ev,
                     price_captured_at=(NOW-timedelta(minutes=1)).isoformat(),match_start_utc=(NOW+timedelta(hours=2)).isoformat(),
                     bet_eligible='yes' if book=='Bet365' or best_eligible else 'no')
            rows.append(dict(candidate=row))
        return dict(generated_at=NOW.isoformat(),matches=[dict(model=C.COUNT_MODEL,prices=rows)])
    def test_most_aces_best_book_and_no_lower_price_gate_evasion(self):
        self.assertEqual(C.alert_rows(self.report(),NOW)[0]['bookmaker'],'Grosvenor')
        self.assertEqual(C.alert_rows(self.report(False),NOW),[])
    def test_reversed_source_keeps_raw_contract_and_compares_same_player(self):
        import json,hashlib
        now=datetime.now(timezone.utc);shadow=C.load_shadow()
        b=dict(date=now.date().isoformat(),tour='ATP',tournament='Stockholm',player1='Taylor Fritz',
               player2='Thiago Agustin Tirante',p_player1='0.38',p_draw='0.06',p_player2='0.56',
               player1_confidence='MED',player2_confidence='MED',quote_status='READY',model=C.COUNT_MODEL,
               generated_at_utc=now.isoformat())
        raw=json.dumps(dict(name='Most Aces 3-Way',odds=[dict(home='2.25',draw='16',away='1.65')]))
        q=dict(date=b['date'],tour='ATP',tournament='Stockholm',player1=b['player2'],player2=b['player1'],
               event_id='123',bookmaker='Sisal IT',player1_odds='2.25',draw_odds='16',player2_odds='1.65',
               capture_ts=now.isoformat(),match_start_utc=(now+timedelta(hours=2)).isoformat(),
               raw_market_json=raw,evidence_sha256=hashlib.sha256(raw.encode()).hexdigest(),source_url='https://www.sisal.it/event/123')
        other=dict(q,event_id='kambi:456',bookmaker='Grosvenor',player1=b['player1'],player2=b['player2'],
                   player1_odds='1.82',draw_odds='10',player2_odds='2.28')
        report=C.compare([b],[q,other],[],now,shadow)
        self.assertIsNotNone(report['matches'][0]['prices'][0]['candidate'])
        row=C.alert_rows(report,now)[0]
        self.assertEqual(row['bookmaker'],'Grosvenor')
        self.assertEqual({x['bookmaker']:float(x['odds']) for x in row['compared_prices']}, {'Sisal IT':2.25,'Grosvenor':2.28})

    def test_sisal_uses_same_verified_full_name_alias(self):
        self.assertEqual(S.player_name('Taylor Harry Fritz'),S.player_name('Taylor Fritz'))
        self.assertNotEqual(S.player_name('Fritz'),S.player_name('Taylor Fritz'))

if __name__=='__main__':unittest.main()
