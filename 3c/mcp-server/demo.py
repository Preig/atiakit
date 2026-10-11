#!/usr/bin/env python3
"""Watch a scripted agent use the trip-record tools. No mcp package, no network, no keys.

    python demo.py              # full walk-through in a throwaway database
    python demo.py --fast       # skip the 3-second expiry demonstration

The same steps a Claude, ChatGPT or Gemini agent would take through server.py:
search, hold, review, change (release and re-hold), request confirmation, and then a
person at the business confirms. FICTIONAL TEACHING DATA throughout.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import Config, Inventory  # noqa: E402

AGENT = "agent:demo-planner"


def say(step: str, text: str = "") -> None:
    print(f"\n== {step}")
    if text:
        print(text)


def show(obj: dict, keys: list[str]) -> None:
    print("   " + json.dumps({k: obj[k] for k in keys if k in obj}))


def base_record(version: int) -> dict:
    return {
        "record_id": "TR-DEMO-0714", "version": version, "updated_at": "2026-10-10T18:00:00Z",
        "notes": "FICTIONAL TEACHING RECORD. DRAFT - PENDING STAFF REVIEW.",
        "party": {"count": 4, "age_bands": [{"band": "18-64", "count": 2}, {"band": "6-7", "count": 1}, {"band": "8-9", "count": 1}]},
        "dates": {"arrive": "2027-07-14", "depart": "2027-07-16"},
        "budget_band": "500_to_1000_usd",
        "preferences": {"interests": ["wildlife", "glaciers", "sled dogs"], "pace": "relaxed", "has_car": True},
        "shortlisted": [], "rejected": [], "holds": [], "open_questions": [],
        "consent": {"purpose": "trip_planning", "traveler_reviewed": False, "agent_may_place_holds": True,
                    "agent_may_confirm": False, "human_contact_offered": True, "retention_days": 30},
    }


def hold_entry(h: dict) -> dict:
    keys = ("hold_id", "product_id", "date", "departure", "seats", "status", "placed_at", "expires_at", "confirmation_id")
    return {k: h[k] for k in keys if k in h}


def run(fast: bool) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="trip-mcp-demo-"))
    inv = Inventory(Config(db_path=str(tmp / "demo.sqlite3"), log_path=str(tmp / "calls.jsonl")))
    print("Scripted agent demo. FICTIONAL DATA: Bay Light Day Cruises, Seward, Mile 12 Kennel, Harbor Kayak Co.")
    print("Party: 2 adults and 2 children (age bands 6-7 and 8-9), July 14 to 16, 2027. No names anywhere.")

    say("1. search_products(date=2027-07-15, party_size=4, youngest_age=6)")
    res = inv.search_products(AGENT, date="2027-07-15", party_size=4, youngest_age=6)
    for p in res["products"]:
        fit = p["age_fit"]["fits"]
        seats = ", ".join(f"{d['departure']} {d['available']} free" for d in p.get("availability", []))
        print(f"   {p['product_id']:<13} age fit: {'yes' if fit else 'NO '}  {seats}")

    say("2. place_hold(BL-CRUISE-4H, 2027-07-15, 14:00, seats=4)")
    h1 = inv.place_hold(AGENT, "BL-CRUISE-4H", "2027-07-15", "14:00", 4, record_id="TR-DEMO-0714")
    show(h1, ["hold_id", "status", "expires_at", "ttl_seconds"])
    print("   " + h1["what_this_means"])

    say("3. put_trip_record(version 1): short list, rejected kayak with the reason, the hold")
    rec = base_record(1)
    rec["shortlisted"] = [{"product_id": "BL-CRUISE-4H", "date": "2027-07-15", "departure": "14:00",
                           "reason": "Minimum age 4 fits children aged 6 and 9. Heated cabin; runs in rain.",
                           "source_fact_ids": ["BL-MIN-AGE", "BL-CABIN", "BL-RAIN"]}]
    rec["rejected"] = [{"product_id": "HK-PADDLE-3H", "rule": "min_age", "reason": "Minimum age 12. The children are 6 and 9.", "source_fact_ids": ["HK-MIN-AGE"]}]
    rec["holds"] = [hold_entry(h1)]
    rec["open_questions"] = [{"id": "Q1", "question": "Lunch is not included. Where can a family eat near the harbor afterward?", "for": "owner", "status": "open"}]
    show(inv.put_trip_record(AGENT, rec), ["ok", "record_id", "version"])

    say("4. The traveler reviews and changes: mornings are better. release_hold, then place_hold at 09:00")
    show(inv.release_hold(AGENT, h1["hold_id"]), ["hold_id", "status", "message"])
    h2 = inv.place_hold(AGENT, "BL-CRUISE-4H", "2027-07-15", "09:00", 4, record_id="TR-DEMO-0714")
    show(h2, ["hold_id", "status", "expires_at"])

    say("5. put_trip_record(version 2) with the change recorded")
    rec = inv.get_trip_record(AGENT, "TR-DEMO-0714")["record"]
    rec["version"] = 2
    rec["consent"]["traveler_reviewed"] = True
    rec["shortlisted"][0]["departure"] = "09:00"
    rec["rejected"].append({"product_id": "BL-CRUISE-4H", "date": "2027-07-15", "departure": "14:00", "rule": "preference",
                            "reason": "The family changed to the morning departure after review.", "source_fact_ids": ["BL-DEPARTURES"]})
    rec["holds"].append(hold_entry(h2))
    show(inv.put_trip_record(AGENT, rec), ["ok", "record_id", "version"])

    say("6. A stale write is refused (an agent that read version 1 sends its own version 2)")
    stale = dict(rec, version=2)
    show(inv.put_trip_record(AGENT, stale), ["ok", "error", "message"])

    say("7. A record with personal data is refused, and nothing is saved")
    bad = dict(rec, version=3, notes="Lead guest email: someone@example.com")
    out = inv.put_trip_record(AGENT, bad)
    show(out, ["ok", "error", "message"])
    for e in out.get("errors", [])[:3]:
        print(f"   - {e['path']}: {e['message']}")

    say("8. request_confirmation: the agent asks, a person decides")
    rc = inv.request_confirmation(AGENT, h2["hold_id"], note="Family of four, reviewed the plan, prefers mornings.")
    show(rc, ["hold_id", "status", "confirmation_id", "message"])

    say("9. What a person at the business sees (python admin.py pending)")
    for item in inv.pending_confirmations():
        print(f"   {item['confirmation_id']}  {item['product_id']} {item['date']} {item['departure']}  seats {item['seats']}  "
              f"{item['minutes_left']} minutes left  note: {item['note']}")

    say("10. The person confirms (python admin.py confirm <id> --by KR)")
    show(inv.decide(rc["confirmation_id"], by="KR", approve=True), ["confirmation_id", "status", "decided_by"])
    show(inv.get_hold(AGENT, h2["hold_id"]), ["hold_id", "status"])

    say("11. Phantom inventory guard: a second agent tries to hold four departures")
    for dep in ("08:00", "13:00"):
        r = inv.place_hold("agent:greedy", "HK-PADDLE-3H", "2027-07-20", dep, 2)
        print(f"   HK-PADDLE-3H {dep}: {r.get('status') or r.get('error')}")
    for dep in ("09:00", "14:00"):
        r = inv.place_hold("agent:greedy", "BL-CRUISE-4H", "2027-07-20", dep, 2)
        print(f"   BL-CRUISE-4H {dep}: {r.get('status') or r.get('error')} {r.get('message', '')}")

    if not fast:
        say("12. Expiry: a hold with a 3-second lifetime, and nobody comes back")
        short = Inventory(Config(db_path=str(tmp / "demo.sqlite3"), log_path=str(tmp / "calls.jsonl"), hold_ttl_seconds=3))
        h3 = short.place_hold("agent:wanderer", "MK-CART-90", "2027-07-14", "16:00", 4)
        print(f"   placed {h3['hold_id']}, seats free now: {short.check_availability('agent:wanderer', 'MK-CART-90', '2027-07-14', 4)['departures'][2]['available']}")
        time.sleep(3.2)
        print(f"   after 3 seconds: {short.get_hold('agent:wanderer', h3['hold_id'])['status']}, seats free: "
              f"{short.check_availability('agent:wanderer', 'MK-CART-90', '2027-07-14', 4)['departures'][2]['available']}")
        short.close()

    say("13. Hold-to-book numbers (python admin.py stats)")
    print("   " + json.dumps({k: v for k, v in inv.stats().items() if k != "ok"}))
    lines = (tmp / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    print(f"\nEvery call was logged: {len(lines)} lines in {tmp / 'calls.jsonl'}")
    inv.close()
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fast", action="store_true", help="skip the expiry demonstration")
    sys.exit(run(ap.parse_args().fast))
