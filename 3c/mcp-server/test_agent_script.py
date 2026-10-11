"""Scripted-agent tests for the trip-record scaffold. Standard library only; the mcp package is NOT needed.

    python -m unittest -v          (or: python -m pytest)

FICTIONAL TEACHING DATA. One test sleeps about 2 seconds to check real expiry with a 2-second TTL.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import Config, Inventory  # noqa: E402

A, B = "agent:alpha", "agent:bravo"
DAY = "2027-07-15"


def record(version: int, holds: list | None = None, bands: list | None = None) -> dict:
    return {
        "record_id": "TR-TEST-0001", "version": version, "updated_at": "2026-10-10T18:00:00Z",
        "party": {"count": 4, "age_bands": bands or [{"band": "18-64", "count": 2}, {"band": "6-7", "count": 1}, {"band": "8-9", "count": 1}]},
        "dates": {"arrive": "2027-07-14", "depart": "2027-07-16"},
        "budget_band": "not_stated", "preferences": {},
        "shortlisted": [{"product_id": "BL-CRUISE-4H", "date": DAY, "reason": "Minimum age 4 fits the children.", "source_fact_ids": ["BL-MIN-AGE"]}],
        "rejected": [{"product_id": "HK-PADDLE-3H", "rule": "min_age", "reason": "Minimum age 12.", "source_fact_ids": ["HK-MIN-AGE"]}],
        "holds": holds or [], "open_questions": [],
        "consent": {"purpose": "trip_planning", "traveler_reviewed": True, "agent_may_place_holds": True,
                    "agent_may_confirm": False, "retention_days": 30},
    }


def as_entry(h: dict) -> dict:
    return {k: h[k] for k in ("hold_id", "product_id", "date", "departure", "seats", "status", "expires_at") if k in h}


class Base(unittest.TestCase):
    ttl = 24 * 3600
    extra: dict = {}

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="trip-mcp-test-"))
        self.cfg = Config(db_path=str(self.tmp / "t.sqlite3"), log_path=str(self.tmp / "calls.jsonl"), hold_ttl_seconds=self.ttl, **self.extra)
        self.inv = Inventory(self.cfg)

    def tearDown(self) -> None:
        self.inv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def free(self, product: str, day: str, dep: str, caller: str = A) -> int:
        res = self.inv.check_availability(caller, product, day, 1)
        return {d["departure"]: d["available"] for d in res["departures"]}[dep]

    def log_lines(self) -> list[dict]:
        return [json.loads(x) for x in (self.tmp / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


class ScriptedAgentJourney(Base):
    def test_search_hold_review_change_confirm(self) -> None:
        inv = self.inv
        # 1. search: the 6-year-old rules out the kayak; prices are never invented
        found = inv.search_products(A, date=DAY, party_size=4, youngest_age=6)
        self.assertTrue(found["ok"])
        fits = {p["product_id"]: p["age_fit"]["fits"] for p in found["products"]}
        self.assertEqual(fits, {"BL-CRUISE-4H": True, "MK-CART-90": True, "HK-PADDLE-3H": False})
        cruise = next(p for p in found["products"] if p["product_id"] == "BL-CRUISE-4H")
        self.assertIn("BL-MIN-AGE", [f["fact_id"] for f in cruise["facts"]])
        self.assertIn("Do not quote a price", cruise["price"])
        self.assertEqual([(d["departure"], d["available"]) for d in cruise["availability"]], [("09:00", 40), ("14:00", 40)])

        # 2. hold the afternoon departure; held seats leave the pool
        h1 = inv.place_hold(A, "BL-CRUISE-4H", DAY, "14:00", 4, record_id="TR-TEST-0001")
        self.assertTrue(h1["ok"], h1)
        self.assertRegex(h1["hold_id"], r"^H-[A-Z]{10}$")
        self.assertEqual(h1["status"], "active")
        self.assertEqual(h1["ttl_seconds"], 24 * 3600)
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "14:00"), 36)

        # 3. write the trip record, then review it (hold status comes from the live inventory)
        saved = inv.put_trip_record(A, record(1, [as_entry(h1)]))
        self.assertTrue(saved["ok"], saved)
        review = inv.get_trip_record(A, "TR-TEST-0001")
        self.assertEqual(review["record"]["holds"][0]["status"], "active")

        # 4. change: release and re-hold the morning departure
        rel = inv.release_hold(A, h1["hold_id"])
        self.assertEqual(rel["status"], "released")
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "14:00"), 40)
        h2 = inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 4, record_id="TR-TEST-0001")
        self.assertTrue(h2["ok"], h2)
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "09:00"), 36)
        review = inv.get_trip_record(A, "TR-TEST-0001")
        self.assertEqual(review["record"]["holds"][0]["status"], "released")   # synced on read
        rec = review["record"]
        rec["version"] = 2
        rec["holds"].append(as_entry(h2))
        self.assertTrue(inv.put_trip_record(A, rec)["ok"])

        # 5. request confirmation: pending only, still counts against capacity
        rc = inv.request_confirmation(A, h2["hold_id"], note="Reviewed with the traveler. Mornings only.")
        self.assertTrue(rc["ok"], rc)
        self.assertEqual(rc["status"], "pending_staff_confirmation")
        self.assertEqual(inv.get_hold(A, h2["hold_id"])["status"], "pending_staff_confirmation")
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "09:00"), 36)
        self.assertEqual(inv.stats()["by_status"].get("confirmed", 0), 0)

        # 6. a person confirms in admin.py
        pending = inv.pending_confirmations()
        self.assertEqual([p["hold_id"] for p in pending], [h2["hold_id"]])
        done = inv.decide(rc["confirmation_id"], by="KR", approve=True)
        self.assertEqual(done["status"], "confirmed")
        self.assertEqual(inv.get_hold(A, h2["hold_id"])["status"], "confirmed")
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "09:00"), 36)
        self.assertEqual(inv.stats()["hold_to_book_rate"], 0.5)

        # 7. every call was logged, with caller and tool
        lines = self.log_lines()
        tools = [x["tool"] for x in lines]
        for t in ("search_products", "check_availability", "place_hold", "put_trip_record", "get_trip_record",
                  "release_hold", "request_confirmation", "get_hold", "admin.pending", "admin.confirm"):
            self.assertIn(t, tools)
        self.assertTrue(all(x["ts"] and x["caller"] and "ok" in x for x in lines))
        self.assertTrue(any(x["caller"] == "staff:KR" for x in lines))

    def test_agent_cannot_confirm(self) -> None:
        src = (HERE / "server.py").read_text(encoding="utf-8")
        tools = re.findall(r"@server\.tool\(\)\s+def (\w+)\(", src)
        self.assertEqual(sorted(tools), sorted(["search_products", "check_availability", "place_hold", "get_hold", "release_hold",
                                                "request_confirmation", "get_trip_record", "put_trip_record"]))
        self.assertFalse(any("confirm" in t and t != "request_confirmation" for t in tools))

    def test_holds_are_private_to_their_caller(self) -> None:
        h = self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 2)
        self.assertEqual(self.inv.get_hold(B, h["hold_id"])["error"], "HOLD_NOT_FOUND")
        self.assertEqual(self.inv.release_hold(B, h["hold_id"])["error"], "HOLD_NOT_FOUND")
        self.assertEqual(self.inv.get_hold(A, h["hold_id"])["status"], "active")

    def test_min_age_is_enforced_when_a_record_is_linked(self) -> None:
        self.assertTrue(self.inv.put_trip_record(A, record(1))["ok"])
        r = self.inv.place_hold(A, "HK-PADDLE-3H", DAY, "08:00", 4, record_id="TR-TEST-0001")
        self.assertEqual(r["error"], "MIN_AGE")
        self.assertTrue(self.inv.place_hold(A, "MK-CART-90", DAY, "10:00", 4, record_id="TR-TEST-0001")["ok"])

    def test_bad_inputs_are_refused_politely(self) -> None:
        inv = self.inv
        self.assertEqual(inv.place_hold(A, "NOPE", DAY, "09:00", 2)["error"], "UNKNOWN_PRODUCT")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", "15/07/2027", "09:00", 2)["error"], "BAD_DATE")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", "2027-02-30", "09:00", 2)["error"], "BAD_DATE")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", DAY, "9am", 2)["error"], "BAD_TIME")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", DAY, "11:00", 2)["error"], "NO_SUCH_DEPARTURE")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 0)["error"], "BAD_NUMBER")
        self.assertEqual(inv.place_hold(A, "BL-CRUISE-4H", "2027-12-01", "09:00", 2)["error"], "NO_SUCH_DEPARTURE")
        self.assertTrue(inv.place_hold(A, "bl-cruise-4h", DAY, "9:00", 2)["ok"])   # tolerant of case and 9:00
        off = inv.check_availability(A, "BL-CRUISE-4H", "2027-12-01", 2)
        self.assertFalse(off["in_season"])
        self.assertTrue(all(not x["ok"] for x in self.log_lines()[:7]))

    def test_unexpected_faults_are_logged_too(self) -> None:
        def broken(now: float) -> dict:
            raise RuntimeError("simulated fault")
        with self.assertRaises(RuntimeError):
            self.inv._run(A, "place_hold", {"product_id": "BL-CRUISE-4H"}, broken)
        last = self.log_lines()[-1]
        self.assertEqual((last["tool"], last["ok"], last["error"]), ("place_hold", False, "INTERNAL_ERROR"))
        self.assertTrue(self.inv.check_availability(A, "BL-CRUISE-4H", DAY, 1)["ok"])   # the transaction was rolled back cleanly


class ExpiryWithTwoSecondTTL(Base):
    ttl = 2

    def test_holds_expire_on_the_server(self) -> None:
        inv = self.inv
        lone = inv.place_hold(A, "MK-CART-90", "2027-07-14", "16:00", 4)     # the agent never comes back
        asked = inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 4)          # staff never answers
        self.assertTrue(lone["ok"] and asked["ok"])
        rc = inv.request_confirmation(A, asked["hold_id"])
        self.assertEqual(rc["status"], "pending_staff_confirmation")
        self.assertEqual(self.free("MK-CART-90", "2027-07-14", "16:00"), 8)
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "09:00"), 36)
        self.assertLessEqual(inv.get_hold(A, lone["hold_id"])["seconds_left"], 2)

        time.sleep(2.3)

        self.assertEqual(inv.get_hold(A, lone["hold_id"])["status"], "expired")
        self.assertEqual(inv.get_hold(A, asked["hold_id"])["status"], "expired")
        self.assertEqual(self.free("MK-CART-90", "2027-07-14", "16:00"), 12)
        self.assertEqual(self.free("BL-CRUISE-4H", DAY, "09:00"), 40)
        late = inv.request_confirmation(A, lone["hold_id"])
        self.assertEqual(late["error"], "HOLD_NOT_ACTIVE")
        staff = inv.decide(rc["confirmation_id"], by="KR", approve=True)
        self.assertEqual(staff["error"], "NOT_PENDING")
        self.assertEqual(inv.pending_confirmations(), [])
        # expired holds no longer count toward the caller's active-hold limit
        self.assertTrue(inv.place_hold(A, "BL-CRUISE-4H", DAY, "14:00", 4)["ok"])


class CutoffBeforeDeparture(Base):
    ttl = 7 * 24 * 3600

    def test_hold_never_runs_into_the_no_refund_window(self) -> None:
        now = datetime(2027, 7, 14, 10, 0, tzinfo=timezone.utc).timestamp()
        self.inv.clock = lambda: now
        late = self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 2)      # departs in under 48 hours
        self.assertEqual(late["error"], "TOO_LATE_TO_HOLD")
        ok = self.inv.place_hold(A, "BL-CRUISE-4H", "2027-07-20", "09:00", 2)
        # 09:00 AKDT on July 20 is 17:00 UTC; minus 48 hours is July 18, 17:00 UTC, sooner than now + 7 days
        self.assertEqual(ok["expires_at"], "2027-07-18T17:00:00Z")


class PhantomInventoryGuards(Base):
    extra = {"max_new_holds_per_caller_per_day": 6}

    def test_per_caller_limit_blocks_phantom_inventory(self) -> None:
        inv = self.inv
        for dep in ("08:00", "13:00"):
            self.assertTrue(inv.place_hold(A, "HK-PADDLE-3H", "2027-07-20", dep, 2)["ok"])
        self.assertTrue(inv.place_hold(A, "BL-CRUISE-4H", "2027-07-20", "09:00", 2)["ok"])
        blocked = inv.place_hold(A, "BL-CRUISE-4H", "2027-07-20", "14:00", 2)
        self.assertEqual(blocked["error"], "HOLD_LIMIT_REACHED")
        self.assertEqual(self.free("BL-CRUISE-4H", "2027-07-20", "14:00"), 40)   # nothing was taken
        self.assertTrue(inv.place_hold(B, "BL-CRUISE-4H", "2027-07-20", "14:00", 2)["ok"])   # other callers unaffected

    def test_duplicate_and_oversized_holds(self) -> None:
        self.assertTrue(self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 4)["ok"])
        self.assertEqual(self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 4)["error"], "DUPLICATE_HOLD")
        self.assertEqual(self.inv.place_hold(B, "BL-CRUISE-4H", DAY, "09:00", 13)["error"], "TOO_MANY_SEATS")

    def test_holds_count_against_capacity(self) -> None:
        inv = self.inv
        for i in range(4):
            self.assertTrue(inv.place_hold(f"agent:{i}", "BL-CRUISE-4H", DAY, "09:00", 10)["ok"])
        full = inv.place_hold("agent:late", "BL-CRUISE-4H", DAY, "09:00", 1)
        self.assertEqual(full["error"], "NOT_ENOUGH_SEATS")
        self.assertEqual(full["available"], 0)
        first = inv.list_holds()[0]
        inv.release_hold(first["caller"], first["hold_id"])
        self.assertTrue(inv.place_hold("agent:late", "BL-CRUISE-4H", DAY, "09:00", 1)["ok"])

    def test_hold_and_release_churn_is_rate_limited(self) -> None:
        for _ in range(6):
            h = self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 2)
            self.assertTrue(h["ok"], h)
            self.inv.release_hold(A, h["hold_id"])
        self.assertEqual(self.inv.place_hold(A, "BL-CRUISE-4H", DAY, "09:00", 2)["error"], "RATE_LIMITED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
