"""Readable exposure scoring. The rules live in rules.json; this file only applies them.

A rule looks like:
  {"id": "long_lead", "label": "Booked more than 60 days ahead",
   "field": "lead_time_days", "op": ">", "value": 60, "points": 2}
Supported ops: >  >=  <  <=  ==  !=  in  (in takes a list).
A booking with no value for the field gets 0 points for that rule.
"""
from __future__ import annotations

import json
import math
import os

OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b,
}


class RulesError(ValueError):
    pass


def load_rules(path: str) -> dict:
    if not os.path.exists(path):
        raise RulesError("Rules file not found: %s" % path)
    with open(path, encoding="utf-8") as fh:
        try:
            rules = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RulesError("rules.json is not valid JSON (line %d): %s" % (exc.lineno, exc.msg))
    validate_rules(rules)
    return rules


def validate_rules(rules: dict) -> None:
    for section in ("scoring", "eligibility", "holdout", "messages", "checks", "power"):
        if section not in rules:
            raise RulesError("rules.json is missing the '%s' section" % section)
    for r in rules["scoring"]["rules"]:
        for key in ("id", "field", "op", "value", "points"):
            if key not in r:
                raise RulesError("Scoring rule %r is missing '%s'" % (r.get("id", "?"), key))
        if r["op"] not in OPS:
            raise RulesError("Scoring rule %r uses unknown op %r" % (r["id"], r["op"]))
    share = rules["holdout"]["share"]
    if not 0 < share < 1:
        raise RulesError("holdout.share needs to be between 0 and 1 (for example 0.5)")
    top = rules["eligibility"]["top_share"]
    if not 0 < top <= 1:
        raise RulesError("eligibility.top_share needs to be above 0 and at most 1 (for example 0.10)")


def derive(booking: dict) -> dict:
    """Add computed fields used by rules. Does not change the input."""
    b = dict(booking)
    if b.get("trip_date") and b.get("booked_date"):
        b["lead_time_days"] = (b["trip_date"] - b["booked_date"]).days
    else:
        b["lead_time_days"] = None
    b["trip_month"] = b["trip_date"].month if b.get("trip_date") else None
    return b


def _norm(v):
    return v.strip().lower() if isinstance(v, str) else v


def condition_true(booking: dict, cond: dict) -> bool:
    actual = booking.get(cond["field"])
    if actual is None or actual == "":
        return False
    expected = cond["value"]
    op = OPS[cond["op"]]
    if cond["op"] == "in":
        return _norm(actual) in [_norm(x) for x in expected]
    try:
        return bool(op(_norm(actual), _norm(expected)))
    except TypeError:
        return False


def all_true(booking: dict, conds: list) -> bool:
    return all(condition_true(booking, c) for c in conds or [])


def score_booking(booking: dict, rules: dict):
    """Return (score, list of rule ids that matched)."""
    b = derive(booking)
    score, hits = 0, []
    for r in rules["scoring"]["rules"]:
        if not r.get("enabled", True):
            continue
        if condition_true(b, r):
            score += int(r["points"])
            hits.append(r["id"])
    return score, hits


def score_all(bookings: list, rules: dict):
    """Score open bookings and mark the top share as eligible.

    Returns (scored_rows, info). Ties at the cutoff are broken by longer lead time, then by booking_id,
    so the same file always gives the same eligible set.
    """
    skip = set(s.lower() for s in rules["eligibility"].get("skip_status", []))
    scored, skipped = [], 0
    for bk in bookings:
        if (bk.get("status") or "").lower() in skip:
            skipped += 1
            continue
        s, hits = score_booking(bk, rules)
        row = derive(bk)
        row["score"] = s
        row["rules_hit"] = "+".join(hits)
        scored.append(row)
    scored.sort(key=lambda r: (-r["score"], -(r["lead_time_days"] or 0), r["booking_id"]))
    k = math.ceil(len(scored) * float(rules["eligibility"]["top_share"])) if scored else 0
    cutoff = scored[k - 1]["score"] if k else None
    for i, row in enumerate(scored):
        row["eligible"] = 1 if i < k else 0
    tied_out = sum(1 for r in scored[k:] if cutoff is not None and r["score"] == cutoff)
    info = {
        "open": len(scored),
        "skipped_status": skipped,
        "eligible": k,
        "cutoff_score": cutoff,
        "tied_at_cutoff_not_selected": tied_out,
    }
    return scored, info
