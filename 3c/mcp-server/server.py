#!/usr/bin/env python3
"""Trip-record MCP server scaffold (tool 3.c, ATIA AI Take-Home Kit, Alaska SBDC).

An MCP server over a MOCK SQLite inventory for the fictional Bay Light Day Cruises, Seward,
and two fictional partners. An AI agent (Claude, ChatGPT, Gemini or any MCP client) can search,
check availability, place a reversible hold that expires on its own, review and change it,
and ask a person at the business to confirm. The agent can never confirm, book or charge.

    python server.py --dry-run                       # no network, no keys: build the server, list tools, run one smoke call
    python server.py                                 # stdio (Claude Desktop, Claude Code, Gemini CLI launch it this way)
    python server.py --transport streamable-http     # http://127.0.0.1:8000/mcp

WARNING: this scaffold has NO authentication. Run it on your own computer only. Do not expose it
to the internet or a shared network: anyone who can reach it can place and release holds.
It refuses to bind to anything but 127.0.0.1, localhost or ::1.

All business rules live in inventory.py, which needs only the Python standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import Config, Inventory  # noqa: E402

# MCP Python SDK import chain. v2 renamed FastMCP to MCPServer; v1 still works through the last fallback.
MCPServer: Any = None
SDK_GENERATION = 0
SDK_IMPORT_ERROR = ""
try:
    from mcp.server.mcpserver import MCPServer  # type: ignore[no-redef]  # v2, as in the migration guide
    SDK_GENERATION = 2
except ImportError:
    try:
        from mcp.server import MCPServer  # type: ignore[no-redef]  # v2, as in the PyPI quickstart
        SDK_GENERATION = 2
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]  # v1
            SDK_GENERATION = 1
        except ImportError as exc:
            SDK_IMPORT_ERROR = str(exc)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

INSTRUCTIONS = """Trip-record server for Bay Light Day Cruises, Seward (FICTIONAL TEACHING DATA) and two partners.
Workflow: search_products, then check_availability, then place_hold (reversible, expires on its own),
then let the traveler review the plan in a trip record (get_trip_record / put_trip_record).
To change a plan, release_hold and place a new hold. When the traveler is happy, call request_confirmation:
a person at the business confirms or declines. You cannot confirm, book or charge.
Never send names, emails, phone numbers, payment details, ID numbers or health details: the trip record
describes the party by counts and age bands only. Cite fact_ids for every reason you give.
If a fact is in not_supplied, ask the business; do not guess. Never quote a price: prices are not in the facts.
Safety calls (weather, sea state, wildlife) stay with the captain and crew."""


def build_server(inv: Inventory) -> Any:
    """Register the eight tools on an MCP server object. Needs the mcp package."""
    if MCPServer is None:
        raise RuntimeError("The mcp package is not installed. " + SDK_IMPORT_ERROR)
    server = MCPServer("baylight-trip-record", instructions=INSTRUCTIONS)
    who = inv.config.caller_id   # one caller per server process; in production, take it from authentication

    @server.tool()
    def search_products(query: str = "", date: str | None = None, party_size: int | None = None,
                        youngest_age: int | None = None) -> dict:
        """Find tours and partner activities. Returns facts with fact_ids, minimum ages, departures,
        what is not supplied, and (if date is given, YYYY-MM-DD) seats free per departure.
        youngest_age filters by minimum age. Never pass names or contact details."""
        return inv.search_products(who, query=query, date=date, party_size=party_size, youngest_age=youngest_age)

    @server.tool()
    def check_availability(product_id: str, date: str, party_size: int = 1) -> dict:
        """Seats free per departure for one product on one date (YYYY-MM-DD). Held seats count against capacity."""
        return inv.check_availability(who, product_id=product_id, date=date, party_size=party_size)

    @server.tool()
    def place_hold(product_id: str, date: str, departure: str, seats: int, record_id: str | None = None) -> dict:
        """Place a reversible, time-limited hold. Returns hold_id and expires_at. Nothing is booked or charged.
        The hold expires on its own. departure is 24-hour HH:MM. record_id (optional) links it to a trip record."""
        return inv.place_hold(who, product_id=product_id, date=date, departure=departure, seats=seats, record_id=record_id)

    @server.tool()
    def get_hold(hold_id: str) -> dict:
        """Current status of one of your holds: active, pending_staff_confirmation, confirmed, released, expired or declined."""
        return inv.get_hold(who, hold_id=hold_id)

    @server.tool()
    def release_hold(hold_id: str) -> dict:
        """Release one of your holds. The seats go back on sale. Use it when the traveler changes the plan."""
        return inv.release_hold(who, hold_id=hold_id)

    @server.tool()
    def request_confirmation(hold_id: str, note: str = "") -> dict:
        """Ask a person at the business to confirm an active hold. This does NOT confirm or book anything.
        Call it only after the traveler has reviewed the plan. note: optional, under 280 characters, no personal data."""
        return inv.request_confirmation(who, hold_id=hold_id, note=note)

    @server.tool()
    def get_trip_record(record_id: str) -> dict:
        """Read a trip record (party as counts and age bands, dates, short list, rejected options, holds, open questions).
        Hold status is refreshed from the live inventory."""
        return inv.get_trip_record(who, record_id=record_id)

    @server.tool()
    def put_trip_record(record: dict) -> dict:
        """Save the next version of a trip record. It is checked against trip-record.schema.json and scanned for
        personal data; anything with names, contact details, payment data or IDs is rejected and nothing is saved.
        version has to be the stored version plus 1 (or any version for a new record)."""
        return inv.put_trip_record(who, record=record)

    return server


def make_inventory(args: argparse.Namespace) -> Inventory:
    cfg = Config.from_env(db_path=args.db, log_path=args.log, hold_ttl_seconds=args.ttl,
                          max_active_holds_per_caller=args.max_holds, caller_id=args.caller_id)
    return Inventory(cfg)


def dry_run(args: argparse.Namespace) -> int:
    tmp = tempfile.mkdtemp(prefix="trip-mcp-dry-")
    args.db, args.log = args.db or os.path.join(tmp, "dry.sqlite3"), args.log or os.path.join(tmp, "calls.jsonl")
    inv = make_inventory(args)
    out: dict[str, Any] = {"mode": "dry-run (no network, no keys)", "db": inv.config.db_path, "log": inv.config.log_path}
    smoke = inv.check_availability(inv.config.caller_id, "BL-CRUISE-4H", "2027-07-15", 4)
    out["smoke_call"] = {"check_availability BL-CRUISE-4H 2027-07-15": [(d["departure"], d["available"]) for d in smoke.get("departures", [])]}
    if MCPServer is None:
        out["mcp_sdk"] = "NOT INSTALLED. Business logic works; to serve MCP, run: pip install -r requirements.txt"
        print(json.dumps(out, indent=2))
        inv.close()
        return 0
    server = build_server(inv)
    import anyio
    tools = anyio.run(server.list_tools)
    out["mcp_sdk"] = f"installed (generation {SDK_GENERATION}, {type(server).__module__}.{type(server).__name__})"
    out["tools"] = [t.name for t in tools]
    print(json.dumps(out, indent=2))
    inv.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Trip-record MCP server scaffold over a mock inventory (fictional data, no auth, local only).")
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1", help="only 127.0.0.1, localhost or ::1 are allowed")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--db", default=None, help="SQLite file (default data/trip_mcp.sqlite3, or env TRIP_MCP_DB)")
    ap.add_argument("--log", default=None, help="JSONL call log (default logs/calls.jsonl, or env TRIP_MCP_LOG)")
    ap.add_argument("--ttl", type=int, default=None, help="hold lifetime in seconds (default 86400, or env TRIP_MCP_HOLD_TTL_SECONDS)")
    ap.add_argument("--max-holds", type=int, default=None, help="active holds per caller (default 3, or env TRIP_MCP_MAX_ACTIVE_HOLDS)")
    ap.add_argument("--caller-id", default=None, help="name for this client in the log (default local-agent, or env TRIP_MCP_CALLER_ID)")
    ap.add_argument("--dry-run", "--check", dest="dry_run", action="store_true", help="build everything, list tools, run one smoke call, exit")
    args = ap.parse_args(argv)

    if args.host not in LOCAL_HOSTS:
        print(f"Refusing to bind to {args.host}. This scaffold has no authentication; it serves 127.0.0.1 only.", file=sys.stderr)
        return 2
    if args.dry_run:
        return dry_run(args)
    if MCPServer is None:
        print("The mcp package is not installed. Run: pip install -r requirements.txt\n(or try: python server.py --dry-run)", file=sys.stderr)
        return 1

    inv = make_inventory(args)
    server = build_server(inv)
    # stdout belongs to the MCP protocol in stdio mode, so everything human-readable goes to stderr.
    print(f"baylight-trip-record: transport={args.transport} db={inv.config.db_path} log={inv.config.log_path} "
          f"hold_ttl={inv.config.hold_ttl_seconds}s sdk_generation={SDK_GENERATION}", file=sys.stderr)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        print(f"Serving http://{args.host}:{args.port}/mcp (local only, no auth). Ctrl+C to stop.", file=sys.stderr)
        if SDK_GENERATION >= 2:
            server.run(transport="streamable-http", host=args.host, port=args.port)
        else:
            server.settings.host, server.settings.port = args.host, args.port
            server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    sys.exit(main())
