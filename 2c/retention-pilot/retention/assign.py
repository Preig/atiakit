"""Seeded holdout assignment, stored once and never reassigned.

Each eligible booking is placed in "holdout" or "treatment" from a hash of (seed, booking_id).
The same seed and booking_id always give the same arm, in any order, on any computer.
The result is written to state/assignments.csv. A booking already in that file keeps its arm,
even if the seed or the share in rules.json changes later.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os

FIELDS = [
    "booking_id", "arm", "assigned_on", "seed", "holdout_share", "score_at_assignment",
    "rate_type", "channel", "lead_time_days", "trip_date", "booked_date", "departure_time",
    "party_size", "addons_count", "price_alert_flag", "booking_value_usd",
]


def unit_hash(seed: str, booking_id: str) -> float:
    h = hashlib.sha256(("%s|%s" % (seed, booking_id)).encode("utf-8")).hexdigest()
    return int(h[:15], 16) / float(16 ** 15)


def arm_for(booking_id: str, seed: str, holdout_share: float) -> str:
    return "holdout" if unit_hash(seed, booking_id) < holdout_share else "treatment"


def read_assignments(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (dt.date,)):
        return v.isoformat()
    return str(v)


def assign(eligible_rows: list[dict], path: str, seed: str, holdout_share: float, today: dt.date | None = None):
    """Append new eligible bookings to the store. Returns (new_rows, kept_count, warnings)."""
    today = today or dt.date.today()
    existing = read_assignments(path)
    known = {r["booking_id"] for r in existing}
    warnings = []
    if existing:
        old = {(r["seed"], r["holdout_share"]) for r in existing}
        if (str(seed), str(holdout_share)) not in old:
            warnings.append(
                "rules.json seed or holdout share differs from earlier assignments. "
                "Earlier bookings keep their arm; only new bookings use the new setting."
            )
    new_rows = []
    for r in eligible_rows:
        if r["booking_id"] in known:
            continue
        row = {
            "booking_id": r["booking_id"],
            "arm": arm_for(r["booking_id"], str(seed), float(holdout_share)),
            "assigned_on": today.isoformat(),
            "seed": str(seed),
            "holdout_share": str(holdout_share),
            "score_at_assignment": r.get("score", ""),
        }
        for f in FIELDS[6:]:
            row[f] = _cell(r.get(f))
        new_rows.append(row)
        known.add(r["booking_id"])
    if new_rows:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        write_header = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if write_header:
                w.writeheader()
            for row in new_rows:
                w.writerow({k: _cell(row.get(k)) for k in FIELDS})
    return new_rows, len(existing), warnings
