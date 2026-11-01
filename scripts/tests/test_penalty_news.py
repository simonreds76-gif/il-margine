import copy
import importlib.util
from pathlib import Path
import unittest
from copy import deepcopy
import json
import tempfile
import subprocess
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location("penalty_news", Path(__file__).parents[1] / "build-penalty-news.py")
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)
from penalty_news_context import incident_context, narrative_context, clock
publisher_spec = importlib.util.spec_from_file_location('penalty_publisher', Path(__file__).parents[1] / 'publish-penalty-news.py')
publisher = importlib.util.module_from_spec(publisher_spec)
publisher_spec.loader.exec_module(publisher)


class PenaltyNewsTests(unittest.TestCase):
    def test_vercel_read_recovers_timeout_with_exact_scoped_get(self):
        response=Mock(status_code=200);response.json.return_value={'deploymentId':'verified'}
        with patch.dict(publisher.os.environ,{'VERCEL_TOKEN':'test-only'}), patch.object(publisher.requests,'get',side_effect=[publisher.requests.Timeout(),response]) as get, patch.object(publisher.time,'sleep') as sleep:
            self.assertEqual(publisher.vercel_read('/v4/aliases/ilmargine.bet'),{'deploymentId':'verified'})
        self.assertEqual(get.call_count,2);sleep.assert_called_once_with(2)
        self.assertEqual(get.call_args.args,('https://api.vercel.com/v4/aliases/ilmargine.bet',))
        self.assertEqual(get.call_args.kwargs['params'],{'teamId':publisher.TEAM})
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_vercel_read_is_bounded_and_does_not_retry_auth(self):
        for code,count in [(403,1),(503,3)]:
            response=Mock(status_code=code,headers={})
            with patch.dict(publisher.os.environ,{'VERCEL_TOKEN':'test-only'}),patch.object(publisher.requests,'get',return_value=response) as get,patch.object(publisher.time,'sleep'),self.assertRaises(RuntimeError):
                publisher.vercel_read('/v4/aliases/ilmargine.bet')
            self.assertEqual(get.call_count,count)

    def test_vercel_read_respects_long_cooldown_and_rejects_mutation_paths(self):
        response=Mock(status_code=429,headers={'Retry-After':'90'})
        with patch.dict(publisher.os.environ,{'VERCEL_TOKEN':'test-only'}),patch.object(publisher.requests,'get',return_value=response) as get,patch.object(publisher.time,'sleep') as sleep,self.assertRaises(RuntimeError):
            publisher.vercel_read('/v4/aliases/ilmargine.bet')
        self.assertEqual(get.call_count,1);sleep.assert_not_called()
        with self.assertRaises(ValueError):publisher.vercel_read('/v13/deployments')

    def setUp(self):
        self.shot = {"id": 100, "situation": "Penalty", "period": "SecondHalf", "eventType": "Goal",
                     "teamId": 1, "playerId": 9, "fullName": "Test Taker", "min": 90, "minAdded": 4}
        self.payload = {"props": {"pageProps": {
            "general": {"leagueId": 47, "finished": True, "matchId": 123, "matchTimeUTCDate": "2026-10-18T12:00:00Z"},
            "header": {"status": {"finished": True}, "teams": [{"id": 1, "name": "Home", "score": 2}, {"id": 2, "name": "Away", "score": 1}]},
            "content": {"shotmap": {"shots": [self.shot]}}}}}
        self.clubs = {"1": {"name": "Home", "logo": "/home.png"}}

    def run_normalize(self):
        return news.normalize(self.payload, "https://www.fotmob.com/matches/example#123", "2026-10-21T12:00:00Z", self.clubs)

    def test_completed_fact_report_without_reviews(self):
        mid, articles, exclusions = self.run_normalize()
        self.assertEqual(mid, "123")
        self.assertEqual(exclusions, [])
        a = articles[0]
        self.assertEqual(a["minute"], "90+4")
        self.assertEqual(a["clubUrl"], "/penalty-takers/epl/home")
        self.assertIsNone(a["cause"])
        self.assertIn("Home 2–1 Away", a["sentences"][1])

    def test_saved_penalty_and_rebound_goal_are_not_a_conversion(self):
        self.shot["eventType"] = "AttemptSaved"
        rebound = dict(self.shot, id=101, situation="RegularPlay", eventType="Goal")
        self.payload["props"]["pageProps"]["content"]["shotmap"]["shots"].append(rebound)
        articles = self.run_normalize()[1]
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["outcome"], "saved")

    def test_shootouts_and_regular_goals_excluded(self):
        self.shot["period"] = "PenaltyShootout"
        self.assertEqual(self.run_normalize()[1], [])
        self.shot["period"] = "SecondHalf"
        self.shot["situation"] = "RegularPlay"
        self.assertEqual(self.run_normalize()[1], [])

    def test_no_guessing_unknown_outcomes(self):
        self.shot["eventType"] = "Blocked"
        _, articles, exclusions = self.run_normalize()
        self.assertEqual(articles, [])
        self.assertEqual(len(exclusions), 1)

    def test_unfinished_matches_are_held(self):
        self.payload["props"]["pageProps"]["header"]["status"]["finished"] = False
        with self.assertRaises(ValueError):
            self.run_normalize()

    def test_retakes_held_and_identical_events_deduplicated(self):
        shots = self.payload["props"]["pageProps"]["content"]["shotmap"]["shots"]
        shots.append(copy.deepcopy(self.shot))
        self.assertEqual(len(self.run_normalize()[1]), 1)
        shots[1]["id"] = 101
        self.assertEqual(self.run_normalize()[1], [])
        self.assertEqual(len(self.run_normalize()[2]), 2)

    def test_idempotent_merge_and_source_corrections(self):
        first = self.run_normalize()[1]
        second = copy.deepcopy(first)
        second[0]["publishedAt"] = second[0]["updatedAt"] = "2026-10-22T12:00:00Z"
        result = news.merge(first, second, {"123"})
        self.assertEqual(result, first)
        second[0]["sourceHash"] = "corrected"
        result = news.merge(first, second, {"123"})
        self.assertEqual(result[0]["publishedAt"], first[0]["publishedAt"])
        self.assertNotEqual(result[0]["updatedAt"], first[0]["updatedAt"])
        self.assertEqual(news.merge(first, [], set()), first)
        self.assertEqual(news.merge(first, [], {"123"}), [])

    def commentary(self):
        return {'Events': [
            {'MessageId': 'kick', 'Elapsed': 90, 'ElapsedPlus': 4, 'IncidentCode': 'PSG', 'Players': [{'Id': 9, 'TeamId': 1}]},
            {'MessageId': 'conceded', 'Elapsed': 90, 'ElapsedPlus': 2, 'IncidentCode': 'penalty lost', 'Description': 'Penalty conceded by Defender (Away) after a foul in the penalty area.', 'Players': [{'Id': 8, 'TeamId': 2}]},
            {'MessageId': 'won', 'Elapsed': 90, 'ElapsedPlus': 2, 'IncidentCode': 'penalty won', 'Description': 'Penalty Home. Winger draws a foul in the penalty area.', 'Players': [{'Id': 7, 'TeamId': 1}]},
        ]}

    def test_award_identifies_fouled_player_not_taker(self):
        result = incident_context(self.shot, self.commentary(), {})
        self.assertEqual(result['wonBy'], 'Winger')
        self.assertEqual(result['concededBy'], 'Defender')
        self.assertLess(clock(45, 9), clock(46))

    def test_handball_does_not_invent_foul_winner(self):
        c = self.commentary()
        c['Events'].pop()
        c['Events'][1]['Description'] = 'Penalty conceded by Defender (Away) with a handball in the penalty area.'
        result = incident_context(self.shot, c, {})
        self.assertEqual(result['type'], 'handball')
        self.assertIsNone(result['wonBy'])

    def test_wrong_player_and_intervening_attempt_are_rejected(self):
        c = self.commentary()
        c['Events'][0]['Players'][0]['Id'] = 99
        self.assertIsNone(incident_context(self.shot, c, {}))
        c = self.commentary()
        c['Events'].insert(1, {'IncidentCode': 'PSG', 'Elapsed': 90, 'ElapsedPlus': 3})
        self.assertIsNone(incident_context(self.shot, c, {}))

    def test_ambiguous_awards_and_wrong_team_rejected(self):
        c = self.commentary()
        c['Events'].append(deepcopy(c['Events'][-1]))
        self.assertIsNone(incident_context(self.shot, c, {}))
        c = self.commentary()
        c['Events'][-1]['Players'][0]['TeamId'] = 2
        self.assertIsNone(incident_context(self.shot, c, {}))

    def test_reviewed_note_expires_when_source_changes(self):
        c = self.commentary()
        c['Events'] = [c['Events'][0], {'MessageId': 'note', 'Elapsed': 90, 'ElapsedPlus': 2, 'Description': 'Verified incident', 'IncidentCode': 'highlight'}]
        notes = {'100': {'type': 'foul', 'wonBy': 'Winger', 'sentence': 'Verified summary', 'evidence': {'note': 'Verified incident'}}}
        self.assertEqual(incident_context(self.shot, c, notes)['method'], 'reviewed_commentary')
        c['Events'][1]['Description'] = 'Corrected incident'
        self.assertIsNone(incident_context(self.shot, c, notes))

    def test_commentary_must_match_the_fixture(self):
        with self.assertRaisesRegex(ValueError, 'different teams'):
            news.normalize(self.payload, 'https://example.com', '2026-10-21', self.clubs,
                           {'HometeamId': 99, 'AwayteamId': 2, 'Events': []})

    def narrative(self):
        content = {'playerStats': {'7': {'id': 7, 'name': 'Rasmus Højlund', 'teamId': 1,
                    'stats': [{'stats': {'Penalty won': {'key': 'penalties_won', 'stat': {'value': 1}}}}]},
                    '8': {'id': 8, 'name': 'Relja Obrić', 'teamId': 2, 'stats': []}}}
        window = [{'IncidentCode': 'highlight', 'Elapsed': 89, 'MessageId': 'award',
                   'Description': 'PENALTY TO HOME! Hojlund is bundled over inside the area.'}]
        return content, window

    def test_narrative_foul_crosschecks_player_and_unique_team_penalty(self):
        content, window = self.narrative()
        result = narrative_context(self.shot, window, content, [self.shot])
        self.assertEqual(result['wonBy'], 'Rasmus Højlund')
        self.assertIsNone(result['concededBy'])
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot, dict(self.shot, id=101)]))
        content['playerStats']['7']['stats'] = []
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot]))

    def test_narrative_handball_requires_single_opponent_and_rejects_negation(self):
        content, window = self.narrative()
        content['playerStats']['7']['stats'] = []
        window[0]['Description'] = 'PENALTY TO HOME! A raised Obric hand blocked the shot.'
        self.assertEqual(narrative_context(self.shot, window, content, [self.shot])['concededBy'], 'Relja Obrić')
        window[0]['Description'] += ' VAR decides it was not handball. The penalty is overturned.'
        self.assertIsNone(narrative_context(self.shot, window, content, [self.shot]))

    def test_unrelated_earlier_incident_is_not_used(self):
        content, window = self.narrative()
        content['playerStats']['7']['stats'] = []
        content['playerStats']['6'] = {'id': 6, 'name': 'Other Defender', 'teamId': 2, 'stats': []}
        window[0]['Description'] = 'PENALTY TO HOME! A raised Obric hand blocked the shot.'
        window.append({'IncidentCode': 'highlight', 'Elapsed': 85, 'MessageId': 'old',
                       'Description': 'Other Defender sees his handball appeal rejected at the other end.'})
        self.assertEqual(narrative_context(self.shot, window, content, [self.shot])['concededBy'], 'Relja Obrić')

    def test_commentary_outage_keeps_enriched_article_only_for_unchanged_facts(self):
        old = self.run_normalize()[1]
        old[0]['incident'] = {'sentence': 'Verified detail'}
        fresh = self.run_normalize()[1]
        self.assertEqual(news.merge(old, fresh, {'123'}), old)
        fresh[0]['eventHash'] = 'corrected-score'
        self.assertIsNone(news.merge(old, fresh, {'123'})[0]['incident'])

    def test_partial_capture_preserves_unresolved_fixture_and_adds_new_one(self):
        old = self.run_normalize()[1]
        fresh = deepcopy(old)
        fresh[0].update(id='fotmob:456:101', matchId='456')
        merged = news.merge(old, fresh, {'456'})
        self.assertEqual({a['matchId'] for a in merged}, {'123', '456'})


