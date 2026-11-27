from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import csv
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from goalkeeper_alert_prices import paired_prices, format_prices
from goalkeeper_quote_integrity import verified_quote
from paddy_keeper_prices import capture_paddy_prices
from goalkeeper_delivery import digest_keys, pick_keys, telegram_text_matches


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1]/(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class AlertPair(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        observed = self.now.isoformat()
        kickoff = (self.now+timedelta(hours=18)).isoformat()
        self.row = dict(event_id='123', league='serie-a', home_team='Parma', away_team='Roma',
                        kickoff_at=kickoff, venue='away', line='2.5', side='over', bookmaker='Grosvenor',
                        odds_decimal='2.35', goalkeeper='Away goalkeeper', contract_scope='team_goalkeeper_away',
                        identity_basis='bookmaker_team_side', captured_at=observed, fair_odds=2.2,
                        created_at=observed, match_date=kickoff[:10], candidate_status='eligible_shadow',
                        edge=.068, status='pending', signal_id='abc', selection_policy='near_even_value_v2')
        group = {'177703':{'polled_at':observed}}
        quotes = []
        for name in ('Keeper A','Keeper B','Keeper C'):
            for n, (fraction, price) in enumerate([('1/4',1.25),('11/8',2.375),('3/1',4.0)], start=2):
                quotes.append(dict(line=name, sel_id=str(len(quotes)+1), fixture_id='91', group_id='177703',
                                   group_name='Goalkeeper Saves', ts=observed, side=f'{n}+', handicap=n-.5,
                                   odds_frac=fraction, odds_dec=price, market_id='177703' if n==3 else '177769'))
        board = dict(id='91', home='Parma', away='Roma', league='Italy Serie A',
                     kickoff_utc=kickoff, in_play=False, group_status=group, quotes=quotes)
        self.live = dict(fixture='91', site='com', server_time=observed, source='cache',
                         group_status=group, quotes=[dict(q) for q in quotes])
        packet = dict(raw=dict(site='com', matches=[board]), goalkeeper_live_responses={'91':self.live},
                      receipt=dict(goalkeeper_fixture_coverage=[dict(event_id='123',source_event_id='91')]))
        calendar = dict(observed_at=observed, fixtures=[dict(home='Parma',away='Roma',date=kickoff,home_id='p',away_id='r')])
        roster = {name:dict(id=name, name=name, role_group='keepers', team_id=club,
                             club_observed_at=observed, club_source_sha256='hash')
                  for name, club in [('Keeper A','p'),('Keeper B','r'),('Keeper C','r')]}
        self.sources = (packet, calendar, roster)

    def pair(self, **change):
        row = {**self.row, **change}
        return paired_prices(row,[row],self.now,self.sources)

    def test_team_and_named_scope_without_official_lineup(self):
        prices = self.pair()
        self.assertEqual([q['goalkeeper'] for q in prices], ['Keeper B','Keeper C',''])
        self.assertFalse(any(verified_quote(q) for q in prices))
        text = format_prices({**self.row, 'display_prices':prices})
        self.assertIn('2.375</b> · EV +8.0% · best price · unconfirmed feed quote', text)
        self.assertIn('Grosvenor · team keeper · <b>2.35</b> · EV +6.8%', text)
        home = self.pair(contract_scope='team_goalkeeper_home',venue='home',goalkeeper='Home goalkeeper')
        self.assertEqual([q['goalkeeper'] for q in home], ['Keeper A',''])
        named = self.pair(alert_model='keeper_watch_v1',goalkeeper='Keeper B',identity_basis='same_fixture_lineup_side')
        self.assertEqual([q['goalkeeper'] for q in named], ['Keeper B',''])

    def paddy_capture(self, markets, **change):
        event = dict(id='123', date=self.row['kickoff_at'], home='Parma', away='Roma',
                     bookmakers={'Paddy Power':markets})
        return capture_paddy_prices([{**event, **change}], self.now)

    def test_paddy_full_match_milestone_reaches_send_and_digest_without_second_claim(self):
        market = dict(name='Goalkeeper To Make 3 Or More Saves', updatedAt=self.now.isoformat(),
                      odds=[dict(home='4.50', away='2.64')])
        self.sources += (self.paddy_capture([market]),)
        alerts = script('goalkeeper-saves-alerts')
        state = {}
        self.assertEqual(alerts.claim([self.row],state,'run',self.now,[self.row],self.sources),1)
        signal = state['signals']['abc']['signal']
        self.assertIn('Paddy Power · team keeper · <b>2.64</b> · EV +20.0% · best price',alerts.message(signal))
        self.assertIn('0.5u at 2.35 Grosvenor',alerts.message(signal))
        self.assertEqual(alerts.claim([self.row],state,'retry',self.now,[self.row],self.sources),0)
        digest = script('football-daily-signal-digest')
        candidates = digest.goalkeeper_candidates([self.row],self.row['match_date'],now=self.now,sources=self.sources)
        self.assertIn('Paddy Power · team keeper · 2.64', digest.candidate_block(candidates[0]))

    def test_three_book_telegram_echo_and_cross_publisher_replay(self):
        import html
        import re
        from unittest.mock import Mock
        market = dict(name='Goalkeeper To Make 3 Or More Saves', updatedAt=self.now.isoformat(),
                      odds=[dict(home='4.50', away='2.64')])
        sources = self.sources + (self.paddy_capture([market]),)
        alerts, digest = script('goalkeeper-saves-alerts'), script('football-daily-signal-digest')
        groups = {'GK':digest.goalkeeper_candidates([self.row],self.row['match_date'],now=self.now,sources=sources)}
        candidate = groups['GK'][0]
        env = dict(GITHUB_RUN_ID='run',GITHUB_RUN_ATTEMPT='1',OPS_ALERT_TELEGRAM_BOT_TOKEN='test',OPS_ALERT_TELEGRAM_CHAT_ID='test')
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,env):
            root = Path(directory)
            keepers, football = root/'goalkeeper-saves', root/'football-form'
            keepers.mkdir()
            football.mkdir()
            state, board = keepers/'gk-saves-telegram-state.json',keepers/'candidates.csv'
            digest_state = football/'football-daily-signal-digest-state.json'
            with board.open('w',newline='',encoding='utf8') as f:
                writer=csv.DictWriter(f,self.row)
                writer.writeheader()
                writer.writerow(self.row)
            before = {}
            alerts.claim([self.row],before,'run:1',self.now,[self.row],sources)
            state.write_text(json.dumps(before),encoding='utf8')
            def acknowledge(*args, **kwargs):
                text = html.unescape(re.sub('<[^>]+>', '', kwargs['json']['text']))
                for expected in ('Over 2.5 saves','Fair odds at capture: 2.20','Paddy Power · team keeper · 2.64 · EV +20.0%',
                                 'Bet365 · Keeper B · 2.375 · EV +8.0%', 'Grosvenor · team keeper · 2.35 · EV +6.8%'):
                    self.assertIn(expected,text)
                return Mock(ok=True,json=lambda:{'ok':True,'result':{'message_id':13,'text':text}})
            with patch.object(alerts,'load_sources',return_value=sources), patch.object(alerts,'datetime') as clock, \
                 patch.object(sys,'argv',['alerts','--send','--state',str(state),'--candidates',str(board)]), \
                 patch.object(alerts.requests,'post',side_effect=acknowledge) as send:
                clock.now.return_value=self.now
                clock.fromisoformat=datetime.fromisoformat
                alerts.main()
                alerts.main()
                send.assert_called_once()
            sent = json.loads(state.read_text())['signals']
            self.assertIs(sent['abc']['three_book_text_verified'],True)
            self.assertEqual(digest.unseen_candidates(groups,{},sent)['GK'],[])
            # Replay from the other direction, including two rows describing one pick.
            state.write_text(json.dumps({'signals':{}}),encoding='utf8')
            with patch.object(sys,'argv',['digest','--state',str(digest_state),'--date',self.row['match_date']]), \
                 patch.object(digest,'build_candidates',return_value={'GK':[candidate,candidate]}), \
                 patch.object(digest,'publish_keeper_claim') as reserve, \
                 patch.object(digest,'send_telegram',side_effect=lambda body,*args:{'message_id':14,'text':body}) as send:
                digest.main()
                digest.main()
                reserve.assert_called_once()
                send.assert_called_once()
                self.assertEqual(send.call_args.args[0].count('Paddy Power ·'),1)
            receipts=json.loads(digest_state.read_text())['sent']
            self.assertTrue(receipts[candidate['id']]['three_book_text_verified'])
            self.assertEqual(alerts.claim([self.row],{},'again',self.now,[self.row],sources,digest_keys(receipts)),0)
            self.assertTrue(pick_keys(self.row) & digest_keys({candidate['id']:{'status':'uncertain'}}))
            self.assertFalse(telegram_text_matches({'message_id':15,'text':'missing odds'},'expected complete text'))

    def test_paddy_rejects_unmatched_stale_suspended_and_conflicting_odds(self):
        market = dict(name='Player Saves', updatedAt=self.now.isoformat(),
                      odds=[dict(label='Keeper B', hdp=2.5,over=2.6,under=1.4)])
        invalid = [dict(name='Player Saves First Half'),dict(name='Combined Goalkeeper Saves'),
                   dict(updatedAt=''),dict(updatedAt=(self.now-timedelta(minutes=11)).isoformat()),
                   dict(updatedAt=(self.now+timedelta(minutes=1)).isoformat()),dict(suspended=True),
                   dict(odds=[dict(label='Keeper A',hdp=2.5,over=2.6)]),
                   dict(odds=[dict(label='Keeper B',hdp=3.0,over=2.6)]),
                   dict(odds=[dict(label='Keeper B',hdp=2.5,under=2.6)]),
                   dict(odds=[dict(label='Keeper B',hdp=2.5,over=2.6,suspended=True)]),
                   dict(odds=[dict(label='Keeper B',hdp=2.5,over=v) for v in (2.6,2.7)])]
        def display(snapshot):
            prices = paired_prices(self.row,[self.row],self.now,self.sources+(snapshot,))
            return format_prices({**self.row,'display_prices':prices})
        for change in invalid:
            self.assertIn('Paddy Power · no fresh matching odds', display(self.paddy_capture([{**market, **change}])), change)
        for change in [dict(inPlay=True),dict(id='456'),dict(home='Roma',away='Parma'),
                       dict(date=(self.now+timedelta(hours=19)).isoformat())]:
            self.assertIn('Paddy Power · no fresh matching odds',display(self.paddy_capture([market],**change)),change)
        self.assertIn('Paddy Power · Keeper B · <b>2.60</b>',display(self.paddy_capture([market])))
        self.assertIn('Paddy Power · no fresh matching odds',display([]))

    def test_wrong_line_side_fixture_and_stale_quotes(self):
        for change in (dict(side='under'),dict(line=4.5),dict(away_team='Lecce'),
                       dict(kickoff_at=(self.now+timedelta(hours=19)).isoformat()),
                       dict(captured_at=(self.now-timedelta(minutes=11)).isoformat())):
            self.assertEqual(self.pair(**change), [], change)
        self.live['server_time'] = (self.now-timedelta(minutes=11)).isoformat()
        self.assertEqual(self.pair(), [])

    def test_mislabelled_or_unbracketed_main_cannot_supply_price(self):
        for q in self.live['quotes']:
            if q['line'] == 'Keeper C' and q['side'] == '3+':
                q.update(handicap=3.5, side='4+')
            if q['line'] == 'Keeper B' and q['side'] == '4+':
                q['suspended'] = True
        self.assertEqual(self.pair(), [])

    def test_prepare_can_retry_a_missing_pair_without_duplicate(self):
        alerts = script('goalkeeper-saves-alerts')
        state = {}
        self.assertEqual(alerts.claim([self.row],state,'1',self.now,[self.row],({}, {}, {})), 0)
        self.assertFalse(state['signals'])
        self.assertEqual(alerts.claim([self.row],state,'2',self.now,[self.row],self.sources), 1)
        self.assertEqual(alerts.claim([self.row],state,'3',self.now,[self.row],self.sources), 0)

    def test_new_verified_higher_price_leads_and_paper_record_stays_locked(self):
        alerts = script('goalkeeper-saves-alerts')
        row = {**self.row, 'contract_scope':'named_player', 'goalkeeper':'Keeper B'}
        higher = {**row, 'bookmaker':'Bet365','odds_decimal':'2.50'}
        with patch('goalkeeper_price_selection.current_quote_issue', return_value=None):
            reason, _, prices = alerts.checked_alert_prices(row,[row,higher],self.now,({}, {}, {}))
        self.assertIsNone(reason)
        self.assertEqual([q['odds'] for q in prices],[2.5,2.35])
        self.assertIn('0.5u at 2.35 Grosvenor',alerts.message({**row,'display_prices':prices}))

    def test_digest_requires_fresh_pair_and_shows_prices_in_plain_text(self):
        digest = script('football-daily-signal-digest')
        args = ([self.row],self.row['match_date'])
        self.assertEqual(digest.goalkeeper_candidates(*args, now=self.now,sources=({}, {}, {})), [])
        result = digest.goalkeeper_candidates(*args, now=self.now,sources=self.sources)
        text = digest.candidate_block(result[0])
        self.assertIn('Bet365 · Keeper B · 2.375', text)
        self.assertIn('Grosvenor · team keeper · 2.35', text)
        self.assertIn('fair 2.20',text)
        self.assertNotIn('<b>',text)

    def test_send_time_loss_releases_unattempted_claim_only(self):
        alerts = script('goalkeeper-saves-alerts')
        state = {}
        alerts.claim([self.row],state,'run:1',self.now,[self.row],self.sources)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder/'state.json'
            path.write_text(json.dumps(state),encoding='utf8')
            board = folder/'candidates.csv'
            with board.open('w',newline='',encoding='utf8') as f:
                writer=csv.DictWriter(f,self.row)
                writer.writeheader()
                writer.writerow(self.row)
            env=dict(GITHUB_RUN_ID='run',GITHUB_RUN_ATTEMPT='1',OPS_ALERT_TELEGRAM_BOT_TOKEN='test',
                     OPS_ALERT_TELEGRAM_CHAT_ID='test')
            with patch.dict(os.environ,env), patch.object(sys,'argv',['alerts','--send','--state',str(path),'--candidates',str(board)]), patch.object(alerts,'datetime') as clock, patch.object(alerts.requests,'post') as post:
                clock.now.return_value=self.now
                clock.fromisoformat=datetime.fromisoformat
                alerts.main()
                post.assert_not_called()
            persisted = json.loads(path.read_text(encoding='utf8'))
            self.assertFalse(persisted['signals'])
            self.assertEqual(persisted['last_deferred_before_send']['reason'], 'awaiting_fresh_bet365_grosvenor_pair')
            self.assertEqual(alerts.claim([self.row],persisted,'new:1',self.now,[self.row],self.sources),1)
