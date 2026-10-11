# Trip-record MCP server (teaching scaffold)

Tool 3.c of the ATIA AI Take-Home Kit (ATIA 2026 Annual Convention, Alaska SBDC).
Web page: https://preig.github.io/atiakit/3c/

**FICTIONAL TEACHING DATA.** Bay Light Day Cruises, Seward, Mile 12 Kennel and Harbor Kayak Co. are fictional.
Mile 12 Kennel's departure times and both partners' capacities and season dates are MOCK values invented for the tests;
they are not approved facts. (Harbor Kayak's 8:00 and 13:00 departures are approved facts.)

> **Warning: this server has no authentication.** Run it on your own computer only. Do not put it on the
> internet or on a shared network: anyone who can reach it can place and release holds. It refuses to
> bind to anything except 127.0.0.1, localhost or ::1. (Recommendation, and a firm one.)

## What this is, in plain words

AI agents are starting to shop for travelers inside Claude, ChatGPT and Gemini. An agent that cannot
place a **reversible hold** will not put a four-person Alaska trip on hold while the family thinks it over.
It will book something it can hold instead.

This folder is a small working model of the pieces a booking system needs before an agent can place your trip:

- an **MCP server** (MCP is the open protocol Claude, ChatGPT and Gemini agents use to call outside tools);
- a **mock inventory** in a local SQLite file: Bay Light's 9:00 and 14:00 departures (capacity 40) plus partner slots;
- **holds that expire on their own**, count against capacity, and are limited per caller;
- a **trip record** that describes the party by counts and age bands, with no names, contact details or payment data;
- a **staff console** (`admin.py`): the agent can only ask; a person at the business confirms;
- a **log** of every call, one JSON line each.

What it is not: it is not connected to any booking platform, it takes no payments, it has no login, and it is
not ready for production. The months in this rung are in platform integration, hold rules and policy, not in this code.

**A six-person operator does not need to run this.** Your move is one question to your booking platform
(on the web page). This scaffold is for a larger operator, a group of members, or ATIA to hand to a developer
as a working specification.

## Try it in five minutes (no keys, no internet, nothing to install)

You need Python 3.10 or newer (python.org). On a Mac, type `python3` where this says `python`.

1. Unzip `trip-record-mcp.zip` and open a terminal in the `trip-record-mcp` folder.
2. Watch a scripted agent plan the fictional family's trip:

   ```
   python demo.py
   ```

   It searches, holds the 14:00 cruise, writes a trip record, changes to 9:00 (release and re-hold),
   gets refused for a stale write and for personal data, asks for confirmation, and a person confirms.
   It also shows a hold expiring after three seconds and a greedy agent being stopped.
3. Run the tests (about 5 seconds; two are skipped until the MCP SDK is installed):

   ```
   python -m unittest -v
   ```

4. Check a trip record file:

   ```
   python validate_record.py trip-record.example.json
   ```

## Connect a real AI client

Install the MCP Python SDK in a virtual environment inside this folder:

```
python -m venv .venv
.venv\Scripts\activate            (Windows)
source .venv/bin/activate         (Mac or Linux)
pip install -r requirements.txt
python server.py --dry-run
```

`--dry-run` needs no network and no keys. It builds the server, lists the eight tools and makes one test call.
In the examples below, replace `/path/to/trip-record-mcp` with your folder. On Windows the Python path is
`C:\\path\\to\\trip-record-mcp\\.venv\\Scripts\\python.exe` (double backslashes inside JSON).
Client settings change often; check your client's current documentation if a snippet does not work.

### Claude Desktop

Settings, Developer, Edit Config opens `claude_desktop_config.json`. Add, then restart Claude Desktop:

```json
{
  "mcpServers": {
    "baylight-trip-record": {
      "command": "/path/to/trip-record-mcp/.venv/bin/python",
      "args": ["/path/to/trip-record-mcp/server.py"],
      "env": { "TRIP_MCP_CALLER_ID": "claude-desktop" }
    }
  }
}
```

### Claude Code

```
claude mcp add baylight-trip-record -- /path/to/trip-record-mcp/.venv/bin/python /path/to/trip-record-mcp/server.py
```

Or put the same `mcpServers` block as above in a `.mcp.json` file at the root of a project.
Over HTTP instead: start `python server.py --transport streamable-http`, then
`claude mcp add --transport http baylight-trip-record http://127.0.0.1:8000/mcp`.

### Gemini CLI

In `~/.gemini/settings.json` (or `.gemini/settings.json` in a project):

```json
{
  "mcpServers": {
    "baylight-trip-record": {
      "command": "/path/to/trip-record-mcp/.venv/bin/python",
      "args": ["/path/to/trip-record-mcp/server.py"],
      "env": { "TRIP_MCP_CALLER_ID": "gemini-cli" }
    }
  }
}
```

Over HTTP: `"baylight-trip-record": { "httpUrl": "http://127.0.0.1:8000/mcp" }`.

### Other local clients (for example Codex CLI)

Most local clients take the same three things: a command (the `.venv` Python), arguments (`server.py`) and
optional environment variables. Codex CLI uses `~/.codex/config.toml`:

```toml
[mcp_servers.baylight-trip-record]
command = "/path/to/trip-record-mcp/.venv/bin/python"
args = ["/path/to/trip-record-mcp/server.py"]
```

### ChatGPT and Claude on the web

These connect only to remote servers over HTTPS with authentication. This scaffold has neither, on purpose.
Making it remote is a developer job: HTTPS, OAuth sign-in for each agent, and a security review.

### A prompt to try once connected

> Using the baylight-trip-record tools, plan July 14 to 16, 2027 for two adults and two children aged 6 and 9.
> Search, hold the cruise departure that fits, and write a trip record whose reasons cite fact ids.
> Show me the plan and wait for my review before you request confirmation. Do not ask for names or contact details.

Then play the person at the business:

```
python admin.py pending
python admin.py confirm C-XXXXXXXXXX --by KR
```

## The eight tools an agent sees

| Tool | What it does | Guard rails |
|---|---|---|
| `search_products` | Products with facts (each with a `fact_id`), minimum ages, departures, what is not supplied, seats free on a date | No prices: they are not in the approved facts. `youngest_age` marks what fits. |
| `check_availability` | Seats free per departure for one product and date | Held seats count against capacity |
| `place_hold` | Reversible hold; returns `hold_id` and `expires_at` | Expires after the TTL (default 24 h) or at the free-cancellation cutoff, whichever is sooner. Per-caller limits. Minimum age checked against a linked trip record. |
| `get_hold` | Status of one of your holds | Callers see only their own holds |
| `release_hold` | Give the seats back | Used for every change: release, then hold again |
| `request_confirmation` | Ask a person to confirm an active hold | Creates a pending staff confirmation only. Nothing is booked or charged. |
| `get_trip_record` | Read a trip record | Hold status is refreshed from the live inventory |
| `put_trip_record` | Save the next version of a trip record | Checked against `trip-record.schema.json` and scanned for personal data; version has to be the stored version plus 1 |

There is no confirm tool for agents. Errors come back as `{"ok": false, "error": "CODE", "message": "..."}`
so an agent can explain them to the traveler.

## What a person at the business sees

```
> python admin.py pending
Holds waiting for a person (FICTIONAL MOCK DATA). Confirm or decline before they expire.

confirmation_id  hold_id       product_id    date        departure  seats  minutes_left  record_id     note
---------------  ------------  ------------  ----------  ---------  -----  ------------  ------------  ----------------------------------
C-UPDZHWDDBF     H-JXVKXXCUTW  BL-CRUISE-4H  2027-07-15  09:00      4      1439          TR-DEMO-0714  Reviewed with the traveler. Mornings only.
```

Other staff commands: `confirm`, `decline`, `holds`, `sweep`, `stats` (hold-to-book rate), `log`, `record`,
`load-example`, `reset --yes`. Run `python admin.py -h`.

In a real system, "confirm" is where your booking platform creates the booking and takes payment in its own
checkout. The agent never sees payment data.

## Settings

Set them as environment variables (in the client's `env` block) or as flags on `server.py`.

| Environment variable | Flag | Default | What it is |
|---|---|---|---|
| `TRIP_MCP_HOLD_TTL_SECONDS` | `--ttl` | 86400 (24 h) | Policy choice: how long a hold lasts |
| `TRIP_MCP_CUTOFF_HOURS` | | 48 | Policy choice: holds end this many hours before departure (Bay Light's free-cancellation window) |
| `TRIP_MCP_MAX_ACTIVE_HOLDS` | `--max-holds` | 3 | Policy choice: active holds per caller |
| `TRIP_MCP_MAX_SEATS_PER_HOLD` | | 12 | Policy choice: larger groups go to a person |
| `TRIP_MCP_MAX_NEW_HOLDS_PER_DAY` | | 20 | Policy choice: stops hold and release churn |
| `TRIP_MCP_CALLER_ID` | `--caller-id` | local-agent | Name of this client in the log. In production it comes from authentication, never from the agent. |
| `TRIP_MCP_DB` | `--db` | data/trip_mcp.sqlite3 | Mock inventory file (rebuilt with fictional data if missing) |
| `TRIP_MCP_LOG` | `--log` | logs/calls.jsonl | Call log, one JSON object per line |
| `TRIP_MCP_UTC_OFFSET_HOURS` | | -8 | Local time for departures (Seward in summer) |
| `TRIP_MCP_SEASON_YEAR` | | 2027 | Season the mock inventory is seeded for |

The server calls no AI model and needs no API keys.

## Policy before code

The survey behind the session (Skift Research + McKinsey, Sept 2026, n = 1,015 US travelers) asked what would
make travelers confident letting AI book. The three answers are the design spec:

| Traveler confidence driver | Where it lives here | Decision for the business |
|---|---|---|
| Review and change before confirming (52%) | Reversible holds, release and re-hold, `traveler_reviewed` in the record | Who may place a hold, and how long it lasts (Policy choice) |
| A track record (30%) | Every call logged; `admin.py stats` gives the hold-to-book rate | What you publish about how holds work (Policy choice) |
| A human who can step in (20%) | `request_confirmation` plus `admin.py confirm` | Who confirms, and how fast in season (Policy choice) |

What happens to inventory while it is held is the fourth decision. Here held seats come off sale; that is a
Policy choice too, and your channel agreements may already set rules for it (Contractual: check your booking
platform terms and each OTA or reseller agreement).

## Moving from scaffold to production (for a developer)

1. Replace the SQLite inventory with your booking platform's API: live availability, time-limited holds that
   expire on the platform, confirmation and cancellation. If the platform has no hold API, do not imitate one
   in a side database (Recommendation): the platform would keep selling the seats you think are held.
2. Add authentication (OAuth per the MCP authorization spec) and HTTPS. Take the caller id from the token.
3. Agree data terms with the platform and any agent channel: what traveler data they pass, keep and delete
   (Contractual: data processing terms in each agreement).
4. Lodges: when an agent shows your price, show the total price including mandatory fees
   (Legal mandate: FTC 16 CFR Part 464, short-term lodging; it does not cover tours).
5. Safety calls stay with people: weather and sea-state go or no-go belong to the captain (Recommendation).
   Guide licensing (AS 08.54, ADF&G guide and business registration) is a Legal mandate and cannot be handed to an agent.
6. Count: bookings through AI channels, hold-to-book rate, share of holds that expire, staff response time.

## Files

| File | What it is |
|---|---|
| `server.py` | MCP server (stdio or streamable-http on 127.0.0.1); thin wrapper over `inventory.py` |
| `inventory.py` | All business rules; standard library only |
| `admin.py` | Staff console |
| `demo.py` | Scripted agent walk-through |
| `validate_record.py` | Schema check plus personal-data scan; also a command-line tool |
| `trip-record.schema.json` | JSON Schema 2020-12 for the trip record; no personal-data fields |
| `trip-record.example.json` | The fictional family from tool 3.a |
| `test_agent_script.py` | Scripted agent: search, hold, review, change, request confirmation; 2-second expiry; per-caller limits |
| `test_schema_pii.py` | The schema and the personal-data guard |
| `test_server_mcp.py` | Local-only binding, dry run, and (with the SDK installed) a real stdio round trip |
| `requirements.txt` | The MCP Python SDK |

## Notes and limits

- MCP SDK versions: `server.py` tries the v2 names first (`MCPServer`) and falls back to v1 (`FastMCP`).
  Tested on Python 3.14 (Windows, October 2026) with mcp 2.3.0 and with mcp 1.30.0: all tests pass with both,
  including a real stdio round trip, and streamable-http answers on 127.0.0.1. `requirements.txt` pins v2.
- The personal-data scan is a guard rail, not a guarantee. It catches emails, phone, card, account and ID numbers,
  street addresses and labels such as "Name:"; it cannot catch every name written in plain text.
  Keep personal data out of trip records in the first place.
- AI drafts. You approve. Anything an agent writes into a trip record is a draft until a person at the business reviews it.
- Effort, cost and time figures on the web page are estimates.