class PublicationGuards(unittest.TestCase):
    def test_promotion_accepts_empty_success_but_rejects_malformed_response(self):
        self.assertEqual(publisher.api_response(''), {})
        self.assertEqual(publisher.api_response('{"deploymentId":"verified"}'), {'deploymentId': 'verified'})
        with self.assertRaises(json.JSONDecodeError):
            publisher.api_response('<html>Authentication required</html>')

    def test_readback_resolves_full_url_for_project_scoped_ci_token(self):
        with patch.object(publisher, 'run', return_value='verified page') as command:
            self.assertEqual(publisher.deployment_page('vercel', 'https://candidate.vercel.app', '/penalty-news/article'), 'verified page')
            command.assert_called_once_with('vercel', 'curl', 'https://candidate.vercel.app/penalty-news/article', '--', '--fail', '--silent')

    def run_guard(self, enabled, outputs):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix='penalty-test-') as tmp:
            root = Path(tmp)
            (root / 'config').mkdir()
            (root / 'config/penalty-news-publication.json').write_text(json.dumps({'enabled': enabled, 'lookbackDays': 8}))
            with patch.object(publisher, 'ROOT', root), patch('sys.argv', ['publish', '--state', str(root / 'evidence')]), patch.object(publisher, 'run', side_effect=outputs) as command:
                publisher.main()
                return command.call_count

    def test_preview_does_not_invoke_capture_git_or_deployment(self):
        self.assertEqual(self.run_guard(False, []), 0)

    def test_dirty_checkout_blocks_publication(self):
        with self.assertRaisesRegex(RuntimeError, 'unrelated tracked changes'):
            self.run_guard(True, [' M src/app/page.tsx'])

    def test_feature_branch_cannot_publish(self):
        with self.assertRaisesRegex(RuntimeError, 'production branch'):
            self.run_guard(True, ['', 'codex/penalty-news-preview-20261021'])


