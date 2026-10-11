import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pilot  # noqa: E402
from retention import report  # noqa: E402
from retention.rules import load_rules  # noqa: E402
from retention.stats import required_sample, split_table, wilson  # noqa: E402

RULES = load_rules(os.path.join(ROOT, "rules.json"))


class WilsonTests(unittest.TestCase):
    def test_known_values(self):
        p, lo, hi = wilson(0, 10)
        self.assertEqual((p, lo), (0.0, 0.0))
        self.assertAlmostEqual(hi, 0.2775, places=4)
        p, lo, hi = wilson(5, 10)
        self.assertAlmostEqual(lo, 0.2366, places=4)
        self.assertAlmostEqual(hi, 0.7634, places=4)
        p, lo, hi = wilson(10, 10)
        self.assertEqual(hi, 1.0)

    def test_zero_n(self):
        self.assertEqual(wilson(0, 0), (None, None, None))


class PowerTests(unittest.TestCase):
    def test_kit_number_50_50(self):
        r = required_sample(0.15, 0.12, 0.5)
        self.assertEqual((r["holdout"], r["treatment"], r["total"]), (2036, 2036, 4072))

    def test_80_20_costs_about_one_and_a_half_times(self):
        rows = {round(r["holdout_share"], 2): r for r in split_table(0.15, 0.12, (0.5, 0.2))}
        r = rows[0.2]
        self.assertTrue(1.45 < r["vs_5050"] < 1.6, r["vs_5050"])
        self.assertAlmostEqual(r["rule_of_thumb_factor"], 1.5625)
        self.assertLess(r["holdout"], r["treatment"])

    def test_power_text_single_operator_is_directional(self):
        text = pilot.power_text(0.15, 0.12, 0.5, 0.05, 0.8, 1500, 0.10, 1)
        self.assertIn("2,036", text)
        self.assertIn("DIRECTIONAL READ ONLY", text)
        self.assertIn("about 28", text)

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            required_sample(0.15, 0.15, 0.5)
        with self.assertRaises(ValueError):
            required_sample(0.15, 0.12, 1.0)


def assignment(i, arm, rate="flexible", value="298"):
    return {"booking_id": "B-%d" % i, "arm": arm, "rate_type": rate, "booking_value_usd": value}


class ReportTests(unittest.TestCase):
    def test_counts_rates_and_exclusions(self):
        a = [assignment(i, "treatment") for i in range(10)] + [assignment(i, "holdout") for i in range(10, 20)]
        a += [assignment(30, "treatment", "non_refundable"), assignment(31, "holdout", "non_refundable")]
        outcomes = [{"booking_id": "B-%d" % i, "outcome": "kept"} for i in range(32)]
        outcomes[0]["outcome"] = "cancelled_in_window"
        outcomes[1]["outcome"] = "operator_cancelled"
        outcomes[10]["outcome"] = "changed_in_window"
        outcomes[11]["outcome"] = "cancelled_in_window"
        outcomes = [o for o in outcomes if o["booking_id"] != "B-19"]  # one holdout outcome missing
        md, rows, summary = report.build(a, outcomes, RULES, queue=[], fictional=True)
        t = summary["Flexible rate"]["treatment"]
        h = summary["Flexible rate"]["holdout"]
        self.assertEqual((t["n"], t["events"], t["operator_cancelled_excluded"]), (9, 1, 1))
        self.assertEqual((h["n"], h["events"], h["with_outcome"]), (9, 2, 9))
        self.assertEqual(t["value_of_in_window_cancellations_usd"], 298.0)
        self.assertEqual(summary["Flexible rate"]["read"], "TOO SMALL TO READ: counts only")
        self.assertEqual(summary["All eligible bookings"]["treatment"]["n"], 10)
        self.assertEqual(summary["Non-refundable rate"]["treatment"]["n"], 1)
        self.assertIn("FICTIONAL", md)
        self.assertIn("No outcome yet for 1", md)
        self.assertEqual(len(rows), 6)

    def test_directional_label(self):
        need = {"holdout": 2036, "treatment": 2036}
        s = {"n": 500}
        self.assertEqual(report.read_label(s, s, need), "DIRECTIONAL ONLY")
        self.assertEqual(report.read_label({"n": 0}, s, need), "NO DATA")
        self.assertTrue(report.read_label({"n": 3000}, {"n": 3000}, need).startswith("SAMPLE SIZE REACHED"))


if __name__ == "__main__":
    unittest.main()
