import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

import tennis_df_surface_paper as paper
from df_surface_reporting import pair_proof, summarize, weekly


def table(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0])
        w.writeheader()
        w.writerows(rows)


class PaperTest(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.folder=self.root/paper.REL
        self.folder.mkdir(parents=True)
        self.source=self.root/"data/oncourt"
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.start=self.now+timedelta(days=1)
        day=self.start.date().isoformat()
        self.reg={"start":(self.now-timedelta(seconds=1)).isoformat()}
        self.cfg=paper.TREND["read_json"](paper.ROOT/"config/tennis-props-rate-trend-prospective-v1.json",{})
        self.q=dict(tour="ATP",event_id="eventA",bookmaker="Exchange example",market="double_faults",
                    player="First Player",opponent="Second Player",date=day,tournament="Paris",surface="Hard",
                    line="3.5",over_odds="1.01",under_odds="1.01",scope="player",match_source="exact",
                    capture_ts=self.now.isoformat(),match_start_utc=self.start.isoformat(),raw_market_name="Player Double Faults",
                    matched_board="yes",history_fingerprint="fixture-test",projection_mean="3.0",
                    distribution="negative_binomial",fair_p_over=".35",fair_p_under=".65",fair_p_push="0")
        b=dict(tour="ATP",date=day,tournament="Paris",player=self.q["player"],opponent=self.q["opponent"],
               generation_date=self.now.date().isoformat(),history_as_of=self.now.date().isoformat(),
               history_fingerprint="fixture-test",player_id="1",opponent_id="2",tour_id="11",surface="Hard",projected_dfs="3.0")
        table(self.root/"data/tennis-props/player-props-board.csv",[b])
        table(self.source/"today_atp.csv",[dict(tour_id="11",date=day,player1_id="1",player2_id="2",round_id="5",result="",complete="",live="")])
        table(self.source/"players_atp.csv",[dict(id=str(i),name=n) for i,n in [(1,self.q["player"]),(2,self.q["opponent"])]])
        table(self.source/"courts.csv",[dict(id="1",name="I.hard"),dict(id="2",name="Clay")])
        table(self.source/"tours_atp.csv",[dict(id=str(i),court_id="1" if i%2 else "2",name="Paris",rank="2") for i in range(1,12)])
        self.games=[]; self.stats=[]
        for i in range(10):
            g=dict(winner_id="1",loser_id=str(i+3),tour_id=str(i+1),round_id="4",
                   result="6-4 6-4",date=(self.now.date()-timedelta(days=i+1)).isoformat())
            s=dict(winner_id=g["winner_id"],loser_id=g["loser_id"],tour_id=g["tour_id"],round_id="4",
                   w_df="3",w_w2sof="39",w_fs="66",w_svpt="105",l_df="1",l_w2sof="32",l_fs="55",l_svpt="87")
            self.games.append(g); self.stats.append(s)
        self.raw=self.folder/"raw.csv"; self.cmp=self.folder/"comparison.csv"; self.records=[]
        table(self.source/"games_atp.csv",self.games)
        table(self.source/"stat_atp.csv",self.stats)

    def capture(self,rows,quotes=None):
        raws=[dict(r,df_pair_evidence=pair_proof(r)) for r in rows]
        table(self.raw,raws)
        table(self.cmp,quotes or rows)
        return paper.capture(self.root,self.folder,self.records,self.raw,self.cmp,self.now,self.reg,self.cfg,lambda:self.now)

    def test_fresh_pairs_no_bets_and_dedupe(self):
        first=self.capture([self.q])
        self.assertEqual(first["added"],1,first)
        r=self.records[0]
        self.assertTrue(all(r["arms"][arm]["side"] is None for arm in ("weighted","astra","control")))
        self.assertEqual(r["support"],"weighted")
        self.assertEqual(r["odds"],{"OVER":1.01,"UNDER":1.01})
        moved=dict(self.q,event_id="relisted",over_odds="2.30")
        result=self.capture([moved])
        self.assertEqual(result["reasons"]["duplicate"],1)
        self.assertEqual(paper.TREND["ledger"](self.folder/"observations.jsonl"),self.records)

    def test_prices_and_line_checks(self):
        for q,why in [(dict(self.q,under_odds=""),"no_valid_two_sided_odds"),
                      (dict(self.q,match_start_utc=self.now.isoformat()),"outside_forward_prematch_window")]:
            self.assertEqual(self.capture([q])["reasons"][why],1)
        stale=dict(self.q,capture_ts=(self.now-timedelta(minutes=11)).isoformat())
        self.reg["start"]=(self.now-timedelta(days=1)).isoformat()
        self.assertEqual(self.capture([stale])["reasons"]["stale_odds"],1)
        self.assertEqual(self.capture([self.q],[dict(self.q,line="4.5")])["reasons"]["raw_pair_missing"],1)
        self.assertEqual(self.capture([self.q],[dict(self.q,under_odds="2")])["reasons"]["conflicting_pair"],1)
        self.assertFalse(paper.original_pair(dict(self.q,df_pair_evidence="")))
        self.assertFalse(paper.original_pair(dict(self.q,under_odds="2",df_pair_evidence=pair_proof(self.q))))
        self.assertEqual(len(self.records),0)

    def test_graded_pass_exact_player_and_report(self):
        pick=dict(self.q,line="2",over_odds="4.00",fair_p_over=".6",fair_p_under=".2",fair_p_push=".2")
        self.assertEqual(self.capture([self.q,pick])["added"],2)
        key=dict(winner_id="2",loser_id="1",tour_id="11",round_id="5")
        game=dict(key,result="6-3 6-4",date=self.start.date().isoformat())
        stat=dict(self.stats[0],**key,l_df="2")
        table(self.source/"games_atp.csv",self.games+[game])
        table(self.source/"stat_atp.csv",self.stats+[dict(stat,round_id="4")])
        later=self.start+timedelta(days=1)
        grades={}
        paper.settle(self.source,self.records,grades,later)
        self.assertFalse(grades)
        table(self.source/"stat_atp.csv",self.stats+[stat])
        paper.settle(self.source,self.records,grades,later)
        self.assertEqual([v["actual"] for v in grades.values()],[2,2])
        r=summarize(self.records,grades,{},later)
        self.assertEqual(r["arms"]["control"]["scored"],1)
        self.assertEqual(r["arms"]["control"]["passes"],1)
        self.assertEqual(r["arms"]["control"]["pushes"],1)
        self.assertEqual(r["arms"]["control"]["roi_pct"],0.0)
        self.assertIn("fixture log loss",weekly(r))
        frozen=dict(grades)
        paper.settle(self.source,self.records,grades,later+timedelta(days=1))
        self.assertEqual(grades,frozen)

    def test_native_walkover(self):
        self.capture([self.q])
        table(self.source/"nonplayed-results_atp.csv",[dict(winner_id="1",loser_id="2",tour_id="11",round_id="5",
              result="W/O",date=self.start.date().isoformat(),date_source="match",status="walkover")])
        grades={}
        paper.settle(self.source,self.records,grades,self.start+timedelta(days=1))
        self.assertEqual(grades[self.records[0]["id"]]["status"],"void")
