import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lab_highlight_portraits as m

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def page(tid, players):
    data = {'props': {'pageProps': {'fallback': {f'team-{tid}': {
        'details': {'id': tid}, 'squad': {'squad': [{'title': 'Attackers', 'members': players}]}}}}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'


class Response:
    def __init__(self, url, text='', image=True):
        self.url = url; self.text = text
        self.headers = {'Content-Type': 'image/png' if image else 'text/html'}
    def raise_for_status(self):
        pass
    def close(self):
        pass


class Session:
    def __init__(self, pages):
        self.pages = pages; self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        if '/playerimages/' in url:
            return Response(url)
        tid = int(url.split('/teams/')[1].split('/')[0])
        value = self.pages[tid]
        if isinstance(value, Exception):
            raise value
        return Response(url, value, False)


class PortraitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clubs = {'Atalanta': 8524, 'Bologna': 9857, 'Frosinone': 9891}
        self.rows = [dict(id=str(i), league='serie-a', team=club, player=name, best_odds=3.2,
                         fair_odds=2.1, date='2026-11-08', player_id='12008', player_photo_url=None)
                     for i, (club, name) in enumerate(zip(self.clubs, ['Nikola Krstovic', 'Tommaso Pobega', 'Antonio Raimondo']))]
        self.write('team-logo-map.json', {'leagues': {'serie-a': {'teams': {
            name: {'fotmob_team_id': tid} for name, tid in self.clubs.items()}}}})
        self.pages = {8524: page(8524, [{'id': 833638, 'name': 'Nikola Krstović'}]),
                      9857: page(9857, [{'id': 790732, 'name': 'Tommaso Pobega'}]),
                      9891: page(9891, [{'id': 1256534, 'name': 'Antonio Raimondo'}])}
    def write(self, name, value):
        (self.root/name).write_text(json.dumps(value))
    def test_three_real_identity_shapes_and_all_nonphoto_fields_preserved(self):
        before=json.dumps(self.rows,sort_keys=True); session=Session(self.pages)
        out, report=m.enrich(self.rows,self.root,session=session,now=NOW)
        self.assertEqual([r['player_photo_url'] for r in out], [m.PHOTO.format(i) for i in [833638,790732,1256534]])
        for old,new in zip(self.rows,out):
            self.assertEqual({k:v for k,v in old.items() if k!='player_photo_url'}, {k:v for k,v in new.items() if k!='player_photo_url'})
        self.assertEqual(json.dumps(self.rows,sort_keys=True),before)
        self.assertEqual(report['with_photo'],3)
        self.assertTrue(all('12008.png' not in c for c in session.calls))
    def test_next_poll_reuses_verified_identity_without_requests(self):
        m.enrich(self.rows,self.root,session=Session(self.pages),now=NOW)
        session=Session({}); out,_=m.enrich(self.rows,self.root,session=session,now=NOW+timedelta(minutes=30))
        self.assertEqual(session.calls,[]); self.assertTrue(all(r['player_photo_url'] for r in out))
    def test_one_failed_club_does_not_block_other_players_and_retry_is_bounded(self):
        self.pages[8524]=m.requests.Timeout()
        out,report=m.enrich(self.rows,self.root,session=Session(self.pages),now=NOW)
        self.assertIsNone(out[0]['player_photo_url']); self.assertEqual(report['with_photo'],2)
        s=Session({}); m.enrich(self.rows,self.root,session=s,now=NOW+timedelta(minutes=30));self.assertEqual(s.calls,[])
        s=Session(self.pages);m.enrich(self.rows,self.root,session=s,now=NOW+timedelta(hours=7));self.assertEqual(len(s.calls),1)
    def test_ambiguous_full_name_is_not_guessed(self):
        self.pages[8524]=page(8524,[{'id':1,'name':'Nikola Krstovic'},{'id':2,'name':'Nikola Krstović'}])
        out,report=m.enrich(self.rows,self.root,session=Session(self.pages),now=NOW)
        self.assertIsNone(out[0]['player_photo_url']); self.assertEqual(report['missing'][0]['reason'],'player_missing_or_ambiguous')
    def test_wrong_club_payload_is_rejected(self):
        self.pages[8524]=page(99,[{'id':833638,'name':'Nikola Krstovic'}])
        out,report=m.enrich(self.rows,self.root,session=Session(self.pages),now=NOW)
        self.assertIsNone(out[0]['player_photo_url']); self.assertEqual(report['with_photo'],2)
    def test_existing_valid_photo_never_depends_on_club_or_opponent(self):
        self.rows[0]['player_photo_url']=m.PHOTO.format(833638); self.rows[0]['team']='Unknown'
        s=Session({});out,report=m.enrich(self.rows[:1],self.root,session=s,now=NOW)
        self.assertEqual(out,self.rows[:1]);self.assertEqual(s.calls,[])
    def test_verified_catalogue_is_shared_without_a_squad_request(self):
        self.write('penalty-player-portraits.json',{'antonioraimondo':'1256534'})
        s=Session({});out,_=m.enrich(self.rows[2:],self.root,session=s,now=NOW)
        self.assertEqual(out[0]['player_photo_url'],m.PHOTO.format(1256534));self.assertEqual(len(s.calls),1)
    def test_malformed_squad_only_holds_its_own_photo(self):
        self.pages[8524]='<script id="__NEXT_DATA__">[]</script>'
        _,report=m.enrich(self.rows,self.root,session=Session(self.pages),now=NOW)
        self.assertEqual(report['with_photo'],2)
    def test_surname_and_coach_are_not_player_identities(self):
        with self.assertRaises(ValueError):m.exact_squad_player(self.pages[8524],8524,'Krstovic')
        with self.assertRaises(ValueError):m.exact_squad_player(self.pages[8524],8524,'Nikola Other')
    def test_unbounded_input_still_has_at_most_six_image_checks(self):
        rows=[{**self.rows[0],'id':str(i),'player':f'Player {i}'} for i in range(20)]
        self.write('penalty-player-portraits.json',{m.key(r['player']):str(100+i) for i,r in enumerate(rows)})
        s=Session({});_,report=m.enrich(rows,self.root,session=s,now=NOW)
        self.assertEqual(len(s.calls),6);self.assertEqual(report['with_photo'],6)


if __name__ == '__main__':
    unittest.main()
