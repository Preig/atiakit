"""MCP layer tests. The first class needs nothing extra; the rest are skipped unless the mcp package is installed.

    python -m unittest -v          (or: python -m pytest)

With mcp installed, this starts server.py over stdio as a real MCP client would (Claude Desktop,
Claude Code, Gemini CLI) and calls the tools through the protocol. No network is used.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server  # noqa: E402

HAVE_MCP = server.MCPServer is not None
EXPECTED = {"search_products", "check_availability", "place_hold", "get_hold", "release_hold",
            "request_confirmation", "get_trip_record", "put_trip_record"}


def payload(result) -> dict:
    """Tool results arrive as structured content (newer SDKs) or as JSON text (older SDKs)."""
    sc = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError(f"no payload in {result!r}")


class LocalOnly(unittest.TestCase):
    def test_refuses_to_bind_beyond_localhost(self) -> None:
        self.assertEqual(server.main(["--host", "0.0.0.0", "--transport", "streamable-http"]), 2)
        self.assertEqual(server.main(["--host", "192.168.1.20", "--dry-run"]), 2)

    def test_dry_run_needs_no_network_or_keys(self) -> None:
        tmp = tempfile.mkdtemp(prefix="trip-mcp-dry-test-")
        try:
            self.assertEqual(server.main(["--dry-run", "--db", os.path.join(tmp, "d.sqlite3"), "--log", os.path.join(tmp, "l.jsonl")]), 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(HAVE_MCP, "mcp package not installed (pip install -r requirements.txt)")
class WithMcpSdk(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="trip-mcp-sdk-")
        self.db, self.log = os.path.join(self.tmp, "s.sqlite3"), os.path.join(self.tmp, "calls.jsonl")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tools_register(self) -> None:
        import anyio
        from inventory import Config, Inventory
        inv = Inventory(Config(db_path=self.db, log_path=self.log))
        try:
            tools = anyio.run(server.build_server(inv).list_tools)
            self.assertEqual({t.name for t in tools}, EXPECTED)
        finally:
            inv.close()

    def test_stdio_round_trip(self) -> None:
        import anyio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=[str(HERE / "server.py"), "--transport", "stdio", "--db", self.db, "--log", self.log, "--caller-id", "agent:stdio-test"],
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        async def go() -> dict:
            out: dict = {}
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    out["tools"] = {t.name for t in (await session.list_tools()).tools}
                    found = payload(await session.call_tool("search_products", {"date": "2027-07-15", "youngest_age": 6}))
                    out["fits"] = {p["product_id"]: p["age_fit"]["fits"] for p in found["products"]}
                    hold = payload(await session.call_tool("place_hold", {"product_id": "BL-CRUISE-4H", "date": "2027-07-15", "departure": "09:00", "seats": 4}))
                    out["hold"] = hold
                    out["ask"] = payload(await session.call_tool("request_confirmation", {"hold_id": hold["hold_id"]}))
                    bad = dict(json.loads((HERE / "trip-record.example.json").read_text(encoding="utf-8")), notes="mail someone@example.com")
                    out["bad_record"] = payload(await session.call_tool("put_trip_record", {"record": bad}))
            return out

        out = anyio.run(go)
        self.assertEqual(out["tools"], EXPECTED)
        self.assertEqual(out["fits"]["HK-PADDLE-3H"], False)
        self.assertEqual(out["hold"]["status"], "active")
        self.assertTrue(out["hold"]["expires_at"].endswith("Z"))
        self.assertEqual(out["ask"]["status"], "pending_staff_confirmation")
        self.assertEqual(out["bad_record"]["error"], "INVALID_RECORD")
        lines = [json.loads(x) for x in Path(self.log).read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(x["caller"] == "agent:stdio-test" for x in lines))
        self.assertEqual([x["tool"] for x in lines], ["search_products", "place_hold", "request_confirmation", "put_trip_record"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
