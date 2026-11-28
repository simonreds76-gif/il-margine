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

    def test_full_referee_pass_precedes_players_and_below_cutoff_is_skipped(self):
        data = {"matches":{"id":self.game["id"],"status":"scheduled",
                           "kickoffTimestamp":int(datetime.fromisoformat(self.game["ko"]).timestamp())},
                "homeTeam":{"id":"home","name":"Home"},"awayTeam":{"id":"away","name":"Away"},
                "referees":{"id":"ref","name":"Example"}}
        events=[]
        class Api:
            def read(_, name, args):
                events.append(name)
                if name=="getMatchDetails":
                    return {"data":data}
                if name=="getReferee":
                    rid=args["refereeId"]
                    return {"profile":{"data":{"id":rid}},"record":{"recentGames":{
                        "context":f"{self.now.date()} to {self.now.date()}",
                        "totals":{"games":20,"yellowCards":80 if rid=="ref" else 79}}}}
                raise AssertionError(name)
        rows=[dict(self.game,appointment={"id":"ref","name":"Example"}),
              dict(self.game,id="fixture.b",appointment={"id":"below","name":"Other"})]
        with patch.object(watch,"discover",return_value=(rows,[])), patch.object(watch,"check_cards"), patch.object(watch,"rank_players",return_value=([self.player],20)) as rank:
            result=watch.screen(watch.Reads(Api()),self.now.date())
        self.assertEqual(events,["getReferee","getReferee","getMatchDetails"])
        self.assertEqual([f["status"] for f in result["fixtures"]],["reviewed","below referee threshold"])
        rank.assert_called_once()

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
        self.assertLessEqual(reader.read.call_count,8)

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
        reader=Mock()
        reader.read.side_effect=[watch.Missing("temporary failure"),{"fixtureCount":1,"fixturesSummary":"- 15:00 Home v Away (id fixture.ok)"}]
        rows=watch.league_calendar(reader,"Premier League","league.E0",self.now.date())
        self.assertEqual(rows[0]["id"],"fixture.ok")
        self.assertIn("startOfDay",reader.read.call_args.kwargs)
        with self.assertRaises(watch.Missing):
            watch.Reads(Mock(),max_reads=0).read("unused")

    def test_local_09_tracks_summer_clock(self):
        self.assertEqual(watch.edition_window(date(2026,7,1))[0].hour,8)
        self.assertEqual(watch.edition_window(date(2026,11,28))[0].hour,9)

    def test_value_distinguishes_booking_frequency_from_yellow_total(self):
        rec=dict(games=20,booked=1,cards=2,starts=14,bookedStarts=1)
        self.assertEqual(watch.assess_card(rec,{"odds":5}),"record below or level with odds")
        self.assertEqual(watch.assess_card(dict(rec,booked=10,bookedStarts=7),{"odds":4}),"possible value")
        self.assertEqual(watch.assess_card(rec,None),"incomplete")

    def test_card_markets_match_player_fixture_side_and_line(self):
        raw=dict(matchId=self.game["id"],playerId=self.player["id"],teamName="Home",playerName="Test Player",
                 statType="yellowCards",oddsType="over",line=0.5,bestOdds=4,bestBookmakerName="Book")
        reader=Mock()
        reader.read.return_value={"data":[dict(raw,line=1.5,bestOdds=9),dict(raw,matchId="wrong",bestOdds=14),
                dict(raw,teamName="Away",bestOdds=10),dict(raw,oddsType="under",bestOdds=11),raw],
                "pagination":{"currentPage":1,"hasNextPage":False}}
        values=watch.booking_odds(reader,[(self.game,self.player)])
        self.assertEqual(values[("abc","123")]["odds"],4)
        self.assertFalse(reader.read.call_args.kwargs["includeStale"])

    def test_uncertain_save_uses_readback_before_retry(self):
        store=Mock()
        store.put.side_effect=watch.requests.ReadTimeout()
        store.get.return_value={"saved":"here"}
        self.assertTrue(watch.save_report(store,"test",{"saved":"here"}))
        self.assertEqual(store.put.call_count,1)

    def test_recovery_edits_original_only_when_shortlist_changes(self):
        old=self.report()
        store=Memory()
        new=dict(old,screenVersion=2)
        p=new["fixtures"][0]["players"][0]
        p.update(cards=dict(games=20,booked=1,cards=1,perAppearance=.05,starts=17,bookedStarts=1),
                 cardPrice=dict(odds=4,book="Book"),cardAssessment="record below or level with odds")
        folder=f"{watch.PREFIX}/{old['day']}"
        store.put(folder+"/original.json",old)
        store.put(folder+"/delivery.json",dict(state="sent",at=self.now.isoformat(),message_id=123))
        with patch.object(watch,"telegram_private",return_value=("https://example.invalid","1")), patch.object(watch.http,"post") as post:
            post.return_value.json.return_value={"ok":True,"result":{"message_id":123,"chat":{"id":1}}}
            watch.deliver(store,new,self.now)
            watch.deliver(store,new,self.now)
            self.assertEqual(post.call_count,1)
            self.assertTrue(post.call_args.args[0].endswith("/editMessageMedia"))


if __name__=="__main__":
    unittest.main()
