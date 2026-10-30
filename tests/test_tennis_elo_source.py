import copy,json,tempfile,unittest,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tennis_elo_source as S

NOW=datetime(2026,10,30,12,tzinfo=timezone.utc)
def html(day='2026-10-26',value='1800.1',name='Test Player'):
    return f'''<html><body>Last update: {day}<table id="reportable"><tr><th>Elo Rank</th><th>Player</th><th>Elo</th><th>hElo</th><th>cElo</th><th>gElo</th></tr><tr><td>1</td><td><a href="/cgi-bin/player.cgi?p=TestPlayer">{name}</a></td><td>{value}</td><td>1700.1</td><td>1600.2</td><td>-</td></tr></table></body></html>'''.encode()

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.out=self.root/'research'
        for name,body in {
            'data/oncourt/players_atp.csv':'id,name,birthdate,country\n1,Test Player,1990-01-02,GBR\n',
            'data/sackmann/atp_players.csv':'player_id,name_first,name_last,dob,ioc\n9,Test,Player,19900102,GBR\n',
            'data/tennis-props/player-name-aliases.csv':'tour,alias,player_name\n',
        }.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
        self.calls=0
    def fetch(self,tour):self.calls+=1;return html()
    def collect(self,day=NOW,fetcher=None,**kwargs):
        return S.collect(self.root,self.out,'ATP',now=day,fetcher=fetcher or self.fetch,minimum=1,**kwargs)
    def test_typed_surface_and_no_fake_grass(self):
        p=S.parse(html(),'ATP',NOW.isoformat(),1)['records'][0]
        self.assertEqual(p['overall'],1800.1);self.assertEqual(p['surface_blended']['Hard'],1700.1)
        self.assertIsNone(p['surface_blended']['Grass']);self.assertNotIn('raw_surface',p)
    def test_future_stale_malformed_dates(self):
        for day in ['2026-11-01','2026-10-01','bad']:
            with self.subTest(day=day),self.assertRaises(ValueError):S.parse(html(day),'ATP',NOW.isoformat(),1)
    def test_invalid_rating(self):
        for value in ['nan','inf','0','-1','4000','oops','']:
            with self.subTest(value=value),self.assertRaises(ValueError):S.parse(html(value=value),'ATP',NOW.isoformat(),1)
    def test_truncation(self):
        with self.assertRaisesRegex(ValueError,'truncated'):S.parse(html()[:-20],'ATP',NOW.isoformat(),1)
    def test_column_drift(self):
        with self.assertRaisesRegex(ValueError,'schema'):S.parse(html().replace(b'hElo',b'hElo Rank'),'ATP',NOW.isoformat(),1)
    def test_duplicate_source_name(self):
        raw=html();row=raw[raw.index(b'<tr><td>1'):raw.index(b'</table>')]
        row=row.replace(b'<td>1</td>',b'<td>2</td>').replace(b'p=TestPlayer',b'p=Other')
        records=S.parse(raw.replace(b'</table>',row+b'</table>'),'ATP',NOW.isoformat(),1)['records']
        mapped,gaps,_=S.identities(self.root,'ATP',records)
        self.assertEqual(mapped,[]);self.assertEqual([g['reason'] for g in gaps],['source_name_homonym']*2)
    def test_duplicate_profile_still_fails(self):
        raw=html();row=raw[raw.index(b'<tr><td>1'):raw.index(b'</table>')].replace(b'<td>1</td>',b'<td>2</td>')
        with self.assertRaisesRegex(ValueError,'duplicate'):S.parse(raw.replace(b'</table>',row+b'</table>'),'ATP',NOW.isoformat(),1)
    def test_partial_row(self):
        with self.assertRaisesRegex(ValueError,'partial'):S.parse(html().replace(b'<td>-</td>',b''),'ATP',NOW.isoformat(),1)
    def test_noncontiguous_ranks(self):
        with self.assertRaisesRegex(ValueError,'ranks'):S.parse(html().replace(b'<td>1</td>',b'<td>2</td>'),'ATP',NOW.isoformat(),1)
    def test_daily_idempotency_and_snapshot_stability(self):
        first=self.collect();contents={p:p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        second=self.collect();self.assertEqual(self.calls,1);self.assertIn('skipped',second)
        self.assertEqual(first['last_good'],second['last_good'])
        self.assertEqual(contents,{p:p.read_bytes() for p in self.out.rglob('*') if p.is_file()})
    def test_unchanged_source_preserves_first_observation(self):
        a=self.collect();b=self.collect(NOW+timedelta(days=1))
        self.assertEqual(a['last_good'],b['last_good']);self.assertTrue(b['unchanged'])
    def test_failed_request_keeps_last_good_and_no_retry_loop(self):
        a=self.collect()
        def fail(t):raise OSError('network unavailable')
        b=self.collect(NOW+timedelta(days=1),fail)
        self.assertEqual(b['state'],'FAILED');self.assertEqual(a['last_good'],b['last_good'])
        self.assertIn('skipped',self.collect(NOW+timedelta(days=1)))
    def test_stale_page_does_not_replace_validated(self):
        a=self.collect();b=self.collect(NOW+timedelta(days=1),lambda t:html('2026-09-01'))
        self.assertEqual(b['state'],'FAILED');self.assertEqual(a['last_good'],b['last_good'])
    def test_no_future_snapshot_or_stale_read(self):
        self.collect()
        with self.assertRaisesRegex(ValueError,'not_available'):S.snapshot_current(self.out/'atp',NOW-timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError,'stale'):S.snapshot_current(self.out/'atp',NOW+timedelta(days=20))
    def test_integrity_read(self):
        a=self.collect();p=self.out/'atp'/a['last_good']['snapshot'];p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash'):S.snapshot_current(self.out/'atp',NOW)
    def test_no_surname_or_initial_guess(self):
        r=S.parse(html(name='T Player'),'ATP',NOW.isoformat(),1)
        mapped,gaps,_=S.identities(self.root,'ATP',r['records']);self.assertFalse(mapped);self.assertEqual(len(gaps),1)
    def test_birthdate_conflict(self):
        p=self.root/'data/sackmann/atp_players.csv';p.write_text(p.read_text().replace('19900102','19900103'))
        b=self.collect();self.assertEqual(b['state'],'FAILED');self.assertEqual(b['reason'],'no_verified_identity_mapping')
    def test_name_collision_is_not_first_wins(self):
        p=self.root/'data/oncourt/players_atp.csv';p.write_text(p.read_text()+'2,Test Player,1990-01-02,GBR\n')
        b=self.collect();self.assertEqual(b['state'],'FAILED')
    def test_duplicate_archive_ids_are_retained_not_history_merged(self):
        p=self.root/'data/sackmann/atp_players.csv';p.write_text(p.read_text()+'10,Test,Player,19900102,GBR\n')
        self.collect();data=S.snapshot_current(self.out/'atp',NOW)
        self.assertEqual(data['players'][0]['sackmann_ids'],[9,10])
    def test_incomplete_duplicate_is_not_merged_or_a_contradiction(self):
        p=self.root/'data/sackmann/atp_players.csv';p.write_text(p.read_text()+'10,Test,Player,,GBR\n')
        self.collect();data=S.snapshot_current(self.out/'atp',NOW)
        self.assertEqual(data['players'][0]['sackmann_ids'],[9])
        self.assertEqual(data['players'][0]['unverified_archive_ids'],[10])
    def test_duplicate_known_conflict_stays_quarantined(self):
        p=self.root/'data/sackmann/atp_players.csv';p.write_text(p.read_text()+'10,Test,Player,19900103,GBR\n')
        self.assertEqual(self.collect()['state'],'FAILED')
    def test_revalidate_rejects_tampered_prior_snapshot(self):
        a=self.collect();(self.out/'atp'/a['last_good']['snapshot']).write_text('{}')
        self.assertEqual(self.collect(revalidate_local=True)['reason'],'prior_snapshot_integrity_failed')
    def test_interrupted_process_retains_last_good_and_attempt_reservation(self):
        a=self.collect();status=self.out/'atp/status.json'
        S.atomic(status,{**a,'state':'RUNNING'})
        b=S.mark_interrupted(self.out,'ATP')
        self.assertEqual(b['state'],'FAILED');self.assertEqual(a['last_good'],b['last_good'])
        self.assertIn('skipped',self.collect());self.assertEqual(self.calls,1)
        self.assertEqual(self.collect(NOW+timedelta(days=1))['state'],'VALIDATED')
    def test_interruption_does_not_overwrite_success(self):
        a=self.collect();self.assertEqual(S.mark_interrupted(self.out,'ATP'),a)
    def test_revalidation_changes_only_forward_mapping_snapshot(self):
        a=self.collect();old=(self.out/'atp'/a['last_good']['snapshot']).read_bytes()
        p=self.root/'data/tennis-props/player-name-aliases.csv';p.write_text(p.read_text()+'ATP,Other Name,Test Player\n')
        b=self.collect(NOW+timedelta(minutes=1),revalidate_local=True)
        self.assertNotEqual(a['last_good']['snapshot'],b['last_good']['snapshot']);self.assertEqual(self.calls,1)
        self.assertEqual(old,(self.out/'atp'/a['last_good']['snapshot']).read_bytes())
        self.assertGreater(b['last_good']['observed_at'],a['last_good']['observed_at'])
    def test_os_lock_rejects_second_process_scope(self):
        with S.lock(self.out/'atp'):
            with self.assertRaises(OSError):
                with S.lock(self.out/'atp'):pass
            self.assertEqual(self.collect()['reason'],'collector_locked')
            self.assertEqual(S.mark_interrupted(self.out,'ATP')['reason'],'collector_locked')
    def test_alias_direction_does_not_block_verified_full_names(self):
        p=self.root/'data/oncourt/players_atp.csv';p.write_text(p.read_text().replace('Test Player','Test Longname Player'))
        a=self.root/'data/tennis-props/player-name-aliases.csv'
        records=S.parse(html(),'ATP',NOW.isoformat(),1)['records']
        for line in ['ATP,Test Longname Player,Test Player','ATP,Test Player,Test Longname Player']:
            a.write_text('tour,alias,player_name\n'+line+'\n')
            mapped,gaps,_=S.identities(self.root,'ATP',records)
            self.assertEqual(len(mapped),1);self.assertFalse(gaps)
    def test_two_source_names_claiming_native_quarantines_both(self):
        a=self.root/'data/tennis-props/player-name-aliases.csv';a.write_text(a.read_text()+'ATP,Other Name,Test Player\n')
        p=self.root/'data/sackmann/atp_players.csv';p.write_text(p.read_text()+'10,Other,Name,19900102,GBR\n')
        records=S.parse(html(),'ATP',NOW.isoformat(),1)['records']
        records.append({**records[0],'name':'Other Name','source_player_key':'OtherName'})
        mapped,gaps,_=S.identities(self.root,'ATP',records)
        self.assertFalse(mapped);self.assertEqual([g['reason'] for g in gaps],['native_id_claimed_twice']*2)

if __name__=='__main__':unittest.main(verbosity=2)
