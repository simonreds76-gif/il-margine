from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import johnny_cards as job
import johnny_cards_edition as edition
from johnny_cards_recovery import retryable
from test_johnny_cards_edition import fixture, provider, STAMP, CAL, DAY
import johnny_cards_recovery as recovery
from test_johnny_cards_edition import Memory

class ExpectedTeams(unittest.TestCase):
    def test_missing_response_is_different_from_no_expected_eleven(self):
        reader=Mock()
        f=fixture()
        reader.read.return_value=None
        self.assertEqual(job.starting_cases(reader,f),([], "lineup lookup failed"))
        reader.read.return_value={"data":{"lineups":{"matchId":f["id"],"available":False}}}
        self.assertEqual(job.starting_cases(reader,f),([], "no expected or confirmed XI published"))

    def test_mixed_confirmations_and_new_bench_or_opponent(self):
        f=fixture()
        case=f["cases"][0]
        xi=provider(f).read("getLineups",{},"")["data"]["lineups"]
        case["rival"]={"id":"opponent.18","name":"Rival","position":"RW"}
        xi["away"]={"status":"predicted","teamId":"away.5","players":[case["rival"]]}
        self.assertEqual(edition.starting_role(f,case,xi),("confirmed","predicted"))
        xi["away"]["players"]=[dict(case["rival"],id="different.10")]
        self.assertFalse(edition.starting_role(f,case,xi))
        xi["home"]["players"]=[]
        self.assertFalse(edition.starting_role(f,case,xi))

    def test_expected_starter_visible_on_both_outputs(self):
        f=fixture()
        checks={f["id"]:edition.recheck(provider(f,lineup="predicted"),f,job.utc(STAMP))}
        doc=edition.make_digest(DAY,dict(slate=[f],calendar=CAL),checks,job.utc(STAMP))
        for key in ("coverage","message"):
            self.assertEqual(doc[key].count("expected starter"),2)

    def test_repair_edits_one_message_and_preserves_original_edition(self):
        store=Memory()
        f=fixture()
        pending=dict(f,id="pending.2",home="Unfinished FC",reviewState="selected")
        store.put(job.edition_key(DAY,"lineup-repair-research"),dict(day=DAY,stage="ranked",slate=[f,pending],calendar=CAL,guideSHA256=recovery.Analyst.digest))
        store.put(job.edition_key(DAY,"lineup-repair-checks"),{f["id"]:edition.recheck(provider(f,lineup="predicted"),f,job.utc(STAMP))})
        store.put(job.edition_key(DAY,"digest"),{"day":DAY,"message":"original"})
        store.data[edition.REPORT]["days"][DAY]={"policy":"johnny-bookings"}
        with patch.object(recovery,"require_edition",return_value={"message_id":11}), patch.object(recovery,"timestamp",return_value=STAMP), patch.object(recovery,"telegram_private",return_value=("https://example.invalid","private")), patch.object(recovery.http,"post") as post:
            post.return_value.ok=True
            post.return_value.json.return_value={"ok":True,"result":{"message_id":11}}
            for _ in range(2):
                recovery.amend(store,DAY)
            self.assertTrue(all(c.args[0].endswith("/editMessageText") and c.kwargs["json"]["message_id"]==11 for c in post.call_args_list))
            self.assertEqual(post.call_count,1)
        self.assertEqual(store.get(job.edition_key(DAY,"digest"))["message"],"original")
        self.assertIn("expected starter",store.get(edition.REPORT)["days"][DAY]["coverage"])
        self.assertIn("Unfinished FC",store.get(edition.REPORT)["days"][DAY]["coverage"])

    def test_only_repair_upcoming_selected_lineup_gaps(self):
        f=dict(fixture(),priority=2,reviewState="unavailable",gap="starting elevens unavailable")
        self.assertTrue(retryable(f,job.utc(STAMP)))
        self.assertTrue(retryable(dict(f,reviewState="unfinished",playerScreen={"selected":[]}),job.utc(STAMP)))
        for edit in (dict(reviewState="complete"),dict(priority=None),dict(gap="no prices"),dict(ko=STAMP)):
            self.assertFalse(retryable(dict(f,**edit),job.utc(STAMP)))

    def test_admin_propagation_polls_without_republishing_or_sending(self):
        draft={"coverage":"new coverage", "complete":False}
        old={"days":{DAY:{"coverage":"old coverage","final":False}}}
        new={"days":{DAY:{"coverage":"new coverage","final":False}}}
        store=Mock()
        store.get.side_effect=[old]*5+[new]
        with patch.object(recovery,"sleep") as wait, patch.object(recovery,"telegram_private") as telegram:
            recovery.verify_published_coverage(store, DAY, draft)
        self.assertGreater(sum(c.args[0] for c in wait.call_args_list), 15)
        store.put.assert_not_called()
        telegram.assert_not_called()
        store.get.side_effect=None
        store.get.return_value=old
        with patch.object(recovery,"sleep"), self.assertRaisesRegex(RuntimeError,"readback still differs"):
            recovery.verify_published_coverage(store, DAY, draft)

    def test_expired_session_renews_once_and_does_not_retry_quota(self):
        api=job.JohnnyProvider(Mock())
        api.headers={"session":"active"}
        with patch.object(job.Provider,"read",side_effect=[job.RemoteError(401),{"ok":True}]) as read:
            self.assertTrue(api.read("getLineups",{})["ok"])
            self.assertEqual(read.call_count,2)
        api.headers={"session":"active"}
        with patch.object(job.Provider,"read",side_effect=job.RemoteError(429)) as read:
            with self.assertRaises(job.RemoteError):
                api.read("getLineups",{})
            self.assertEqual(read.call_count,1)
