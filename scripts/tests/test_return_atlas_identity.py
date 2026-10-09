import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('identity', Path(__file__).parents[1] / 'return_atlas_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class IdentityTests(unittest.TestCase):
    def test_reviewed_players_keep_published_ids(self):
        self.assertEqual(identity.source_player_id('14507', '45197'), 'oc-45197')
        self.assertEqual(identity.source_player_id('60351', '97973'), 'oc-97973')

    def test_older_archive_preserves_existing_profile_ids(self):
        for source, oncourt in identity.PUBLISHED_ALIASES.items():
            self.assertEqual(identity.source_player_id(source, oncourt), "oc-" + oncourt)
            with self.assertRaises(ValueError):
                identity.source_player_id(source, "wrong-person")

    def test_different_person_is_rejected(self):
        with self.assertRaises(ValueError):
            identity.source_player_id('14507', '97973')

    def test_other_source_ids_are_unchanged(self):
        self.assertEqual(identity.source_player_id('7890', '123'), 'vbt-7890')


if __name__ == '__main__':
    unittest.main()
