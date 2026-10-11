#!/usr/bin/env python3
"""Rebuild the fictional mock data in data/. Seeded, so the files come out the same every time.

  python tools/make_mock_data.py

Bookings: 300 for Bay Light Day Cruises, Seward (FICTIONAL TEACHING BUSINESS), season May 15 to
September 15, 2026. No names, emails, phones or payment data. One extra column, booking_note,
is there on purpose so you can watch the adapter drop it.

Outcomes: simulated. The in-window change and cancellation chances below are invented for
teaching. Treatment bookings (with the default rules.json seed and split) get a 25% lower chance,
also invented, so the report has something to show. With 300 bookings the effect is not detectable,
which is the point of the power command.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from retention.assign import arm_for  # noqa: E402
from retention.rules import load_rules, score_all  # noqa: E402

SEASON_START = dt.date(2026, 5, 15)
SEASON_END = dt.date(2026, 9, 15)
EARLIEST_BOOKING = dt.date(2026, 1, 2)
PRICE_PER_GUEST = 149  # invented for the report's revenue line; not a Bay Light fact
NOTES = ["", "", "", "", "", "stroller", "window seat request", "celebrating a birthday", "arriving by cruise ship"]


def pick(rng, weighted):
    r, acc = rng.random(), 0.0
    for value, w in weighted:
        acc += w
        if r < acc:
            return value
    return weighted[-1][0]


def make_bookings(n=300, seed=2026):
    rng = random.Random(seed)
    days = (SEASON_END - SEASON_START).days
    rows = []
    for i in range(1, n + 1):
        trip = SEASON_START + dt.timedelta(days=rng.randint(0, days))
        lead_band = pick(rng, [((0, 14), 0.30), ((15, 60), 0.30), ((61, 180), 0.40)])
        lead = rng.randint(*lead_band)
        booked = max(EARLIEST_BOOKING, trip - dt.timedelta(days=lead))
        rate = pick(rng, [("flexible", 0.70), ("non_refundable", 0.30)])
        channel = pick(rng, [("direct", 0.40), ("ota", 0.45), ("hotel_desk", 0.15)])
        party = pick(rng, [(1, 0.10), (2, 0.40), (3, 0.15), (4, 0.20), (5, 0.08), (6, 0.07)])
        addons = pick(rng, [(0, 0.60), (1, 0.30), (2, 0.10)])
        alert = 1 if (rate == "flexible" and rng.random() < 0.20) else 0
        rows.append({
            "booking_id": "BL-26-%04d" % i,
            "booked_date": booked.isoformat(),
            "trip_date": trip.isoformat(),
            "departure_time": rng.choice(["9:00", "14:00"]),
            "product": "4-hour wildlife and glacier cruise",
            "rate_type": rate,
            "channel": channel,
            "party_size": party,
            "addons_count": addons,
            "price_alert_flag": alert,
            "booking_value_usd": party * PRICE_PER_GUEST,
            "status": "open",
            "booking_note": rng.choice(NOTES),
        })
    return rows


def in_window_chance(b) -> float:
    lead = (dt.date.fromisoformat(b["trip_date"]) - dt.date.fromisoformat(b["booked_date"])).days
    if b["rate_type"] == "non_refundable":
        return 0.03  # date changes only
    p = 0.08
    p += 0.08 if lead > 60 else 0.0
    p += 0.04 if b["channel"] == "ota" else 0.0
    p += 0.02 if int(b["addons_count"]) == 0 else 0.0
    return p


def make_outcomes(bookings, rules, seed=2027):
    rng = random.Random(seed)
    typed = []
    for b in bookings:
        t = dict(b)
        t["booked_date"] = dt.date.fromisoformat(b["booked_date"])
        t["trip_date"] = dt.date.fromisoformat(b["trip_date"])
        t["addons_count"] = int(b["addons_count"])
        t["price_alert_flag"] = int(b["price_alert_flag"])
        typed.append(t)
    scored, _ = score_all(typed, rules)
    eligible = {r["booking_id"] for r in scored if r["eligible"]}
    seed_txt, share = str(rules["holdout"]["seed"]), float(rules["holdout"]["share"])
    out = []
    for b in bookings:
        trip = dt.date.fromisoformat(b["trip_date"])
        p = in_window_chance(b)
        if b["booking_id"] in eligible and arm_for(b["booking_id"], seed_txt, share) == "treatment":
            p *= 0.75
        r = rng.random()
        if r < 0.03:
            outcome, when = "operator_cancelled", trip - dt.timedelta(days=1)
        elif r < 0.03 + p:
            kind = "changed_in_window" if rng.random() < 0.4 else "cancelled_in_window"
            if b["rate_type"] == "non_refundable":
                kind = "changed_in_window"
            booked = dt.date.fromisoformat(b["booked_date"])
            span = max(0, (trip - booked).days - 3)
            outcome, when = kind, booked + dt.timedelta(days=rng.randint(0, span))
        elif b["rate_type"] == "flexible" and r < 0.05 + p:
            outcome, when = "cancelled_late", trip - dt.timedelta(days=1)
        else:
            outcome, when = "kept", trip
        out.append({"booking_id": b["booking_id"], "outcome": outcome, "outcome_date": when.isoformat()})
    return out


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    rules = load_rules(os.path.join(HERE, "rules.json"))
    bookings = make_bookings()
    outcomes = make_outcomes(bookings, rules)
    data = os.path.join(HERE, "data")
    os.makedirs(data, exist_ok=True)
    write_csv(os.path.join(data, "baylight-bookings-mock.csv"), bookings)
    write_csv(os.path.join(data, "baylight-outcomes-mock.csv"), outcomes)
    print("Wrote %d bookings and %d outcomes to %s" % (len(bookings), len(outcomes), data))


if __name__ == "__main__":
    main()