class PublicationLiveTree(unittest.TestCase):
    def test_divergent_source_copies_only_news_onto_live_tree(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp)
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid');git('config','commit.gpgsign','false')
            for path in (publisher.DATA,publisher.CHECKPOINT):(root/path).parent.mkdir(parents=True,exist_ok=True)
            packet={'generatedAt':'2026-10-27T12:00:00Z','articles':[{'id':'a','updatedAt':'2026-10-27T12:00:00Z'}]}
            live_config={'ignoreCommand':'original build guard','git':{'deploymentEnabled':{'main':False}},'headers':[{'source':'/','headers':[]}]}
            (root/'vercel.json').write_text(json.dumps(live_config))
            (root/publisher.DATA).write_text(json.dumps(packet));(root/publisher.CHECKPOINT).write_text('{}');(root/'layout.txt').write_text('base')
            git('add','.');git('commit','-qm','base');base=git('rev-parse','HEAD')
            packet['generatedAt']='2026-10-28T12:00:00Z';packet['articles'].append({'id':'b','updatedAt':'2026-10-28T12:00:00Z'})
            (root/publisher.DATA).write_text(json.dumps(packet));(root/publisher.CHECKPOINT).write_text('{"captured":true}');(root/'layout.txt').write_text('stale source layout')
            git('add','.');git('commit','-qm','source');source=git('rev-parse','HEAD')
            git('checkout','-qb','live',base);(root/'layout.txt').write_text('current live UI');git('add','.');git('commit','-qm','live');live=git('rev-parse','HEAD')
            evidence=root/'evidence';evidence.mkdir()
            with patch.object(publisher,'ROOT',root):tree=publisher.news_tree(live,source,evidence)
            self.assertEqual(git('show',tree+':layout.txt'),'current live UI')
            self.assertEqual(json.loads(git('show',tree+':'+publisher.DATA)),packet)
            self.assertEqual(set(git('diff-tree','--name-only','-r',live+'^{tree}',tree).splitlines()),{publisher.DATA,publisher.CHECKPOINT,'vercel.json'})
            published_config=json.loads(git('show',tree+':vercel.json'))
            self.assertFalse(published_config['git']['deploymentEnabled'].pop(publisher.PUBLICATION_PREFIX+'*'))
            self.assertEqual(published_config,live_config)
            self.assertEqual(git('rev-parse','HEAD'),live)
            self.assertEqual(len(json.loads((root/publisher.DATA).read_text())['articles']),1)
            with patch.object(publisher,'ROOT',root),self.assertRaisesRegex(RuntimeError,'regress'):
                publisher.news_tree(source,live,evidence)

    def run_current_news(self, capture=None):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp);(root/'config').mkdir();(root/'config/penalty-news-publication.json').write_text('{"enabled":true,"lookbackDays":8}')
            (root/publisher.DATA).parent.mkdir(parents=True);(root/publisher.DATA).write_text('{"generatedAt":"same","articles":[]}')
            state=root/'evidence';state.mkdir();(state/'capture-state.json').write_text('{}')
            report = {'matchesChecked': 0, 'matchesExpected': 0, 'errors': [], 'excluded': [], 'articles': 0}
            report.update(capture or {})
            (state/'report.json').write_text(json.dumps(report))
            def command(*args,**kw):
                if args[:2]==('git','status'):return ''
                if args==('git','rev-parse','--abbrev-ref','HEAD'):return publisher.BRANCH
                if args[:2]==('git','diff'):return ''
                if args==('git','rev-parse','HEAD'):return 'divergent-source-sha'
                if len(args)>1 and args[1]=='scripts/build-penalty-news.py':return ''
                if args[:2]==('vercel','api'):
                    if '/aliases/' in args[2]:return '{"deploymentId":"live"}'
                    return '{"id":"live","url":"live.vercel.app","meta":{"githubCommitSha":"different-live-sha"}}'
                if args[:2]==('vercel','curl'):return '<main data-news-version="same">current articles</main>'
                raise AssertionError('Unexpected command '+str(args))
            def api_read(path):
                return json.loads(command('vercel','api',path))
            with patch.object(publisher,'ROOT',root),patch.object(publisher,'run',side_effect=command),patch.object(publisher,'vercel_read',side_effect=api_read),patch.object(publisher.shutil,'which',return_value='vercel'),patch.dict(publisher.os.environ,{'VERCEL_TOKEN':'test-only','GITHUB_STEP_SUMMARY':''}),patch('builtins.print'),patch('sys.argv',['publish','--state',str(state)]):
                publisher.main()
            return json.loads((state/'publication.json').read_text())

    def test_current_news_needs_no_ancestry_check_or_deployment(self):
        self.assertEqual(self.run_current_news()['status'], 'already_current')

    def test_final_data_wait_is_visible_without_failing_or_building(self):
        waiting = [{'matchId': '123', 'pendingSince': '2026-10-28T21:00:00+00:00'}]
        receipt = self.run_current_news({'waitingForFinalData': waiting, 'pendingMatchIds': ['123']})
        self.assertEqual(receipt['status'], 'already_current')
        self.assertEqual(receipt['waitingForFinalData'], waiting)
        self.assertEqual(receipt['pendingMatchIds'], ['123'])

    def test_overdue_or_invalid_data_still_fails_after_publication_check(self):
        for issue in ({'errors': [{'matchId': '123', 'reason': 'Final data overdue'}]},
                      {'excluded': [{'matchId': '123', 'reason': 'Ambiguous penalty'}]}):
            with self.subTest(issue=issue), self.assertRaisesRegex(RuntimeError, 'Capture incomplete'):
                self.run_current_news(issue)


