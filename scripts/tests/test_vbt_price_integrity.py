import copy
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from h2h_historical_prices import paired_prices
from vbt_price_integrity import corrections, reviewed_price, suspicious_close


class PriceIntegrityTests(unittest.TestCase):
    def test_extreme_unverified_move_is_held_without_inventing_a_price(self):
        row = dict(cote1_ouverture='6', cote2_ouverture='1.153',
                   cote1_cloture='1.012', cote2_cloture='49.35')
        self.assertTrue(suspicious_close(row))
        self.assertEqual(paired_prices(row), (None, None))
        # A legitimately short opening favourite is not rejected for being short.
        row.update(cote1_ouverture='1.03', cote2_ouverture='25')
        self.assertFalse(suspicious_close(row))
        self.assertEqual(paired_prices(row), ([1.012, 49.35], 'cloture'))

    def test_reviewed_prices_are_repeatable_and_bound_to_exact_source_identity(self):
        for c in corrections().values():
            row = dict(match_id=c['sourceId'], date=c['sourceDate']+' 12:00:00',
                       joueur1_id=c['sourcePlayerIds'][0], joueur2_id=c['sourcePlayerIds'][1],
                       cote1_cloture=str(c['oldSourceOdds'][0]), cote2_cloture=str(c['oldSourceOdds'][1]))
            self.assertEqual(paired_prices(row), (c['sourceOdds'], 'reviewed'))
            for key, value in [('date', '1999-01-01'), ('joueur1_id', 'wrong'),
                               ('cote1_cloture', '2.12345')]:
                with self.assertRaises(ValueError):
                    reviewed_price({**row, key: value})
            fixed = {**row, 'cote1_cloture':str(c['sourceOdds'][0]),
                     'cote2_cloture':str(c['sourceOdds'][1])}
            self.assertEqual(paired_prices(fixed), (c['sourceOdds'], 'reviewed'))

    def test_normal_opening_and_later_snapshots_are_not_equalised(self):
        row = dict(cote1_ouverture='3.5', cote2_ouverture='1.3',
                   cote1_cloture='2.1', cote2_cloture='1.8')
        before = copy.deepcopy(row)
        self.assertFalse(suspicious_close(row))
        self.assertIsNone(reviewed_price(row))
        self.assertEqual(paired_prices(row), ([2.1, 1.8], 'cloture'))
        self.assertEqual(row, before)
