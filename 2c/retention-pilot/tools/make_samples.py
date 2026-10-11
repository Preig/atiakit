#!/usr/bin/env python3
"""Write sample_output/example-drafts.md: one dry-run draft each of A, B and C, plus a bad draft
and the flags the local checks raise on it. Fictional data only.

  python tools/make_samples.py
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from retention import drafting  # noqa: E402
from retention.rules import load_rules  # noqa: E402

FICTIONAL_TERMS = ("FICTIONAL EXAMPLE TERMS: switch to our non-refundable rate at least 30 days before your trip "
                   "and we add a printed wildlife guide for each guest. (The owner writes the real terms.)")

BAD_DRAFT = """Subject: Don't cancel!

Hello,

Good news: we'll match any lower price you find, and for $99 more you get a private charter.
You will see whales, guaranteed. Call 907-555-0142 to lock it in."""


def main():
    rules = load_rules(os.path.join(HERE, "rules.json"))
    facts, facts_text = drafting.load_facts(os.path.join(HERE, "approved_facts.md"))
    addons = drafting.load_addons(os.path.join(HERE, "approved_addons.csv"))
    tdir = os.path.join(HERE, "templates")
    booking = {
        "booking_id": "BL-26-DEMO", "booked_date": dt.date(2026, 3, 2), "trip_date": dt.date(2026, 7, 14),
        "departure_time": "9:00", "rate_type": "flexible", "channel": "direct", "party_size": 2,
        "addons_count": 0, "price_alert_flag": 1,
    }
    ctx = drafting.booking_context(booking)
    out = ["# Example drafts (dry run, fictional)", "",
           "Bay Light Day Cruises, Seward is a FICTIONAL TEACHING BUSINESS. These were made by "
           "`python tools/make_samples.py` from the templates, approved_facts.md and approved_addons.csv. "
           "No model was called. Each [FILL] is a fact the owner has not supplied yet.", "",
           "Example booking: %s, trip %s at %s, flexible rate, booked direct, party of %d, no add-ons."
           % (ctx["booking_id"], ctx["trip_date_long"], ctx["departure_time"], booking["party_size"]), ""]

    plans = drafting.plan_messages(booking, rules, addons)
    addon = next((p.get("addon") for p in plans if p["type"] == "B" and not p.get("skip")), None)
    for mtype, extra in (("A", None), ("B", addon), ("C", None)):
        terms = FICTIONAL_TERMS if mtype == "C" else ""
        subject, text = drafting.dry_run_draft(mtype, tdir, facts, ctx, extra, terms)
        raw = drafting.load_template(os.path.join(tdir, drafting.TEMPLATE_FILES[mtype]))[2]
        allowed = "\n".join([facts_text, raw, terms, "\n".join(str(v) for v in (extra or {}).values()),
                             "\n".join(ctx.values())])
        flags = drafting.check_draft(text, allowed, rules, int(rules["messages"]["max_words"]))
        name = drafting.MESSAGE_INFO[mtype][0]
        out += ["## Message %s: %s" % (mtype, name), ""]
        if mtype == "C":
            out += ["Only drafted when the owner writes terms into rules.json. The terms below are fictional.", ""]
        out += ["```text", text, "```", "", "Local checks: " + ("; ".join(flags) if flags else "no flags"), ""]

    rules_c = copy.deepcopy(rules)
    allowed = facts_text
    flags = drafting.check_draft(BAD_DRAFT, allowed, rules_c, int(rules["messages"]["max_words"]))
    out += ["## A draft the checks would stop", "",
            "If a model wrote this, the queue row would carry these flags. A person still decides.", "",
            "```text", BAD_DRAFT, "```", ""]
    out += ["- " + f for f in flags]
    out += ["", "The phone number above is a fictional 555 number used only to show the check."]
    path = os.path.join(HERE, "sample_output", "example-drafts.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("Wrote %s" % path)


if __name__ == "__main__":
    main()
