import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from adapters.csv_adapter import BOOKING_COLUMNS, AdapterError, load_bookings, load_outcomes  # noqa: E402
from adapters.platform_stubs import ADAPTERS  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "export_with_pii.csv")
MOCK = os.path.join(ROOT, "data", "baylight-bookings-mock.csv")


class AdapterTests(unittest.TestCase):
    def test_drops_personal_columns_and_logs_names_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, log = load_bookings(FIXTURE, tmp)
            for r in rows:
                self.assertTrue(set(r) <= set(BOOKING_COLUMNS), r.keys())
            joined = "\n".join(log.lines)
            for col in ("Guest Name", "Guest Email", "Phone", "Card Last 4", "Special Requests"):
                self.assertIn("'%s'" % col, joined)
            with open(os.path.join(tmp, "adapter-log.txt"), encoding="utf-8") as fh:
                written = fh.read()
            for secret in ("FAKE NAME", "example.invalid", "555", "4242", "FAKE REQUEST"):
                self.assertNotIn(secret, joined)
                self.assertNotIn(secret, written)

    def test_values_that_look_personal_are_blanked(self):
        rows, log = load_bookings(FIXTURE, None)
        t2 = next(r for r in rows if r["booking_id"] == "T-002")
        self.assertEqual(t2["product"], "")
        self.assertTrue(any("line 3" in line and "email" in line for line in log.lines))

    def test_bad_rows_are_skipped(self):
        rows, log = load_bookings(FIXTURE, None)
        ids = [r["booking_id"] for r in rows]
        self.assertEqual(ids, ["T-001", "T-002"])
        self.assertTrue(any("line 4" in line for line in log.lines))
        self.assertTrue(any("line 5" in line for line in log.lines))

    def test_normalizes_types(self):
        rows, _ = load_bookings(FIXTURE, None)
        t1, t2 = rows
        self.assertEqual((t1["rate_type"], t1["channel"], t1["party_size"], t1["addons_count"]),
                         ("flexible", "ota", 2, 0))
        self.assertEqual((t2["rate_type"], t2["channel"]), ("non_refundable", "direct"))
        self.assertEqual(t2["trip_date"].isoformat(), "2026-07-20")
        self.assertEqual(t2["booked_date"].isoformat(), "2026-05-01")

    def test_missing_required_column_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("booking_id,trip_date\nA-1,2026-07-01\n")
            with self.assertRaises(AdapterError):
                load_bookings(path, None)

    def test_mock_file_loads_and_drops_note_column(self):
        rows, log = load_bookings(MOCK, None)
        self.assertEqual(len(rows), 300)
        self.assertTrue(any("booking_note" in line for line in log.lines))
        self.assertTrue(all("booking_note" not in r for r in rows))

    def test_outcomes_loader(self):
        rows, _ = load_outcomes(os.path.join(ROOT, "data", "baylight-outcomes-mock.csv"), None)
        self.assertEqual(len(rows), 300)
        self.assertTrue(all(r["outcome"] for r in rows))

    def test_platform_stubs_are_not_built(self):
        for cls in ADAPTERS.values():
            with self.assertRaises(NotImplementedError):
                cls().fetch_open_bookings()


if __name__ == "__main__":
    unittest.main()
