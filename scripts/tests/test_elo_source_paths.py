from pathlib import Path, PureWindowsPath, PurePosixPath
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tennis_elo_rebuild as E
class PortableEloSources(unittest.TestCase):
 def test_same_relative_source_key_on_both_platforms(self):
  for cls,base in [(PureWindowsPath,'D:/runtime'),(PurePosixPath,'/runtime')]:
   root=cls(base)
   with patch.object(E,'sha',return_value='same'):
    self.assertEqual(E.source_manifest(root,[root/'data/oncourt/games_atp.csv']),{'data/oncourt/games_atp.csv':'same'})
 def test_changed_file_hash_still_rejected(self):
  root=PureWindowsPath('D:/runtime');path=root/'data/oncourt/games_atp.csv'
  with patch.object(E,'sha',return_value='old'):old=E.source_manifest(root,[path])
  with patch.object(E,'sha',return_value='new'):new=E.source_manifest(root,[path])
  self.assertNotEqual(old,new)
if __name__=='__main__':unittest.main()
