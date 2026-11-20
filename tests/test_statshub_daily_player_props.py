import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import statshub_daily_board as board

AT="2026-11-20T10:50:00+00:00"
ROW=dict(matchId="a-v-b.123",playerId="person.12",playerName="A Player",teamId="a.1",teamName="Alpha",
         statType="shots",oddsType="over",line=1.5,bestBookmakerName="Book",bestOdds=2.25,
         inPredictedLineup=True,hitRateL15=80,matchup="favours the over",bestOddsAgeMinutes=8)
HIST=dict(span={"teams":["Alpha"]},requestedStat={"statType":"shots","column":"count"},
          matchColumns=["matchId","date","minutes","count"],matchRows=[
              [str(i+1),"2026-10-01",80,2 if i<16 else 0] for i in range(20)])

class Reader:
    limit=40
    def __init__(self,rows=None,history=None):
        self.log=[]; self.rows=rows if rows is not None else [ROW]; self.history=history or HIST
    def read(self,name,args,slot):
        self.log.append((name,args))
        if name=="getFixturesByDate":
            found=args["competitionId"]==board.LEAGUES["Bundesliga"][0]
            data=dict(fixtureCount=int(found),fixturesSummary="- Fri 20:00 Alpha v Beta (id a-v-b.123)" if found else "")
        elif name=="getPropScreener":
            data=dict(data=self.rows)
        elif name=="getMatchOdds":
            data=dict(context="Alpha v Beta · kick-off Fri 20 Nov 2026, 20:00 UTC",markets=[
                dict(name="Double Chance",outcomes=[dict(label="Alpha or Draw",best=dict(odds=3,bookmaker="Book",ageMinutes=1))])])
        elif name=="getPlayerStats": data=self.history
        else: raise AssertionError(name)
        return dict(at=AT,data=data)

class DailyProps(unittest.TestCase):
    def screen(self,reader):
        return board.morning(reader,"2026-11-20",clock=lambda:AT)

    def test_scopes_inputs_and_uses_player_history(self):
        reader=Reader([ROW,dict(ROW,statType="yellowCards"),dict(ROW,line=0.5,bestOdds=1.2)])
        result=self.screen(reader)
        self.assertEqual(len(result["picks"]),1)
        p=result["picks"][0]
        self.assertEqual((p["side"],p["hits"],p["starts"],p["meanMinutes"]),("player",16,20,80))
        query=next(q for name,q in reader.log if name=="getPropScreener")
        self.assertEqual(set(query["statTypes"]),set(board.PLAYER_STATS))
        self.assertEqual(query["oddsFrom"],1.70)

    def test_rejects_team_cheap_unverified_and_unfavourable(self):
        for change in (dict(inPredictedLineup=False,startedLastGame=True),dict(bestOddsAgeMinutes=61),
                       dict(bestOddsAgeMinutes=None),dict(matchup="favours the under"),dict(bestOdds=1.20)):
            with self.subTest(change=change):
                self.assertEqual(self.screen(Reader([dict(ROW,**change)]))["picks"],[])

    def test_club_time_and_unique_fixture_boundaries(self):
        past=HIST["matchRows"][:9]
        for hist in (dict(HIST,span={"teams":["Alpha","Old"]}),
                     dict(HIST,matchRows=past+past+[["future","2026-11-21",90,3]])):
            self.assertEqual(self.screen(Reader(history=hist))["picks"],[])

    def test_competing_lines_for_one_player(self):
        row=dict(id="a",matchId="a.1",player="x.2",odds=2.5,minimum=2.0,ko=AT)
        winner=dict(row,id="b",odds=3.0)
        other=dict(row,id="c",player="p.4")
        self.assertEqual([p["id"] for p in board.distinct_players([row,other,winner])],["b","c"])

    def test_correction_archives_once_and_does_not_resend(self):
        class Store:
            def __init__(self):
                self.data={board.REPORT:dict(pilot=board.START,days={board.START:dict(final=True,delivery="sent",picks=[dict(id="old")])})}
            def get(self,key,default=None): return copy.deepcopy(self.data.get(key,default))
            def put(self,key,value,replace=True):
                if not replace and key in self.data: return False
                self.data[key]=copy.deepcopy(value); return True
        store=Store()
        with patch.object(board,"Store",return_value=store), patch.object(board,"Provider"), patch.object(board,"datetime") as dt, patch.object(board,"morning",return_value=self.screen(Reader([]))), patch.object(board,"send_digest") as send:
            dt.now.return_value=board.utc(AT)
            board.run(); board.run()
            send.assert_called_once()
            self.assertIn("Correction:",send.call_args.args[2][0])
            self.assertIn(board.PLAYER_POLICY,send.call_args.args[1])
            self.assertEqual(store.data[board.REPORT]["days"][board.START]["picks"],[])
            self.assertEqual(store.data["archive/2026-11-20-before-player-counts.json"]["picks"],[dict(id="old")])
