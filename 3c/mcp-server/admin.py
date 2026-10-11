#!/usr/bin/env python3
"""Staff console for the trip-record MCP scaffold. This is what a person at the business uses.

    python admin.py pending                      # holds waiting for a person, soonest expiry first
    python admin.py confirm C-ABCDEFGHJK --by KR  # a person confirms (only before the hold expires)
    python admin.py decline C-ABCDEFGHJK --by KR --note "Marine warning forecast"
    python admin.py holds [--all]                # live holds (or every hold ever placed)
    python admin.py sweep                        # expire overdue holds now (every call does this anyway)
    python admin.py stats                        # holds placed, by status, hold-to-book rate
    python admin.py log [--tail 20]              # the JSONL call log
    python admin.py record TR-DEMO-0714          # show a stored trip record
    python admin.py load-example                 # store trip-record.example.json (fictional) for practice
    python admin.py reset --yes                  # delete the mock database and the log, start fresh

Standard library only. Uses the same database and log as server.py (env TRIP_MCP_DB / TRIP_MCP_LOG or --db / --log).
In a real system, "confirm" is where the booking platform creates the booking and takes payment
through its own checkout. The agent never sees payment data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import Config, Inventory  # noqa: E402


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def _table(rows: list[dict], cols: list[str]) -> str:
    if not rows:
        return "(none)"
    widths = {c: max(len(c), *(len(_cell(r.get(c))) for r in rows)) for c in cols}
    line = "  ".join(c.ljust(widths[c]) for c in cols).rstrip()
    out = [line, "  ".join("-" * widths[c] for c in cols)]
    for r in rows:
        out.append("  ".join(_cell(r.get(c)).ljust(widths[c]) for c in cols).rstrip())
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Staff console: confirm or decline holds an agent asked about. Fictional mock data.")
    ap.add_argument("--db", default=None)
    ap.add_argument("--log", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    for name in ("confirm", "decline"):
        p = sub.add_parser(name)
        p.add_argument("confirmation_id")
        p.add_argument("--by", required=True, help="initials or role of the person deciding")
        p.add_argument("--note", default="", help="optional, no personal data")
    p = sub.add_parser("holds")
    p.add_argument("--all", action="store_true")
    sub.add_parser("sweep")
    sub.add_parser("stats")
    p = sub.add_parser("log")
    p.add_argument("--tail", type=int, default=20)
    p = sub.add_parser("record")
    p.add_argument("record_id")
    sub.add_parser("load-example")
    p = sub.add_parser("reset")
    p.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    cfg = Config.from_env(db_path=args.db, log_path=args.log)

    if args.cmd == "reset":
        if not args.yes:
            print("This deletes the mock database and the call log. Run again with --yes to do it.")
            return 1
        for f in (cfg.db_path, cfg.db_path + "-wal", cfg.db_path + "-shm", cfg.log_path):
            if os.path.exists(f):
                os.remove(f)
        print("Mock database and log deleted. They are rebuilt with fictional data on the next run.")
        return 0

    if args.cmd == "log":
        if not os.path.exists(cfg.log_path):
            print("(no log yet)")
            return 0
        with open(cfg.log_path, encoding="utf-8") as fh:
            lines = fh.readlines()[-args.tail:]
        sys.stdout.write("".join(lines))
        return 0

    inv = Inventory(cfg)
    try:
        if args.cmd == "pending":
            items = inv.pending_confirmations()
            print("Holds waiting for a person (FICTIONAL MOCK DATA). Confirm or decline before they expire.\n")
            print(_table(items, ["confirmation_id", "hold_id", "product_id", "date", "departure", "seats", "minutes_left", "record_id", "note"]))
        elif args.cmd in ("confirm", "decline"):
            res = inv.decide(args.confirmation_id, by=args.by, approve=(args.cmd == "confirm"), note=args.note)
            if not res.get("ok"):
                print(f"Not done: {res.get('message')}")
                return 1
            print(f"{res['confirmation_id']} {res['status']} by {res['decided_by']} (hold {res['hold_id']}).")
            if args.cmd == "confirm":
                print("Mock only. In a real system, create the booking in your booking platform now; it takes payment in its own checkout.")
        elif args.cmd == "holds":
            print(_table(inv.list_holds(include_closed=args.all), ["hold_id", "caller", "product_id", "date", "departure", "seats", "status", "expires_at"]))
        elif args.cmd == "sweep":
            print(f"{inv.sweep()} hold(s) expired.")
        elif args.cmd == "stats":
            print(json.dumps(inv.stats(), indent=2))
        elif args.cmd == "record":
            res = inv.get_trip_record("staff", args.record_id)
            print(json.dumps(res, indent=2) if res.get("ok") else f"Not found: {res.get('message')}")
            return 0 if res.get("ok") else 1
        elif args.cmd == "load-example":
            rec = json.loads((HERE / "trip-record.example.json").read_text(encoding="utf-8"))
            res = inv.put_trip_record("staff", rec)
            print(json.dumps(res, indent=2))
            return 0 if res.get("ok") else 1
    finally:
        inv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
