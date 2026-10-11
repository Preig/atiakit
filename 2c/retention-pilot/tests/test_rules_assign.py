import copy
import datetime as dt
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from adapters.csv_adapter import load_bookings  # noqa: E402
from retention import assign as assign_mod  # noqa: E402
from retention.rules import RulesError, load_rules, score_all, score_booking, validate_rules  # noqa: E402

RULES = load_rules(os.path.join(ROOT, "rules.json"))


def booking(**kw):
    b = {"booking_id": "X-1", "booked_date": dt.date(2026, 1, 10), "trip_date": dt.date(2026, 7, 1),
         "rate_type": "flexible", "channel": "ota", "addons_count": 0, "price_alert_flag": 1}
    b.update(kw)
    return b


class ScoringTests(unittest.TestCase):
    def test_four_default_rules(self):
        score, hits = score_booking(booking(), RULES)
        self.assertEqual(score, 6)
        self.assertEqual(hits, ["long_lead", "flexible", "ota", "no_addons"])

    def test_disabled_rule_is_ignored_and_can_be_enabled(self):
        rules = copy.deepcopy(RULES)
        for r in rules["scoring"]["rules"]:
            if r["id"] == "price_alert":
                r["enabled"] = True
        self.assertEqual(score_booking(booking(), rules)[0], 7)

    def test_short_lead_nonref_direct(self):
        b = booking(booked_date=dt.date(2026, 6, 20), rate_type="non_refundable", channel="direct", addons_count=2)
        self.assertEqual(score_booking(b, RULES)[0], 0)

    def test_missing_value_scores_zero(self):
        self.assertEqual(score_booking(booking(addons_count=None, channel=""), RULES)[0], 4)

    def test_top_share_is_deterministic(self):
        rows, _ = load_bookings(os.path.join(ROOT, "data", "baylight-bookings-mock.csv"), None)
        a, info = score_all(rows, RULES)
        b, _ = score_all(list(reversed(rows)), RULES)
        self.assertEqual(info["eligible"], 30)
        self.assertEqual([r["booking_id"] for r in a if r["eligible"]], [r["booking_id"] for r in b if r["eligible"]])

    def test_skip_status(self):
        scored, info = score_all([booking(status="cancelled"), booking(booking_id="X-2")], RULES)
        self.assertEqual(info["skipped_status"], 1)
        self.assertEqual(len(scored), 1)

    def test_validation(self):
        bad = copy.deepcopy(RULES)
        bad["holdout"]["share"] = 1.5
        with self.assertRaises(RulesError):
            validate_rules(bad)


class AssignmentTests(unittest.TestCase):
    def test_same_input_same_arm(self):
        self.assertEqual(assign_mod.arm_for("BL-1", "s", 0.5), assign_mod.arm_for("BL-1", "s", 0.5))

    def test_share_is_close_to_target(self):
        ids = ["B-%d" % i for i in range(20000)]
        for share in (0.5, 0.2):
            hold = sum(1 for i in ids if assign_mod.arm_for(i, "seed", share) == "holdout") / len(ids)
            self.assertAlmostEqual(hold, share, delta=0.015)

    def test_stored_once_never_reassigned(self):
        rows = [{"booking_id": "B-%d" % i, "score": 6, "rate_type": "flexible"} for i in range(40)]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state", "assignments.csv")
            new, kept, warn = assign_mod.assign(rows, path, "seed-1", 0.5, dt.date(2026, 10, 10))
            self.assertEqual((len(new), kept, warn), (40, 0, []))
            first = {r["booking_id"]: r["arm"] for r in assign_mod.read_assignments(path)}
            more = rows + [{"booking_id": "NEW-1", "score": 5}]
            new2, kept2, warn2 = assign_mod.assign(more, path, "another-seed", 0.2, dt.date(2026, 10, 11))
            self.assertEqual([r["booking_id"] for r in new2], ["NEW-1"])
            self.assertEqual(kept2, 40)
            self.assertTrue(warn2)
            after = {r["booking_id"]: r["arm"] for r in assign_mod.read_assignments(path)}
            for k, v in first.items():
                self.assertEqual(after[k], v)

    def test_store_has_no_personal_fields(self):
        for f in assign_mod.FIELDS:
            self.assertNotRegex(f, "name|email|phone|card|address")


if __name__ == "__main__":
    unittest.main()
