import copy
import datetime as dt
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from retention import DRAFT_MARKER, drafting  # noqa: E402
from retention.rules import load_rules  # noqa: E402

RULES = load_rules(os.path.join(ROOT, "rules.json"))
FACTS, FACTS_TEXT = drafting.load_facts(os.path.join(ROOT, "approved_facts.md"))
ADDONS = drafting.load_addons(os.path.join(ROOT, "approved_addons.csv"))
TDIR = os.path.join(ROOT, "templates")


def booking(**kw):
    b = {"booking_id": "BL-T", "booked_date": dt.date(2026, 3, 1), "trip_date": dt.date(2026, 7, 14),
         "departure_time": "9:00", "rate_type": "flexible", "channel": "direct", "party_size": 2,
         "addons_count": 0, "price_alert_flag": 0}
    b.update(kw)
    return b


def allowed_for(mtype, ctx, addon=None, terms=""):
    raw = drafting.load_template(os.path.join(TDIR, drafting.TEMPLATE_FILES[mtype]))[2]
    return "\n".join([FACTS_TEXT, raw, terms, "\n".join(str(v) for v in (addon or {}).values()),
                      "\n".join(ctx.values())])


class FactsAndTemplates(unittest.TestCase):
    def test_facts_skip_fill_lines(self):
        self.assertIn("meeting_point", FACTS)
        self.assertNotIn("contact_person", FACTS)
        self.assertNotIn("track_record", FACTS)

    def test_missing_fact_becomes_fill(self):
        out = drafting.render("Call {{fact.contact_person}} about {{fact.offer}}.", FACTS, {}, None, "")
        self.assertEqual(out, "Call [FILL: contact person] about 4-hour wildlife and glacier cruise.")

    def test_every_dry_run_draft_has_marker_and_only_fill_flags(self):
        ctx = drafting.booking_context(booking())
        for mtype, addon, terms in (("A", None, ""), ("B", ADDONS[0], ""), ("C", None, "Owner terms here.")):
            subject, text = drafting.dry_run_draft(mtype, TDIR, FACTS, ctx, addon, terms)
            self.assertTrue(text.startswith(DRAFT_MARKER))
            self.assertIn("Subject: " + subject, text)
            flags = drafting.check_draft(text, allowed_for(mtype, ctx, addon, terms), RULES, 160)
            self.assertTrue(all("[FILL]" in f for f in flags), flags)

    def test_no_guest_name_placeholder_in_templates(self):
        for f in drafting.TEMPLATE_FILES.values():
            with open(os.path.join(TDIR, f), encoding="utf-8") as fh:
                text = fh.read().lower()
            self.assertNotIn("name}}", text.replace("addon.name}}", ""))
            self.assertIn("hello,", text)


class Planning(unittest.TestCase):
    def test_ota_booking_gets_only_a(self):
        plans = drafting.plan_messages(booking(channel="ota"), RULES, ADDONS)
        self.assertEqual(plans[0]["type"], "A")
        self.assertTrue(all(p.get("skip") for p in plans[1:]))
        self.assertIn("Contractual", plans[1]["skip"])

    def test_direct_no_addons_morning_gets_kennel(self):
        plans = [p for p in drafting.plan_messages(booking(), RULES, ADDONS) if not p.get("skip")]
        self.assertEqual([p["type"] for p in plans], ["A", "B"])
        self.assertEqual(plans[1]["addon"]["addon_id"], "K1")
        self.assertEqual(plans[0]["send_date"], dt.date(2026, 3, 2))
        self.assertEqual(plans[1]["send_date"], dt.date(2026, 3, 16))

    def test_afternoon_gets_kayak(self):
        plans = [p for p in drafting.plan_messages(booking(departure_time="14:00"), RULES, ADDONS) if not p.get("skip")]
        self.assertEqual(plans[1]["addon"]["addon_id"], "P1")

    def test_lockin_needs_owner_terms(self):
        b = booking(addons_count=1, price_alert_flag=1)
        plans = drafting.plan_messages(b, RULES, ADDONS)
        self.assertEqual([p["type"] for p in plans if not p.get("skip")], ["A"])
        self.assertTrue(any("lock-in terms" in p.get("skip", "") for p in plans))
        rules = copy.deepcopy(RULES)
        rules["messages"]["lockin_terms"] = "Fictional terms."
        plans = drafting.plan_messages(b, rules, ADDONS)
        self.assertEqual([p["type"] for p in plans if not p.get("skip")], ["A", "C"])

    def test_confidence_first(self):
        rules = copy.deepcopy(RULES)
        rules["messages"]["lockin_terms"] = "Fictional terms."
        plans = drafting.plan_messages(booking(price_alert_flag=1), rules, ADDONS)
        kept = [p["type"] for p in plans if not p.get("skip")]
        self.assertEqual(kept[0], "A")
        self.assertLessEqual(len(kept), 2)

    def test_trip_too_soon(self):
        plans = drafting.plan_messages(booking(booked_date=dt.date(2026, 7, 12)), RULES, ADDONS)
        self.assertEqual(len(plans), 1)
        self.assertIn("too soon", plans[0]["skip"])


class Checks(unittest.TestCase):
    def setUp(self):
        self.ctx = drafting.booking_context(booking())
        self.allowed = allowed_for("A", self.ctx)

    def flags(self, text):
        return drafting.check_draft(text, self.allowed, RULES, 160)

    def test_number_guard_flags_new_price(self):
        f = self.flags(DRAFT_MARKER + "\nSubject: x\n\nAdd lunch for $99.")
        self.assertTrue(any("99" in x for x in f), f)

    def test_known_numbers_pass(self):
        f = self.flags(DRAFT_MARKER + "\nSubject: x\n\nMeet at 9:00 for the 4-hour cruise, 12-minute walk, 48 hours.")
        self.assertFalse(any("number" in x for x in f), f)

    def test_price_match_and_promises_flagged(self):
        f = self.flags(DRAFT_MARKER + "\nSubject: x\n\nWe will match any lower price. You will see whales, guaranteed.")
        joined = " | ".join(f)
        self.assertIn("match any", joined)
        self.assertIn("will see", joined)
        self.assertIn("guarantee", joined)

    def test_words_in_approved_facts_are_allowed(self):
        f = self.flags(DRAFT_MARKER + "\nSubject: x\n\nFree cancellation until 48 hours before departure, with a full refund.")
        self.assertEqual(f, [])

    def test_personal_data_flagged(self):
        f = self.flags(DRAFT_MARKER + "\nSubject: x\n\nWrite to someone@example.invalid or 907-555-0199.")
        self.assertTrue(any("email" in x for x in f))
        self.assertTrue(any("phone" in x for x in f))

    def test_missing_marker_flagged(self):
        self.assertIn("missing the DRAFT marker", self.flags("Hello"))

    def test_split_model_text_adds_marker(self):
        subject, text, added = drafting.split_model_text("Subject: Hi there\n\nHello,", "fallback")
        self.assertTrue(added)
        self.assertTrue(text.startswith(DRAFT_MARKER))
        self.assertEqual(subject, "Hi there")


if __name__ == "__main__":
    unittest.main()
