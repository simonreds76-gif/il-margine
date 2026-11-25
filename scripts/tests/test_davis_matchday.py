import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import davis_matchday as d

DAY = "2026-11-25"
NOW = datetime.fromisoformat(DAY+"T14:05:00+00:00")
# Synthetic pairings. These are parser tests, never published nominees.
ROSTER = {("Adam One","Italy"),("Ben Two","Italy"),("Cory Three","Korea, Rep."),("Dan Four","Korea, Rep."),("Dave Four","Korea, Rep.")}
ROWS = [(["Adam One","Cory Three"],["st-scheduled"]),(["Ben Two","Dan Four"],["st-scheduled"])]
REFERENCE = [("Three C.","One A."),("Two B.","Four Dan")]


class DavisTests(unittest.TestCase):
    def test_names_order_and_preannouncement(self):
        ties, _ = d.make_programme(ROWS,ROSTER,REFERENCE,DAY,NOW)
        self.assertEqual(ties[0]["singles"],[r[0] for r in ROWS])
        self.assertEqual(ties[0]["teams"],["Italy","Korea, Rep."])
        self.assertEqual(ties[0]["session"],DAY+"T15:00:00Z")
        self.assertFalse(d.make_programme(ROWS,ROSTER,REFERENCE,DAY,NOW.replace(hour=13))[0])

    def test_disagreement_ambiguity_and_cancelled(self):
        self.assertFalse(d.make_programme(ROWS,ROSTER,[],DAY,NOW)[0])
        self.assertFalse(d.make_programme(ROWS,ROSTER,[REFERENCE[0],("Two B.","Four D.")],DAY,NOW)[0])
        self.assertFalse(d.make_programme(ROWS[:1],ROSTER,REFERENCE,DAY,NOW)[0])
        ambiguous = [ROWS[0], (["Two B.","Four D."],["st-scheduled"])]
        self.assertFalse(d.make_programme(ambiguous,ROSTER,REFERENCE,DAY,NOW)[0])
        cancelled = [ROWS[0], (ROWS[1][0],["st-cancelled"])]
        self.assertEqual(d.make_programme(cancelled,ROSTER,REFERENCE,DAY,NOW)[1],{"Italy","Korea, Rep."})

    def test_price_free_day_and_singles_filters(self):
        def row(a,b,date=DAY):
            return f'<li class="mr st-scheduled"><a class="mr-a" href="/partita/fixture-{date}-id"></a><div class="mr-p"><div class="pl"><a class="pn">{a}</a></div><div class="pl"><a class="pn">{b}</a></div></div></li>'
        page = BeautifulSoup(f'<title>Davis Cup</title><section aria-labelledby="oop-h"><div id="u-{DAY}"><ol class="ml">'+row("One A.","Three C.")+row("A/B","C/D")+row("Old","Other","2026-11-24")+'</ol></div></section>',"html.parser")
        self.assertEqual(d.order_rows(page,DAY),[ (["One A.","Three C."],["mr","st-scheduled"]) ])
        self.assertEqual(d.order_rows(page,"2026-11-26"),[])

    def test_previous_results_only_between_ties(self):
        title = "<title>Davis Cup - World Group</title>"
        results = '<section aria-labelledby="res-h"><a href="/partita/earlier-rubber">Result</a></section>'
        self.assertEqual(d.order_rows(BeautifulSoup(title+results, "html.parser"), DAY), [])
        for html in (title, title+results+'<div class="st-scheduled"></div>', "<title>Unavailable</title>"+results):
            with self.assertRaises(ValueError):
                d.order_rows(BeautifulSoup(html,"html.parser"), DAY)

    def test_public_verification_needs_both_cards_and_order(self):
        ties,_=d.make_programme(ROWS,ROSTER,REFERENCE,DAY,NOW)
        html=BeautifulSoup('<section aria-label="Davis Cup">'+''.join(f'<div data-singles-order="{i}"><button>'+''.join(f'<span class="x__name">{n}</span>' for n in names)+'</button></div>' for i,(names,_) in enumerate(ROWS,1))+'</section>',"html.parser")
        fixtures=[{"programme":{"order":i},"sides":[{"name":n} for n in names]} for i,(names,_) in enumerate(ROWS,1)]
        with patch.object(d,"fetch",return_value=html),patch.object(d.requests,"get") as get,patch.object(d,"homepage_cards",return_value=set()):
            get.return_value.json.return_value={"tennis":{"fixtures":fixtures}}
            receipt=d.public_check(ties)
            self.assertEqual((receipt["matchday"],receipt["homeFeed"],receipt["homeCards"]),(2,2,0))
            self.assertFalse(receipt["verified"])

