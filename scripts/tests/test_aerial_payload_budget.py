import copy
import json
import tempfile
import unittest
from pathlib import Path
from aerial_data import public_bytes, save, read, utc, validate

class AerialPayloadBudgetTests(unittest.TestCase):
    def setUp(self):
        self.now=utc('2026-10-31T13:30:00Z')
        self.payload={'schema_version':1,'generated_at':self.now.isoformat(),
                      'calendar_observed_at':self.now.isoformat(),'fixtures':[]}

    def test_budget_uses_actual_published_utf8_not_escaped_display_json(self):
        self.payload['padding']=['Ã‰derson']*330000
        self.assertGreater(len(json.dumps(self.payload).encode()),4_000_000)
        self.assertLess(len(public_bytes(self.payload)),4_000_000)
        self.assertTrue(validate(self.payload,self.now))

    def test_real_oversize_still_blocked(self):
        self.payload['padding']='x'*4_000_000
        with self.assertRaisesRegex(ValueError,'4 MB'):validate(self.payload,self.now)

    def test_nonfinite_values_rejected(self):
        self.payload['padding']=float('nan')
        with self.assertRaises(ValueError):validate(self.payload,self.now)

    def test_saved_bytes_and_roundtrip_preserve_every_field(self):
        self.payload['name']='Ã‰derson';self.payload['stats']={'rate':.333,'unknown':None,'zero':0}
        before=copy.deepcopy(self.payload)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'board.json';save(p,self.payload)
            self.assertEqual(p.read_bytes(),public_bytes(self.payload))
            self.assertEqual(read(p),before)
        self.assertEqual(self.payload,before)

    def test_calendar_expiry_not_bypassed(self):
        self.payload['calendar_observed_at']='2026-10-28T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'calendar is stale'):validate(self.payload,self.now)

if __name__=='__main__':unittest.main()
