import json, tempfile, unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refresh_matchday_portraits import exact_player, refresh, recover, valid_image, PLACEHOLDERS

class PortraitTests(unittest.TestCase):
    def test_exact_identity_and_duplicates(self):
        a={'FirstName':'Hikaru','LastName':'Shiraishi','PlayerId':'S0C2'}
        b={**a,'FirstName':'Shozo','PlayerId':'S123'}
        self.assertEqual(exact_player('Hikaru Shiraishi',[a,b]),a)
        self.assertIsNone(exact_player('Shiraishi',[a,b]))
        self.assertIsNone(exact_player('Hikaru Shiraishi',[a,a]))
    def test_reviewed_alias_only(self):
        p={'FirstName':'Tai','LastName':'Sach','PlayerId':'S0U5'}
        self.assertEqual(exact_player('Tai Leonard Sach',[p]),p)
        self.assertIsNone(exact_player('T. Sach',[p]))
    def test_placeholder_html_and_tiny_images_rejected(self):
        self.assertFalse(valid_image(b'<html>'+b'x'*10000,'text/html',set()))
        self.assertFalse(valid_image(b'\x89PNG\r\n\x1a\n'+b'x'*4700,'image/png',set()))
    def test_wimbledon_fallback_is_verified(self):
        def fetch(url):
            if 'byname' in url:return json.dumps([{'FirstName':'Hikaru','LastName':'Shiraishi','PlayerId':'S0C2','PlayerHeadshotUrl':'https://www.atptour.com/-/media/alias/player-headshot/S0C2'}]).encode(),'application/json'
            return (b'\x89PNG\r\n\x1a\n'+b'x'*(9000 if 'wimbledon' in url else 4700),'image/png')
        row,status=recover('Hikaru Shiraishi',PLACEHOLDERS,fetch)
        self.assertIn('wimbledon',row['src']);self.assertEqual(status['status'],'verified')
    def test_a_failed_player_does_not_block_other_players(self):
        def fetch(url):
            if '/bad/' in url:raise TimeoutError()
            if 'byname' in url:return json.dumps([{'FirstName':'Test','LastName':'Good','PlayerId':'G123','PlayerHeadshotUrl':'https://www.atptour.com/-/media/alias/player-headshot/G123'}]).encode(),'application/json'
            return b'\x89PNG\r\n\x1a\n'+b'x'*9000,'image/png'
        with tempfile.TemporaryDirectory() as tmp:
            photos,a=refresh([{'player1_name':'Test Bad','player2_name':'Test Good'}],[],{},Path(tmp)/'cache.json',fetch=fetch)
            self.assertIn('test good',photos);self.assertEqual(a['missing'][0]['name'],'Test Bad')
    def test_previous_photos_and_overrides_survive_without_network(self):
        old={'known player':{'name':'Known Player','src':'/known.jpg'}}
        override={'name':'Hikaru Shiraishi','src':'/hikaru.jpg'}
        def fail(url):raise AssertionError('No lookup expected')
        with tempfile.TemporaryDirectory() as tmp:
            photos,a=refresh([{'player1_name':'Known Player','player2_name':'Hikaru Shiraishi'}],[],old,Path(tmp)/'cache.json',[override],fetch=fail)
            self.assertEqual(a['attempted'],0);self.assertEqual(a['covered'],2);self.assertEqual(photos['known player'],old['known player'])
            self.assertNotIn('hikaru shiraishi',old)
    def test_limit_and_cooldown_prevent_repeated_polling(self):
        rows=[{'player1_name':'Test '+str(i),'player2_name':'Existing Player'} for i in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'cache.json'
            def fail(url):raise TimeoutError()
            _,a=refresh(rows,[{'name':'Existing Player','src':'/x.jpg'}],{},cache,max_players=2,fetch=fail)
            self.assertEqual(a['attempted'],2);self.assertEqual(a['queued'],2)
            _,b=refresh(rows,[{'name':'Existing Player','src':'/x.jpg'}],{},cache,max_players=2,fetch=fail)
            self.assertEqual(b['attempted'],2)
            _,c=refresh(rows,[{'name':'Existing Player','src':'/x.jpg'}],{},cache,max_players=2,fetch=fail)
            self.assertEqual(c['attempted'],0)


    def test_prepare_repeated_catalogue_is_unchanged_and_bad_config_retains_it(self):
        from refresh_matchday_portraits import prepare, CATALOGUE, catalogue_is_live
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); checkout=root/'checkout'; candidate=root/'candidate'
            prior=[{'name':'Known Player','src':'/known.jpg'}]
            target=checkout/CATALOGUE;target.parent.mkdir(parents=True);target.write_text(json.dumps(prior))
            legacy=checkout/'src/data/tip-tennis-portraits.json';legacy.parent.mkdir(parents=True);legacy.write_text('[]')
            override=root/'overrides.json';override.write_text('[]')
            a=prepare(checkout,candidate,[{'player1_name':'Known Player'}],override,max_players=0)
            self.assertFalse(a['changed']);self.assertEqual(a['covered'],1)
            self.assertEqual(json.loads((candidate/'release'/CATALOGUE).read_text()),prior)
            override.write_text('bad json')
            b=prepare(checkout,candidate,[],override,max_players=0)
            self.assertEqual(b['status'],'last_good_retained');self.assertFalse(b['changed'])
            self.assertTrue(catalogue_is_live(checkout,'https://example.invalid',lambda *a,**k:json.dumps(prior).encode()))
            self.assertFalse(catalogue_is_live(checkout,'https://example.invalid',lambda *a,**k:b'[]'))

if __name__=='__main__':unittest.main()
