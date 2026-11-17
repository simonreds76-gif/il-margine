import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import goalkeeper_half_adjustment as half
from goalkeeper_forecast_evidence import archive, source_hashes
from goalkeeper_saves_live import predict_mean, price_side


class ForwardPaper(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.folder=self.root/"inputs"
        self.at=datetime(2026,11,20,14,tzinfo=UTC)
        self.kick=(self.at+timedelta(hours=2)).isoformat()
        self.source=self.root/"source"
        self.source.write_text("private fixture test")
        self.params=dict(features=list("abcdefghi"),centers=[0]*9,scales=[1]*9,beta=[.2]+[0]*9,
                         alpha=.12,fallback_mean=3.,league_venue_means={"epl|home":3.,"epl|away":3.})
        self.enterContext(patch.object(half,"PARAM_HASH",half.digest(self.params)))
        self.results={}
        self.enterContext(patch.object(half,"targets",side_effect=lambda *a:(self.results,{})))
        lu=dict(observed_at=self.at.isoformat(),fotmob_match_id=300,home_fotmob_team_id=1,away_fotmob_team_id=2,
                home_starters=[dict(name="Keeper H",role_group="GK",player_id=10)],
                away_starters=[dict(name="Keeper A",role_group="GK",player_id=20)])
        self.rows=[]
        for venue,name,odds in (("home","Keeper H",2.9),("away","Keeper A",1.9)):
            q=dict(bookmaker="Fixture Book",player=name,captured_at=self.at.isoformat(),kickoff_at=self.kick,
                   line=3.5,odds_decimal=odds,side="over",event_id="123",source="fixture")
            mu=predict_mean(self.params,[0]*9,"epl",venue)
            p=price_side("over",3.5,odds,mu,.12)
            eligible=p["edge"]>=.05
            self.rows.append(dict(**q,_research_quote=q,_research_features=[0]*9,_research_lineup=lu,model_mean=mu,
                model_probability=p["model_probability"],candidate_status="eligible_shadow" if eligible else "no_value",
                strongest_for_fixture="yes" if eligible else "no",lineup_status="confirmed_starter",goalkeeper=name,
                contract_scope="named_player",venue=venue,home_team="H",away_team="A",league="epl",blockers=""))

    def capture(self,rows=None,at=None):
        at=at or self.at
        result=archive(self.folder, self.rows if rows is None else rows,self.params,source_hashes([self.source]),now=at)
        return half.run(self.root,[self.folder/"packets"/(k+".json") for k in result["accepted_packets"]],at)

    def test_lock_settle_repeat_and_flag_correction(self):
        report=self.capture()
        self.assertEqual(report["fixtures"],1)
        self.assertEqual(report["arms"]["current"]["pending"],1)
        self.assertEqual(self.capture()["fixtures"],1)
        self.results["300"]=dict(source_hash="verified",full_match_agreement=True,kickoff=self.kick,league="epl",
                                keepers=[dict(player_id=i,team_id=t,started=True,minutes=90,saves=s,event_saves=s)
                                         for i,t,s in ((10,1,5),(20,2,1))])
        settled=half.run(self.root,[],self.at+timedelta(days=1))
        self.assertEqual(settled["paired_settled_fixtures"],1)
        for a in half.ARMS:
            arm=settled["arms"][a]
            self.assertEqual(arm["n"],2)
            self.assertGreater(arm["log_loss"],0)
            if arm["settled"]:
                self.assertAlmostEqual(arm["roi_pct"],190)
        self.assertEqual(half.run(self.root,[],self.at+timedelta(days=1))["arms"],settled["arms"])
        self.results["300"]["keepers"][0].update(saves=3,event_saves=3)
        self.assertEqual(half.run(self.root,[],self.at+timedelta(days=2))["holds"],{"changed_verified_result":1})

    def test_stale_team_scope_wrong_price_and_source_are_excluded(self):
        for changes in ({"contract_scope":"team_goalkeeper_home"},{"odds_decimal":1.5}):
            rows=copy.deepcopy(self.rows)
            rows[0].update(changes)
            self.assertEqual(self.capture(rows)["fixtures"],0)
        self.assertEqual(self.capture(at=self.at+timedelta(minutes=11))["fixtures"],0)
        rows=copy.deepcopy(self.rows)
        for r in rows:
            r["bookmaker"]=r["_research_quote"]["bookmaker"]="Bet365"
        self.assertEqual(self.capture(rows)["fixtures"],0)

    def test_no_bet_contributes_zero_stake(self):
        rows=copy.deepcopy(self.rows)
        for r in rows:
            r["odds_decimal"]=r["_research_quote"]["odds_decimal"]=1.5
            r.update(candidate_status="value_ladder",strongest_for_fixture="no")
        report=self.capture(rows)
        for a in half.ARMS:
            self.assertEqual(report["arms"][a]["no_bets"],1)
            self.assertIsNone(report["arms"][a]["roi_pct"])