class PostMatchCapture(unittest.TestCase):
    setUp = PenaltyNewsTests.setUp
    run_normalize = PenaltyNewsTests.run_normalize

    def test_wrong_fixture_identity_and_teams_rejected(self):
        expected = {'matchId': '123', 'leagueId': 47, 'homeId': '1', 'awayId': '2', 'kickoff': '2026-10-18T12:00:00Z'}
        news.validate_fixture(self.payload, expected)
        with self.assertRaisesRegex(ValueError, 'identity'):
            news.validate_fixture(self.payload, dict(expected, matchId='456'))
        with self.assertRaisesRegex(ValueError, 'teams'):
            news.validate_fixture(self.payload, dict(expected, homeId='99'))
        with self.assertRaisesRegex(ValueError, 'date'):
            news.validate_fixture(self.payload, dict(expected, kickoff='2026-10-19T12:00:00Z'))

    def test_batch_bounded_and_failed_fixtures_not_lost_outside_window(self):
        records = {str(i): {'status': 'pending', 'inWindow': False} for i in range(20)}
        due, deferred = news.due_matches(records, 'post-match', '2026-10-25T12:00:00+00:00', 16)
        self.assertEqual((len(due), deferred), (16, 4))
        records[due[0]].update(status='verified', verifiedAt='2026-10-25T11:00:00+00:00')
        self.assertNotIn(due[0], news.due_matches(records, 'post-match', '2026-10-25T12:00:00+00:00', 16)[0])

    def test_followup_for_delayed_commentary_and_daily_corrections(self):
        r = {'123': {'status': 'verified', 'followUpDue': '2026-10-25T14:00:00+00:00', 'inWindow': True}}
        self.assertEqual(news.due_matches(r, 'post-match', '2026-10-25T13:00:00+00:00', 16)[0], [])
        self.assertEqual(news.due_matches(r, 'post-match', '2026-10-25T14:00:00+00:00', 16)[0], ['123'])
        self.assertEqual(news.due_matches(r, 'daily', '2026-10-25T13:00:00+00:00', 128)[0], ['123'])

    def test_metadata_alone_never_changes_public_revision(self):
        articles = self.run_normalize()[1]
        previous = news.public_packet({}, articles, 'old-version', '2026-10-18', True, 68)
        self.assertEqual(news.public_packet(previous, articles, 'new-version', '2026-10-25', False, 1), previous)
        changed = deepcopy(articles)
        changed[0]['title'] = 'Source correction'
        self.assertEqual(news.public_packet(previous, changed, 'new-version', '2026-10-25', True, 1)['generatedAt'], 'new-version')

    def capture_fixture(self, root, payload):
        (root / 'data/goalscorer').mkdir(parents=True)
        (root / 'data/goalscorer/team-logo-map.json').write_text(json.dumps({'leagues': {'epl': {'teams': {'Home': {'fotmob_team_id': 1}}}}}))
        evidence = root / 'evidence'
        evidence.mkdir()
        fixture = {'id': 123, 'home': {'id': 1}, 'away': {'id': 2},
                   'status': {'finished': True, 'utcTime': '2026-10-18T12:00:00Z', 'scoreStr': '2 - 1'}}
        news.atomic_write(evidence / 'fixtures-20261018.json', {'leagues': [{'id': 47, 'matches': [fixture]}]})
        news.atomic_write(evidence / 'match-123.json', {'sourceUrl': 'https://www.fotmob.com/matches/example#123', 'observedAt': '2026-10-18T15:00:00Z', 'payload': payload})
        return evidence

    def capture(self, root):
        args = ['build', '--offline', '--allow-partial', '--mode', 'post-match', '--end-date', '2026-10-18', '--days', '1',
                '--output', str(root / 'news.json'), '--checkpoint', str(root / 'state.json'), '--evidence-dir', str(root / 'evidence')]
        with patch.object(news, 'ROOT', root), patch('sys.argv', args):
            news.main()
        return news.read(root / 'evidence/report.json', {})

    def test_second_run_does_not_fetch_completed_match_or_change_article(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root = Path(tmp)
            evidence = self.capture_fixture(root, self.payload)
            self.assertEqual(self.capture(root)['matchesChecked'], 1)
            before = (root / 'news.json').read_bytes()
            (evidence / 'match-123.json').unlink()
            report = self.capture(root)
            self.assertEqual((report['matchesExpected'], report['cachedVerified'], report['errors']), (0, 1, []))
            self.assertEqual((root / 'news.json').read_bytes(), before)

    def test_missing_source_retried_even_after_calendar_window(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root = Path(tmp)
            evidence = self.capture_fixture(root, self.payload)
            packet = (evidence / 'match-123.json').read_bytes()
            (evidence / 'match-123.json').unlink()
            self.assertEqual(self.capture(root)['pendingMatchIds'], ['123'])
            news.atomic_write(evidence / 'fixtures-20261018.json', {'leagues': []})
            (evidence / 'match-123.json').write_bytes(packet)
            report = self.capture(root)
            self.assertEqual((report['matchesChecked'], report['pendingMatchIds'], report['articles']), (1, [], 1))

    def test_no_penalty_matches_are_cached_too(self):
        self.payload['props']['pageProps']['content']['shotmap']['shots'] = []
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root = Path(tmp)
            evidence = self.capture_fixture(root, self.payload)
            self.assertEqual(self.capture(root)['articles'], 0)
            (evidence / 'match-123.json').unlink()
            self.assertEqual(self.capture(root)['matchesExpected'], 0)

    def test_live_detail_waits_then_recovers_penalty_once_without_losing_old_news(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root = Path(tmp)
            old = self.run_normalize()[1]
            previous = news.public_packet({}, old, 'old-version', '2026-10-18', True, 1)
            news.atomic_write(root / 'news.json', previous)
            self.payload['props']['pageProps']['general']['finished'] = False
            self.payload['props']['pageProps']['header']['status']['finished'] = False
            evidence = self.capture_fixture(root, self.payload)
            first = self.capture(root)
            self.assertEqual(first['errors'], [])
            self.assertEqual(first['matchesChecked'], 0)
            self.assertEqual(first['pendingMatchIds'], ['123'])
            self.assertEqual(len(first['waitingForFinalData']), 1)
            self.assertEqual(news.read(root / 'news.json', {}), previous)
            since = first['waitingForFinalData'][0]['pendingSince']
            self.assertEqual(self.capture(root)['waitingForFinalData'][0]['pendingSince'], since)
            packet = news.read(evidence / 'match-123.json', {})
            packet['payload']['props']['pageProps']['general']['finished'] = True
            packet['payload']['props']['pageProps']['header']['status']['finished'] = True
            news.atomic_write(evidence / 'match-123.json', packet)
            recovered = self.capture(root)
            self.assertEqual((recovered['matchesChecked'], recovered['articles']), (1, 1))
            self.assertEqual(recovered['pendingMatchIds'], [])
            self.assertEqual(recovered['waitingForFinalData'], [])
            self.assertNotIn('finalDataPendingSince', news.read(root / 'state.json', {})['matches']['123'])
            self.assertEqual(self.capture(root)['articles'], 1)

    def test_final_data_wait_escalates_after_one_hour_without_resetting_clock(self):
        self.payload['props']['pageProps']['header']['status']['finished'] = False
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root = Path(tmp)
            self.capture_fixture(root, self.payload)
            self.capture(root)
            checkpoint = news.read(root / 'state.json', {})
            since = (news.datetime.now(news.timezone.utc) - news.timedelta(hours=1)).isoformat()
            checkpoint['matches']['123']['finalDataPendingSince'] = since
            news.atomic_write(root / 'state.json', checkpoint)
            report = self.capture(root)
            self.assertEqual(report['waitingForFinalData'], [])
            self.assertEqual(report['pendingMatchIds'], ['123'])
            self.assertEqual(report['errors'][0]['pendingSince'], since)
            self.assertIn('one hour', report['errors'][0]['reason'])

    def test_bad_identity_and_missing_final_evidence_do_not_get_grace(self):
        for problem in ('identity', 'missing_status', 'cancelled', 'missing_shots'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
                root = Path(tmp)
                payload = deepcopy(self.payload)
                page = payload['props']['pageProps']
                if problem == 'identity':
                    page['general'].update(matchId=999, finished=False)
                elif problem == 'missing_status':
                    del page['header']['status']['finished']
                elif problem == 'cancelled':
                    page['header']['status'].update(cancelled=True, finished=False)
                else:
                    del page['content']['shotmap']
                self.capture_fixture(root, payload)
                report = self.capture(root)
                self.assertEqual(len(report['errors']), 1)
                self.assertEqual(report['waitingForFinalData'], [])
                self.assertEqual(report['pendingMatchIds'], ['123'])


if __name__ == "__main__":
    unittest.main()
