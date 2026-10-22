import importlib.util
from pathlib import Path
import unittest
import tempfile
import subprocess

spec=importlib.util.spec_from_file_location('sync',Path(__file__).parents[1]/'sync-pinnacle-corners.py')
sync=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
HEADER='captured_at,league,match_date,kickoff_iso,home_team,away_team,line,side,odds_decimal,odds_american\n'
def row(hour,price='2.0'):
    return f'2026-10-23T{hour}:00:00Z,epl,2026-10-24,2026-10-24T15:00:00Z,A,B,9.5,over,{price},100\n'

class CaptureSyncTests(unittest.TestCase):
    def test_divergent_appends_and_duplicates_are_preserved_once(self):
        base=HEADER+row('08')
        merged=sync.union_csv(base,base+row('09'),base+row('10')+row('09'))
        self.assertEqual(merged,base+row('10')+row('09'))
    def test_conflicting_same_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            sync.union_csv(HEADER,HEADER+row('09'),HEADER+row('09','3.0'))
    def test_rewrites_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'rewrite/deletion'):
            sync.union_csv(HEADER+row('08'),HEADER,HEADER+row('08'))
    def test_different_headers_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'schemas'):
            sync.union_csv(HEADER,HEADER.replace('side,','SIDE,'),HEADER)

    def test_real_git_divergence_preserves_both_captures_and_remote_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            remote=root/'remote.git'; local=root/'local'; peer=root/'peer'
            def run(*args,cwd=root):
                return subprocess.check_output(['git',*args],cwd=cwd,stderr=subprocess.STDOUT).decode().strip()
            run('init','--bare',str(remote));run('clone',str(remote),str(local))
            for repo in [local]:
                run('config','user.name','test',cwd=repo);run('config','user.email','test@example.invalid',cwd=repo)
            run('checkout','-b',sync.BRANCH,cwd=local)
            target=local/sync.CAPTURE;target.parent.mkdir(parents=True);target.write_text(HEADER+row('08'))
            run('add','.',cwd=local);run('commit','-m','base',cwd=local);run('push','origin',sync.BRANCH,cwd=local)
            run('clone','-b',sync.BRANCH,str(remote),str(peer))
            run('config','user.name','test',cwd=peer);run('config','user.email','test@example.invalid',cwd=peer)
            target.write_text(HEADER+row('08')+row('09'))
            run('add','.',cwd=local);run('commit','-m','local evidence',cwd=local)
            (peer/sync.CAPTURE).write_text(HEADER+row('08')+row('10'))
            (peer/'remote.txt').write_text('remote code stays')
            run('add','.',cwd=peer);run('commit','-m','remote evidence and code',cwd=peer);run('push','origin',sync.BRANCH,cwd=peer)
            sync.sync(local)
            self.assertEqual(target.read_text(),HEADER+row('08')+row('10')+row('09'))
            self.assertEqual((local/'remote.txt').read_text(),'remote code stays')
            self.assertEqual(run('status','--porcelain',cwd=local),'')
            run('push','origin',sync.BRANCH,cwd=local)
            sync.sync(local)
            self.assertEqual(target.read_text().count(row('09')),1)

if __name__=='__main__':unittest.main()
