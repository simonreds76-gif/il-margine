from unittest import TestCase
from pathlib import Path
from tennis_settlement_identity import verified_names, with_native_aliases


class NativeAlias(TestCase):
    def test_exact_binding_and_collisions(self):
        native=dict(id="29932",name="Taylor Harry Fritz",birthdate="1997-10-28",country="USA")
        row=dict(tour="ATP",native_id="29932",archive_id="126203",native_birthdate="1997-10-28",
                 archive_birthdate="1997-10-28",country="USA",alias="Taylor Harry Fritz",
                 player_name="Taylor Fritz",verified_at="2026-10-30")
        norm=lambda n:str(n or "").lower()
        def resolve(people,aliases):
            return verified_names(people,aliases,"ATP",norm)
        self.assertEqual(resolve([native],[row]),{"taylor fritz":("29932","Taylor Harry Fritz")})
        for change in (dict(native_id="2"),dict(country="GBR"),dict(archive_birthdate="2000-01-01"),
                       dict(tour="WTA"),dict(alias="Fritz"),dict(verified_at="")):
            self.assertEqual(resolve([native],[dict(row,**change)]),{})
        self.assertEqual(resolve([native,dict(native,id="9",name="Taylor Fritz")],[row]),{})

        # The actual game winner is the opponent. Resolve by numeric ID on
        # the loser side; a similarly named unrelated native row stays out.
        n="Taylor Harry Fritz"
        def read(path):
            return [row] if path.name=="player-name-aliases.csv" else [native]
        def pair(a,b):
            return tuple(sorted((norm(a),norm(b))))
        def load(directory,signals):
            self.assertEqual(signals[-1]["player"],n)
            m=dict(winner_name="Opponent",loser_name=n,winner_id="18",loser_id="29932",w_ace="8",l_ace="12")
            return {("ATP",2026,pair(n,"Opponent")):[m,dict(m,loser_id="999")]}
        s=dict(tour="ATP",date="2026-11-06",player="Taylor Fritz",opponent="Opponent")
        idx=with_native_aliases(Path("test/oncourt"),[s],read,norm,pair,load)
        found,=idx["ATP",2026,pair("Taylor Fritz","Opponent")]
        self.assertEqual((found["loser_id"],found["loser_name"],found["l_ace"]),("29932","taylor fritz","12"))
