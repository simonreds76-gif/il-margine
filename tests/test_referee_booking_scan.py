from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import referee_booking_scan as watch


class Memory:
    def __init__(self):
        self.rows = {}

    def get(self, key, default=None):
        return self.rows.get(key, default)

    def put(self, key, value, replace=True):
        if key in self.rows and not replace:
            return False
        self.rows[key] = value
        return True


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(watch.UTC)
        ko = (self.now + timedelta(hours=3)).replace(second=0, microsecond=0)
        self.game = dict(home="Home", away="Away", id="fixture.abc", league="Serie A", core=True, ko=ko.isoformat())
        self.player = dict(id="p.123", player="Test Player", team="Home", side="home", lineup="predicted",
                           fouls=20,apps=10,minutes=800,perGame=2,per90=2.25)
    def report(self):
        fixture = dict(self.game, status="reviewed", referee="Example", players=[self.player],
                       refSample=dict(games=20,yellows=80,mean=4,first="2026-01-01",last="2026-11-20",capped=False))
        return dict(day=str(self.now.astimezone(watch.UK).date()),preview=False,fixtures=[fixture],calendarGaps=[],reads=1)

    def test_foul_leaders_are_returned_without_any_odds_or_booking_reads(self):
        data = {"matches":{"id":self.game["id"],"status":"scheduled",
                           "kickoffTimestamp":int(datetime.fromisoformat(self.game["ko"]).timestamp())},
                "homeTeam":{"id":"home","name":"Home"},"awayTeam":{"id":"away","name":"Away"},
                "referees":{"id":"ref","name":"Example"}}
        reader = Mock()
        reader.read.return_value = {"data":data}
        with patch.object(watch,"rank_players",return_value=([self.player],20)) as rank:
            result = watch.analyse(reader,self.game,self.now,{"ref":{"games":20,"mean":4}})
            self.assertEqual(result,"reviewed")
            self.assertEqual(self.game["players"],[self.player])
            rank.assert_called_once()
            reader.read.assert_called_once_with("getMatchDetails",matchId=self.game["id"])
            self.assertEqual(watch.analyse(reader,self.game,self.now,{"ref":{"games":20,"mean":3.99}}),
                             "below referee threshold")
            self.assertEqual(rank.call_count,1)

    def test_dated_referee_history(self):
        reader = Mock()
        def fake(name, refereeId, recentGames):
            n=recentGames
            first="2025-09-01" if n>33 else "2026-01-01"
            return {"profile":{"data":{"id":"ref.abc"}},"record":{"recentGames":{
                "context":f"{first} to 2026-11-10", "totals":{"games":n,"yellowCards":n*4}}}}
        reader.read.side_effect=fake
        result=watch.referee_sample(reader,{"id":"ref.abc"},date(2026,11,27))
        self.assertEqual((result["games"],result["yellows"]),(33,132))
        self.assertLessEqual(reader.read.call_count,7)

    def test_recent_future_result_rejected(self):
        reader=Mock()
        reader.read.return_value={"profile":{"data":{"id":"ref"}},"record":{"recentGames":{
            "context":"2026-01-01 to 2026-11-30","totals":{"games":50,"yellowCards":200}}}}
        with self.assertRaises(watch.Missing):
            watch.referee_sample(reader,{"id":"ref"},date(2026,11,27))

    def test_core_duplicate_and_reserves(self):
        reader=Mock()
        def fake(name, **args):
            if name=="getFixturesByDate":
                if args["date"]=="2026-11-28" and args["competitionId"]==watch.LEAGUES["Serie A"][0]:
                    return {"fixturesSummary":"- 14:00 Home v Away (id fixture.abc)", "fixtureCount":1}
                return {"fixturesSummary":"","fixtureCount":0}
            return {"pagination":{"page":1,"hasNextPage":False},"data":[
                {"nextMatchId":f"alt.{i}","nextGame":f"{game} (Cup), Sat 28 Nov 2026, 14:00 UTC"}
                for i,game in [("abc","Home v Away"),("xyz","Club v Town"),("bad","Club U20 v Town U20")]]}
        reader.read.side_effect=fake
        rows,gaps=watch.discover(reader,*watch.edition_window(date(2026,11,28)))
        self.assertFalse(gaps)
        self.assertEqual([r["core"] for r in rows],[True,False])
        self.assertEqual([r["away"] for r in rows],["Away","Town"])

    def test_rank_both_elevens_before_accessing_any_prices(self):
        reader=Mock()
        teams={s: {"id":s,"name":s.title()} for s in ("home","away")}
        xi={s:{"teamId":s,"status":"predicted","players":[{"id":f"{s}{i}"} for i in range(11)]} for s in teams}
        def fake(name, **args):
            if name=="getLineups":
                return {"lineups":{"available":True,"matchId":self.game["id"],**xi}}
            self.assertEqual(name,"getTopStatLeaders")
            self.assertEqual(args["stat"],"fouls")
            side=args["teamId"]
            return {"filtersApplied":args,"data":[{"playerId":f"{side}{i}","teamId":side,"playerName":f"P{i}",
                    "minutesPlayed":360,"appearances":4,"statValue":i+(1 if side=="away" else 0)} for i in (1,2,3,15)]}
        reader.read.side_effect=fake
        players,count=watch.rank_players(reader,self.game,{"competition":{"stageId":"stage"},"matches":{"seasonId":"s"}},teams)
        self.assertEqual(count,6)
        self.assertEqual([p["id"] for p in players],["away3","away2","home3"])
        self.assertEqual(reader.read.call_count,3)

    def test_short_caption_full_attachment_expiry_and_unfinished(self):
        report=self.report()
        ps=report["fixtures"][0]["players"]
        for i in range(1,5):
            ps.append(dict(ps[0],id=str(i),player=f"Runner {i}",perGame=10-i))
        report["fixtures"].append(dict(self.game,status="no assigned referee"))
        caption,body,n=watch.digest(report,self.now)
        self.assertEqual(n,5)
        self.assertEqual(caption.count(" fouls in "),3)
        self.assertIn("Runner 1",caption)
        self.assertNotIn("Runner 4",caption)
        self.assertNotIn("odds",body.lower())
        self.assertIn("Runner 4",body)
        self.assertIn("1 incomplete",caption)
        self.assertLess(len(caption.encode("utf-16-le"))//2,1024)
        self.assertEqual(watch.digest(report,self.now+timedelta(hours=4))[2],0)

    def test_save_then_deliver_once(self):
        report=self.report()
        store=Memory()
        with patch.object(watch,"telegram_private",return_value=("https://example.invalid","1")), patch.object(watch.http,"post") as post:
            post.return_value.json.return_value={"ok":True,"result":{"message_id":123}}
            watch.deliver(store,report,self.now)
            watch.deliver(store,report,self.now)
            post.assert_called_once()
            self.assertIn("document",post.call_args.kwargs["files"])

    def test_no_resend_on_uncertain_delivery(self):
        report=self.report()
        store=Memory()
        with patch.object(watch,"telegram_private",return_value=("https://example.invalid","1")), patch.object(watch.http,"post",side_effect=TimeoutError) as post:
            with self.assertRaises(TimeoutError):
                watch.deliver(store,report,self.now)
            with self.assertRaises(RuntimeError):
                watch.deliver(store,report,self.now)
            post.assert_called_once()

    def test_isolated_missing_fixture_and_budget(self):
        rows=[dict(self.game,id=i) for i in ("a","b")]
        reader=Mock(calls=2)
        with patch.object(watch,"discover",return_value=(rows,[])), patch.object(watch,"analyse",side_effect=[watch.Missing("missing XI"),"reviewed"]):
            result=watch.screen(reader,date.today())
        self.assertEqual([r["status"] for r in result["fixtures"]],["missing XI","reviewed"])
        with self.assertRaises(watch.Missing):
            watch.Reads(Mock(),max_reads=0).read("unused")

    def test_local_09_tracks_summer_clock(self):
        self.assertEqual(watch.edition_window(date(2026,7,1))[0].hour,8)
        self.assertEqual(watch.edition_window(date(2026,11,28))[0].hour,9)


if __name__=="__main__":
    unittest.main()
