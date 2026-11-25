from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import johnny_cards as job
import johnny_cards_edition as edition

DAY = "2026-11-25"
STAMP = DAY + "T10:45:00+00:00"
SEND = DAY + "T10:55:00+00:00"
CAL = [{"league":"morning edition","gap":""}]


class Memory:
    def __init__(self):
        self.data = {edition.REPORT: {"days":{"older":{"policy":"older"}}}}

    def get(self, key, default=None):
        return deepcopy(self.data.get(key, default))

    def put(self, key, value, replace=True):
        if not replace and key in self.data:
            return False
        self.data[key] = deepcopy(value)
        return True


def fixture():
    old = dict(kind="booking",line=0.5,odds=4.5,book="Bet365",rules="verified")
    foul = dict(old,kind="fouls",line=1.5,odds=2.2)
    case = dict(name="Alex Example",player={"id":"alex.42","name":"A. Example","position":"LB"},side="home",
                lineup="predicted",verdict="WATCH",foulsVerdict="WATCH",booking=old,offers=[old,foul],
                bookingRange={"low":0.25,"evLow":0.125},foulsRange={"low":0.48,"evLow":0.056})
    return dict(id="test.11",ko=DAY+"T20:00:00+00:00",home="Home",away="Away",league="Test",
                competitionId="league.3",teams={"home":{"id":"home.4"},"away":{"id":"away.5"}},
                verdictAt=DAY+"T10:00:00Z",reviewState="complete",cases=[case],
                assessment={"cases":[{"index":0,"booking":"BET","fouls":"BET","foulLine":"1.5"}]})


def provider(f, lineup="confirmed", foul_line=1.5, card_price=4.5):
    def market(name, line, price):
        return {"name":name,"outcomes":[{"label":f"Alex Example Over {line}","books":1,
                         "best":{"odds":price,"ageMinutes":3,"bookmaker":"Bet365"}}]}
    reads = {
        "getMatchDetails":{"data":{"matches":{"id":f["id"],"status":"scheduled",
             "kickoffTimestamp":int(job.utc(f["ko"]).timestamp())},"competition":{"competitionId":f["competitionId"]},
             "homeTeam":f["teams"]["home"],"awayTeam":f["teams"]["away"]}},
        "getLineups":{"lineups":{"matchId":f["id"],"home":{"teamId":"home.4","status":lineup,
                    "players":[f["cases"][0]["player"]]}}},
        "getMatchOdds":{"context":"Home v Away · kick-off 25 Nov 2026, 20:00 UTC",
             "markets":[market("Player To Be Booked",0.5,card_price),market("Player Fouls",foul_line,2.2)]},
    }
    r = Mock()
    r.read.side_effect = lambda name,args,slot: {"at":STAMP,"data":reads[name]}
    return r


class EditionTests(unittest.TestCase):
    def test_new_lineup_and_exact_odds_are_required_for_each_market(self):
        f = fixture()
        def check(**args):
            return edition.recheck(provider(f,**args),f,job.utc(STAMP))["picks"]
        self.assertEqual([(q["kind"],q["line"]) for q in check()],[("booking",0.5),("fouls",1.5)])
        self.assertEqual([(q["kind"],q["lineup"]) for q in check(lineup="predicted")],
                         [("booking","predicted"),("fouls","predicted")])
        self.assertTrue(all(q["lineup"]=="confirmed" for q in check()))
        self.assertEqual(check(lineup="squad"),[])
        self.assertEqual(check(foul_line=2.5,card_price=3.9),[])
        f["cases"][0]["rival"] = {"id":"not-in-xi"}
        self.assertEqual(check(),[])

    def test_each_verdict_survives_interruption_and_resume(self):
        first, second = fixture(), dict(fixture(),id="test.12")
        s = Memory()
        reader = Mock(log=[], errors=0)
        analyst = Mock(digest="hash")
        analyst.select_fixtures.side_effect = lambda rows:list(reversed(rows))
        def investigate(reader,f,*_):
            if f["id"] == first["id"]:
                raise RuntimeError("runner interrupted")
            f["screened"] = [{"name":"completed"}]
        def save(doc):
            s.put("snapshot",doc)
        with patch.object(job,"calendar",return_value=([first,second],CAL)), patch.object(job,"triage",side_effect=lambda r,f:f), patch.object(job,"investigate",side_effect=investigate):
            with self.assertRaisesRegex(RuntimeError,"runner interrupted"):
                job.scan(reader,DAY,analyst,lambda:STAMP,save=save)
        snap = s.get("snapshot")
        self.assertEqual([f["reviewState"] for f in snap["slate"]],["selected","complete"])
        self.assertEqual(snap["slate"][1]["verdictAt"],STAMP)
        with patch.object(job,"investigate",side_effect=lambda r,f,*_:f.update(screened=[{}])) as run:
            job.scan(reader,DAY,analyst,lambda:STAMP,save=save,previous=snap)
            self.assertEqual(run.call_count,1)
        self.assertEqual(analyst.select_fixtures.call_count,1)
        self.assertEqual(s.get("snapshot")["stage"],"finished")

    def test_once_only_partial_digest_and_later_completed_fixture(self):
        f = fixture()
        s = Memory()
        now = job.utc(STAMP)
        checks = {f["id"]:edition.recheck(provider(f),f,now)}
        waiting = dict(f,id="pending",home="Unfinished FC",reviewState="selected")
        path = edition.edition_key(DAY,"research")
        s.put(path,{"calendar":CAL,"slate":[f,waiting]})
        s.put(edition.edition_key(DAY,"checks"),checks)
        def send(store,key,parts):
            store.put("receipts/"+key+"-0.json",{"state":"sent","message_id":11})
        with patch.object(edition,"send_digest",side_effect=send) as telegram:
            edition.deliver(s,DAY,lambda:SEND)
            s.put(path,{"calendar":CAL,"slate":[f]})
            edition.deliver(s,DAY,lambda:SEND)
            self.assertEqual(telegram.call_count,1)
        doc=s.get(edition.edition_key(DAY,"digest"))
        self.assertEqual(len(doc["picks"]),2)
        self.assertIn("over 1.5 fouls @ 2.2",doc["message"])
        self.assertIn("to be booked @ 4.5",doc["message"])
        self.assertIn("Unfinished (1) · Unfinished FC v Away",doc["message"])
        self.assertIn("older",s.get(edition.REPORT)["days"])
        self.assertFalse(s.get(edition.REPORT)["days"][DAY]["final"])

    def test_sender_does_not_need_a_running_research_worker_or_a_provider(self):
        f = fixture()
        self.assertIn("Fixture list unavailable",edition.make_digest(DAY,{}, {},job.utc(SEND))["message"])
        doc = edition.make_digest(DAY,{"calendar":CAL,"slate":[f]}, {},job.utc(SEND))
        self.assertEqual(doc["picks"],[])
        self.assertIn("final check outstanding",doc["message"])
        chk=edition.recheck(provider(f),f,job.utc(STAMP))
        for q in chk["picks"]:
            q["age"]=58
        doc=edition.make_digest(DAY,{"calendar":CAL,"slate":[f]},{f["id"]:chk},job.utc(SEND))
        self.assertEqual(doc["picks"],[])
        self.assertIn("odds expired",doc["message"])
        f["ko"]=DAY+"T10:54:00Z"
        self.assertFalse(edition.make_digest(DAY,{"calendar":CAL,"slate":[f]},{f["id"]:chk},job.utc(SEND))["picks"])
