"""Business logic for the trip-record MCP scaffold (tool 3.c, ATIA AI Take-Home Kit).

Standard library only (sqlite3). The MCP layer in server.py is a thin wrapper around this
module, so every rule here can be tested without the mcp package.

FICTIONAL TEACHING DATA: Bay Light Day Cruises, Seward, and its partners Mile 12 Kennel and
Harbor Kayak Co. are fictional. Mile 12 Kennel's departure times, both partners' capacities and
both partners' season dates are MOCK values invented for the test harness; they are not in the
approved facts. (Harbor Kayak's 8:00 and 13:00 departures are in the approved facts.)

Rules the code enforces (each is a policy choice you can change in Config):
  * A hold is reversible and time-limited. It expires on the server even if the agent disappears.
    Expiry is applied at the start of every call (and by admin.py sweep).
  * A hold also expires no later than the free-cancellation cutoff (48 hours before departure
    for the fictional Bay Light terms), so a hold never runs into the no-refund window.
  * Held seats count against capacity, so two agents cannot both promise the last seats.
  * Each caller has a limit on active holds, on seats per hold, on new holds per day, and may
    not hold the same departure twice. That stops an agent from creating phantom inventory.
  * An agent can only ask for confirmation. A person confirms or declines with admin.py.
  * Every call, including refused ones, is written to a JSONL log.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import validate_record

HERE = Path(__file__).resolve().parent

ACTIVE_STATES = ("active", "pending_staff_confirmation")
SEAT_STATES = ("active", "pending_staff_confirmation", "confirmed")   # these use up capacity
ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"   # letters only, so ids never look like phone or card numbers


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass
class Config:
    db_path: str = str(HERE / "data" / "trip_mcp.sqlite3")
    log_path: str = str(HERE / "logs" / "calls.jsonl")
    hold_ttl_seconds: int = 24 * 3600            # Policy choice: how long a hold lasts (default 24 hours)
    cutoff_hours_before_departure: int = 48      # Policy choice: holds end before the no-refund window
    max_active_holds_per_caller: int = 3         # Policy choice: stops phantom inventory
    max_seats_per_hold: int = 12                 # Policy choice: larger groups go to a person
    max_new_holds_per_caller_per_day: int = 20   # Policy choice: stops hold/release churn
    local_utc_offset_hours: int = -8             # Seward in summer (AKDT). Used for departure times.
    season_year: int = 2027                      # which season the mock inventory is seeded for
    caller_id: str = "local-agent"               # in production this comes from authentication, never from the agent

    @classmethod
    def from_env(cls, **overrides: Any) -> "Config":
        c = cls(
            db_path=os.environ.get("TRIP_MCP_DB") or cls.db_path,
            log_path=os.environ.get("TRIP_MCP_LOG") or cls.log_path,
            hold_ttl_seconds=_env_int("TRIP_MCP_HOLD_TTL_SECONDS", cls.hold_ttl_seconds),
            cutoff_hours_before_departure=_env_int("TRIP_MCP_CUTOFF_HOURS", cls.cutoff_hours_before_departure),
            max_active_holds_per_caller=_env_int("TRIP_MCP_MAX_ACTIVE_HOLDS", cls.max_active_holds_per_caller),
            max_seats_per_hold=_env_int("TRIP_MCP_MAX_SEATS_PER_HOLD", cls.max_seats_per_hold),
            max_new_holds_per_caller_per_day=_env_int("TRIP_MCP_MAX_NEW_HOLDS_PER_DAY", cls.max_new_holds_per_caller_per_day),
            local_utc_offset_hours=_env_int("TRIP_MCP_UTC_OFFSET_HOURS", cls.local_utc_offset_hours),
            season_year=_env_int("TRIP_MCP_SEASON_YEAR", cls.season_year),
            caller_id=os.environ.get("TRIP_MCP_CALLER_ID") or cls.caller_id,
        )
        for k, v in overrides.items():
            if v is not None:
                setattr(c, k, v)
        return c


# --------------------------------------------------------------------------- fictional seed data

PRODUCTS: list[dict[str, Any]] = [
    {
        "product_id": "BL-CRUISE-4H", "business": "Bay Light Day Cruises (FICTIONAL)", "name": "Wildlife and glacier cruise",
        "duration_minutes": 240, "min_age": 4, "capacity": 40, "departures": ["09:00", "14:00"],
        "season": ["05-15", "09-15"], "mock_note": "",
        "not_supplied": ["group discounts", "private charters", "pet policy", "accessibility of the vessel", "price"],
    },
    {
        "product_id": "MK-CART-90", "business": "Mile 12 Kennel (FICTIONAL PARTNER)", "name": "Summer sled-dog cart ride",
        "duration_minutes": 90, "min_age": 2, "capacity": 12, "departures": ["10:00", "13:00", "16:00"],
        "season": ["05-15", "09-15"],
        "mock_note": "MOCK: departure times, capacity and season dates are invented for the test harness. They are not in the approved facts. The partner confirms them.",
        "not_supplied": ["departure times", "how guests without a car get there", "price"],
    },
    {
        "product_id": "HK-PADDLE-3H", "business": "Harbor Kayak Co. (FICTIONAL PARTNER)", "name": "Guided paddle",
        "duration_minutes": 180, "min_age": 12, "capacity": 10, "departures": ["08:00", "13:00"],
        "season": ["05-15", "09-15"],
        "mock_note": "MOCK: capacity and season dates are invented for the test harness. They are not in the approved facts.",
        "not_supplied": ["meeting point", "whether it runs in rain", "price"],
    },
]

FACTS: dict[str, tuple[str, str]] = {
    "BL-DURATION": ("BL-CRUISE-4H", "4-hour wildlife and glacier cruise."),
    "BL-DEPARTURES": ("BL-CRUISE-4H", "Departs 9:00 and 14:00, May 15 to September 15."),
    "BL-CAPACITY": ("BL-CRUISE-4H", "Capacity 40."),
    "BL-MIN-AGE": ("BL-CRUISE-4H", "Minimum age 4."),
    "BL-CABIN": ("BL-CRUISE-4H", "Heated enclosed cabin, two restrooms, hot drinks included."),
    "BL-LUNCH": ("BL-CRUISE-4H", "Lunch not included."),
    "BL-MEETING": ("BL-CRUISE-4H", "Meeting point: small-boat harbor, a 12-minute walk from the cruise ship dock."),
    "BL-RAIN": ("BL-CRUISE-4H", "Runs in rain. Cancels only for a marine warning, with a full refund."),
    "BL-CANCEL": ("BL-CRUISE-4H", "Free cancellation until 48 hours before departure; inside 48 hours, no refund."),
    "MK-OFFER": ("MK-CART-90", "Summer sled-dog cart ride, 90 minutes."),
    "MK-DRIVE": ("MK-CART-90", "15 minutes by car from the harbor."),
    "MK-MIN-AGE": ("MK-CART-90", "Ages 2 and up."),
    "MK-RAIN": ("MK-CART-90", "Runs in rain."),
    "MK-CODE": ("MK-CART-90", "Referral code BAYLIGHT-K."),
    "HK-OFFER": ("HK-PADDLE-3H", "3-hour guided paddle. Departs 8:00 and 13:00."),
    "HK-MIN-AGE": ("HK-PADDLE-3H", "Minimum age 12."),
    "HK-WIND": ("HK-PADDLE-3H", "Cancels in wind over 15 knots."),
    "HK-CODE": ("HK-PADDLE-3H", "Referral code BAYLIGHT-P."),
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
  product_id TEXT PRIMARY KEY, business TEXT, name TEXT, duration_minutes INTEGER, min_age INTEGER,
  capacity INTEGER, departures_json TEXT, season_start TEXT, season_end TEXT, mock_note TEXT, not_supplied_json TEXT);
CREATE TABLE IF NOT EXISTS facts (fact_id TEXT PRIMARY KEY, product_id TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS slots (
  product_id TEXT, date TEXT, departure TEXT, capacity INTEGER, PRIMARY KEY (product_id, date, departure));
CREATE TABLE IF NOT EXISTS holds (
  hold_id TEXT PRIMARY KEY, caller TEXT, product_id TEXT, date TEXT, departure TEXT, seats INTEGER,
  status TEXT, placed_ts REAL, expires_ts REAL, ended_ts REAL, record_id TEXT, confirmation_id TEXT);
CREATE INDEX IF NOT EXISTS holds_slot ON holds (product_id, date, departure, status);
CREATE INDEX IF NOT EXISTS holds_caller ON holds (caller, status);
CREATE TABLE IF NOT EXISTS confirmations (
  confirmation_id TEXT PRIMARY KEY, hold_id TEXT, caller TEXT, status TEXT, requested_ts REAL,
  note TEXT, decided_ts REAL, decided_by TEXT, decision_note TEXT);
CREATE TABLE IF NOT EXISTS trip_records (
  record_id TEXT PRIMARY KEY, version INTEGER, json TEXT, updated_ts REAL, updated_by TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


# --------------------------------------------------------------------------- helpers

class ToolError(Exception):
    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_date(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        raise ToolError("BAD_DATE", "Use a date like 2027-07-15.")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ToolError("BAD_DATE", "Use a real date like 2027-07-15.") from None


def _norm_time(value: Any) -> str:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(value or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ToolError("BAD_TIME", "Use a 24-hour departure time like 09:00.")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _norm_int(value: Any, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        raise ToolError("BAD_NUMBER", f"{name} has to be a whole number from {lo} to {hi}.")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ToolError("BAD_NUMBER", f"{name} has to be a whole number from {lo} to {hi}.") from None
    if n != value and not (isinstance(value, str) and value.strip().isdigit()):
        raise ToolError("BAD_NUMBER", f"{name} has to be a whole number from {lo} to {hi}.")
    if not lo <= n <= hi:
        raise ToolError("BAD_NUMBER", f"{name} has to be from {lo} to {hi}.")
    return n


def _new_id(prefix: str) -> str:
    return prefix + "-" + "".join(secrets.choice(ID_ALPHABET) for _ in range(10))


def _check_free_text(text: str, field_name: str, limit: int = 280) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        raise ToolError("TOO_LONG", f"{field_name} is limited to {limit} characters.")
    res = validate_record.scan_personal_data(text)
    if res.errors:
        raise ToolError("PERSONAL_DATA", f"{field_name} looks like it contains personal data: {res.errors[0].message}")
    return text


# --------------------------------------------------------------------------- the inventory

class Inventory:
    """Mock inventory and trip-record store over SQLite. One instance per server process."""

    def __init__(self, config: Config | None = None, clock: Callable[[], float] = time.time) -> None:
        self.config = config or Config()
        self.clock = clock
        self._lock = threading.RLock()
        Path(self.config.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config.log_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.config.db_path, timeout=10, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA_SQL)
        self.schema = validate_record.load_schema(HERE / "trip-record.schema.json")
        self._seed_if_empty()

    # ----- setup
    def _seed_if_empty(self) -> None:
        with self._lock:
            if self.db.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
                return
            year = self.config.season_year
            self.db.execute("BEGIN IMMEDIATE")
            try:
                for p in PRODUCTS:
                    self.db.execute(
                        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (p["product_id"], p["business"], p["name"], p["duration_minutes"], p["min_age"], p["capacity"],
                         json.dumps(p["departures"]), f"{year}-{p['season'][0]}", f"{year}-{p['season'][1]}",
                         p["mock_note"], json.dumps(p["not_supplied"])))
                    d = date.fromisoformat(f"{year}-{p['season'][0]}")
                    end = date.fromisoformat(f"{year}-{p['season'][1]}")
                    while d <= end:
                        for dep in p["departures"]:
                            self.db.execute("INSERT INTO slots VALUES (?,?,?,?)", (p["product_id"], d.isoformat(), dep, p["capacity"]))
                        d += timedelta(days=1)
                for fid, (pid, text) in FACTS.items():
                    self.db.execute("INSERT INTO facts VALUES (?,?,?)", (fid, pid, text))
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('seeded_for', ?)", (str(year),))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        self.db.close()

    # ----- plumbing
    def _log(self, caller: str, tool: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        entry = {"ts": iso(self.clock()), "caller": caller, "tool": tool, "args": args, "ok": bool(result.get("ok"))}
        for k in ("error", "hold_id", "status", "confirmation_id", "record_id", "version", "expires_at"):
            if k in result:
                entry[k] = result[k]
        line = json.dumps(entry, ensure_ascii=False)
        with open(self.config.log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _run(self, caller: str, tool: str, log_args: dict[str, Any], fn: Callable[[float], dict[str, Any]]) -> dict[str, Any]:
        """Run one call: sweep expired holds, do the work in one transaction, log it."""
        with self._lock:
            now = self.clock()
            try:
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    self._sweep(now)
                    result = fn(now)
                    self.db.execute("COMMIT")
                except Exception:
                    self.db.execute("ROLLBACK")
                    raise
            except ToolError as exc:
                result = {"ok": False, "error": exc.code, "message": exc.message, **exc.extra}
            except Exception:
                # an unexpected fault is logged too (every call is logged), then raised for the MCP layer to report
                self._log(caller, tool, log_args, {"ok": False, "error": "INTERNAL_ERROR"})
                raise
            self._log(caller, tool, log_args, result)
            return result

    def _sweep(self, now: float) -> int:
        expired = [r["hold_id"] for r in self.db.execute(
            f"SELECT hold_id FROM holds WHERE status IN {ACTIVE_STATES} AND expires_ts <= ?", (now,))]
        for hid in expired:
            self.db.execute("UPDATE holds SET status='expired', ended_ts=expires_ts WHERE hold_id=?", (hid,))
            self.db.execute("UPDATE confirmations SET status='expired', decided_ts=? WHERE hold_id=? AND status='pending'", (now, hid))
        return len(expired)

    def _product(self, product_id: Any) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM products WHERE product_id=?", (str(product_id or "").strip().upper(),)).fetchone()
        if not row:
            raise ToolError("UNKNOWN_PRODUCT", f"No product {product_id!r}. Call search_products to see product ids.")
        return row

    def _used(self, product_id: str, day: str, dep: str) -> dict[str, int]:
        out = {"held": 0, "confirmed": 0}
        for r in self.db.execute(
                "SELECT status, COALESCE(SUM(seats),0) AS s FROM holds WHERE product_id=? AND date=? AND departure=? "
                f"AND status IN {SEAT_STATES} GROUP BY status", (product_id, day, dep)):
            out["confirmed" if r["status"] == "confirmed" else "held"] += r["s"]
        return out

    def _departure_ts(self, day: str, dep: str) -> float:
        local = datetime.fromisoformat(f"{day}T{dep}:00").replace(tzinfo=timezone(timedelta(hours=self.config.local_utc_offset_hours)))
        return local.timestamp()

    def _slots(self, product: sqlite3.Row, day: str, now: float, party_size: int | None) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM slots WHERE product_id=? AND date=? ORDER BY departure", (product["product_id"], day)).fetchall()
        out = []
        cutoff = self.config.cutoff_hours_before_departure * 3600
        for s in rows:
            used = self._used(product["product_id"], day, s["departure"])
            available = max(0, s["capacity"] - used["held"] - used["confirmed"])
            too_late = self._departure_ts(day, s["departure"]) - cutoff <= now
            need = party_size or 1
            out.append({
                "departure": s["departure"], "capacity": s["capacity"], "held": used["held"], "confirmed": used["confirmed"],
                "available": available, "can_hold": (available >= need) and not too_late,
                **({"note": f"Inside {self.config.cutoff_hours_before_departure} hours of departure: ask a person at the business."} if too_late else {}),
            })
        return out

    def _hold_row(self, caller: str, hold_id: Any) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM holds WHERE hold_id=? AND caller=?", (str(hold_id or "").strip(), caller)).fetchone()
        if not row:
            raise ToolError("HOLD_NOT_FOUND", f"No hold {hold_id!r} for this caller.")
        return row

    @staticmethod
    def _hold_view(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "hold_id": row["hold_id"], "product_id": row["product_id"], "date": row["date"], "departure": row["departure"],
            "seats": row["seats"], "status": row["status"], "placed_at": iso(row["placed_ts"]), "expires_at": iso(row["expires_ts"]),
            **({"confirmation_id": row["confirmation_id"]} if row["confirmation_id"] else {}),
        }

    # ----- tools (each returns a plain dict; ok False carries error and message)
    def search_products(self, caller: str, query: str = "", date: str | None = None, party_size: int | None = None,
                        youngest_age: int | None = None) -> dict[str, Any]:
        args = {"query": (query or "")[:60], "date": date, "party_size": party_size, "youngest_age": youngest_age}

        def work(now: float) -> dict[str, Any]:
            day = _norm_date(date) if date else None
            size = _norm_int(party_size, "party_size", 1, 60) if party_size is not None else None
            young = _norm_int(youngest_age, "youngest_age", 0, 120) if youngest_age is not None else None
            q = (query or "").strip().lower()
            results = []
            for p in self.db.execute("SELECT * FROM products ORDER BY product_id"):
                facts = [{"fact_id": f["fact_id"], "text": f["text"]} for f in
                         self.db.execute("SELECT fact_id, text FROM facts WHERE product_id=? ORDER BY fact_id", (p["product_id"],))]
                blob = " ".join([p["product_id"], p["business"], p["name"]] + [f["text"] for f in facts]).lower()
                if q and not all(word in blob for word in q.split()):
                    continue
                item: dict[str, Any] = {
                    "product_id": p["product_id"], "business": p["business"], "name": p["name"],
                    "duration_minutes": p["duration_minutes"], "min_age": p["min_age"],
                    "departures": json.loads(p["departures_json"]), "season": f"{p['season_start']} to {p['season_end']}",
                    "facts": facts, "not_supplied": json.loads(p["not_supplied_json"]),
                    "price": "Not in the approved facts. Do not quote a price; ask the business.",
                }
                if p["mock_note"]:
                    item["mock_note"] = p["mock_note"]
                if young is not None:
                    fits = young >= p["min_age"]
                    item["age_fit"] = {"fits": fits, "reason": f"Minimum age {p['min_age']}; youngest traveler is {young}."}
                if day:
                    in_season = p["season_start"] <= day <= p["season_end"]
                    item["in_season"] = in_season
                    item["availability"] = self._slots(p, day, now, size) if in_season else []
                results.append(item)
            return {"ok": True, "count": len(results), "products": results,
                    "data_note": "FICTIONAL TEACHING DATA. Cite fact_ids when you explain a choice. Anything in not_supplied is a question for the business, not a guess."}
        return self._run(caller, "search_products", args, work)

    def check_availability(self, caller: str, product_id: str, date: str, party_size: int = 1) -> dict[str, Any]:
        args = {"product_id": product_id, "date": date, "party_size": party_size}

        def work(now: float) -> dict[str, Any]:
            p = self._product(product_id)
            day = _norm_date(date)
            size = _norm_int(party_size, "party_size", 1, 60)
            if not p["season_start"] <= day <= p["season_end"]:
                return {"ok": True, "product_id": p["product_id"], "date": day, "in_season": False, "departures": [],
                        "message": f"Not operating on {day}. Season: {p['season_start']} to {p['season_end']}."}
            return {"ok": True, "product_id": p["product_id"], "date": day, "party_size": size, "in_season": True,
                    "departures": self._slots(p, day, now, size),
                    "note": "Held seats count against capacity. can_hold means a hold for this party would be accepted now."}
        return self._run(caller, "check_availability", args, work)

    def place_hold(self, caller: str, product_id: str, date: str, departure: str, seats: int, record_id: str | None = None) -> dict[str, Any]:
        args = {"product_id": product_id, "date": date, "departure": departure, "seats": seats, "record_id": record_id}
        cfg = self.config

        def work(now: float) -> dict[str, Any]:
            p = self._product(product_id)
            day, dep = _norm_date(date), _norm_time(departure)
            n = _norm_int(seats, "seats", 1, 60)
            if n > cfg.max_seats_per_hold:
                raise ToolError("TOO_MANY_SEATS", f"A hold is limited to {cfg.max_seats_per_hold} seats. Larger groups go to a person at the business.")
            slot = self.db.execute("SELECT * FROM slots WHERE product_id=? AND date=? AND departure=?", (p["product_id"], day, dep)).fetchone()
            if not slot:
                raise ToolError("NO_SUCH_DEPARTURE", f"{p['product_id']} has no {dep} departure on {day}. Call check_availability first.")
            active = self.db.execute(f"SELECT COUNT(*) FROM holds WHERE caller=? AND status IN {ACTIVE_STATES}", (caller,)).fetchone()[0]
            if active >= cfg.max_active_holds_per_caller:
                raise ToolError("HOLD_LIMIT_REACHED", f"This caller already has {active} active holds (the limit is {cfg.max_active_holds_per_caller}). "
                                "Release one before placing another.")
            recent = self.db.execute("SELECT COUNT(*) FROM holds WHERE caller=? AND placed_ts > ?", (caller, now - 86400)).fetchone()[0]
            if recent >= cfg.max_new_holds_per_caller_per_day:
                raise ToolError("RATE_LIMITED", f"This caller placed {recent} holds in the last 24 hours (the limit is {cfg.max_new_holds_per_caller_per_day}).")
            dup = self.db.execute(f"SELECT hold_id FROM holds WHERE caller=? AND product_id=? AND date=? AND departure=? AND status IN {ACTIVE_STATES}",
                                  (caller, p["product_id"], day, dep)).fetchone()
            if dup:
                raise ToolError("DUPLICATE_HOLD", f"This caller already holds this departure ({dup['hold_id']}). Change the seats by releasing it and holding again.")
            dep_ts = self._departure_ts(day, dep)
            cutoff_ts = dep_ts - cfg.cutoff_hours_before_departure * 3600
            if cutoff_ts <= now:
                raise ToolError("TOO_LATE_TO_HOLD", f"Inside {cfg.cutoff_hours_before_departure} hours of departure. Holds are not offered; ask a person at the business.")
            rid = None
            if record_id:
                rid = str(record_id).strip()
                if not re.fullmatch(r"TR-[A-Z0-9]+(-[A-Z0-9]+)*", rid) or len(rid) > 40:
                    raise ToolError("BAD_RECORD_ID", "record_id looks like TR-DEMO-0714.")
                stored = self.db.execute("SELECT json FROM trip_records WHERE record_id=?", (rid,)).fetchone()
                if stored:
                    bands = [b.get("band", "") for b in json.loads(stored["json"]).get("party", {}).get("age_bands", [])]
                    lows = [(int(re.match(r"\d+", b).group(0)), b) for b in bands if re.match(r"\d+", b)]
                    if lows and min(lows)[0] < p["min_age"]:
                        raise ToolError("MIN_AGE", f"Minimum age {p['min_age']} (an approved fact). Trip record {rid} has a traveler in the "
                                        f"{min(lows)[1]} age band. Offer something else.")
            used = self._used(p["product_id"], day, dep)
            available = slot["capacity"] - used["held"] - used["confirmed"]
            if n > available:
                raise ToolError("NOT_ENOUGH_SEATS", f"Only {max(available, 0)} seats are free on {day} at {dep}.", available=max(available, 0))
            expires = min(now + cfg.hold_ttl_seconds, cutoff_ts)
            hid = _new_id("H")
            self.db.execute("INSERT INTO holds VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (hid, caller, p["product_id"], day, dep, n, "active", now, expires, None, rid, None))
            return {
                "ok": True, "hold_id": hid, "status": "active", "product_id": p["product_id"], "date": day, "departure": dep, "seats": n,
                "placed_at": iso(now), "expires_at": iso(expires), "ttl_seconds": int(round(expires - now)),
                "what_this_means": "Reversible. Nothing is booked or charged. The hold expires on its own at expires_at and the seats go back on sale. "
                                   "Let the traveler review and change the plan, then call request_confirmation. A person at the business confirms.",
            }
        return self._run(caller, "place_hold", args, work)

    def get_hold(self, caller: str, hold_id: str) -> dict[str, Any]:
        def work(now: float) -> dict[str, Any]:
            row = self._hold_row(caller, hold_id)
            view = self._hold_view(row)
            if row["status"] in ACTIVE_STATES:
                view["seconds_left"] = max(0, int(row["expires_ts"] - now))
            return {"ok": True, **view}
        return self._run(caller, "get_hold", {"hold_id": hold_id}, work)

    def release_hold(self, caller: str, hold_id: str) -> dict[str, Any]:
        def work(now: float) -> dict[str, Any]:
            row = self._hold_row(caller, hold_id)
            if row["status"] not in ACTIVE_STATES:
                return {"ok": True, **self._hold_view(row), "message": f"Nothing to release: the hold is already {row['status']}."}
            self.db.execute("UPDATE holds SET status='released', ended_ts=? WHERE hold_id=?", (now, row["hold_id"]))
            self.db.execute("UPDATE confirmations SET status='withdrawn', decided_ts=? WHERE hold_id=? AND status='pending'", (now, row["hold_id"]))
            row = self._hold_row(caller, hold_id)
            return {"ok": True, **self._hold_view(row), "message": "Released. The seats are back on sale."}
        return self._run(caller, "release_hold", {"hold_id": hold_id}, work)

    def request_confirmation(self, caller: str, hold_id: str, note: str = "") -> dict[str, Any]:
        def work(now: float) -> dict[str, Any]:
            row = self._hold_row(caller, hold_id)
            if row["status"] == "pending_staff_confirmation":
                return {"ok": True, **self._hold_view(row), "message": "Already waiting for a person at the business."}
            if row["status"] != "active":
                raise ToolError("HOLD_NOT_ACTIVE", f"The hold is {row['status']}. Place a new hold first.", status=row["status"])
            clean = _check_free_text(note, "note")
            cid = _new_id("C")
            self.db.execute("INSERT INTO confirmations VALUES (?,?,?,?,?,?,?,?,?)", (cid, row["hold_id"], caller, "pending", now, clean, None, None, None))
            self.db.execute("UPDATE holds SET status='pending_staff_confirmation', confirmation_id=? WHERE hold_id=?", (cid, row["hold_id"]))
            row = self._hold_row(caller, hold_id)
            return {
                "ok": True, **self._hold_view(row),
                "message": f"Sent to a person at the business. They confirm or decline before the hold expires at {iso(row['expires_ts'])}. "
                           "Nothing is booked or charged yet. Tell the traveler that a person will follow up.",
            }
        return self._run(caller, "request_confirmation", {"hold_id": hold_id, "note_chars": len(note or "")}, work)

    def get_trip_record(self, caller: str, record_id: str) -> dict[str, Any]:
        def work(now: float) -> dict[str, Any]:
            row = self.db.execute("SELECT * FROM trip_records WHERE record_id=?", (str(record_id or "").strip(),)).fetchone()
            if not row:
                raise ToolError("RECORD_NOT_FOUND", f"No trip record {record_id!r}.")
            rec = json.loads(row["json"])
            synced = []
            for h in rec.get("holds", []):
                live = self.db.execute("SELECT * FROM holds WHERE hold_id=?", (h.get("hold_id"),)).fetchone()
                if live and (live["status"] != h.get("status") or iso(live["expires_ts"]) != h.get("expires_at")):
                    h["status"], h["expires_at"] = live["status"], iso(live["expires_ts"])
                    if live["confirmation_id"]:
                        h["confirmation_id"] = live["confirmation_id"]
                    synced.append(h["hold_id"])
            return {"ok": True, "record_id": row["record_id"], "version": row["version"], "updated_at": iso(row["updated_ts"]),
                    "record": rec, "holds_synced_from_inventory": synced,
                    "note": "Hold status comes from the live inventory. To change the record, send the next version with put_trip_record."}
        return self._run(caller, "get_trip_record", {"record_id": record_id}, work)

    def put_trip_record(self, caller: str, record: Any) -> dict[str, Any]:
        rid = record.get("record_id") if isinstance(record, dict) else None
        ver = record.get("version") if isinstance(record, dict) else None

        def work(now: float) -> dict[str, Any]:
            if not isinstance(record, dict):
                raise ToolError("INVALID_RECORD", "The trip record has to be a JSON object.")
            if len(json.dumps(record)) > 64_000:
                raise ToolError("TOO_LONG", "The trip record is limited to 64,000 characters.")
            rec = json.loads(json.dumps(record))
            rec["updated_at"] = iso(now)          # the server's clock wins
            res = validate_record.validate(rec, self.schema, now=datetime.fromtimestamp(now, tz=timezone.utc))
            if not res.ok:
                raise ToolError("INVALID_RECORD", "The trip record failed validation. Nothing was saved.",
                                errors=[{"path": i.path, "message": i.message, "kind": i.kind} for i in res.errors[:20]])
            existing = self.db.execute("SELECT version FROM trip_records WHERE record_id=?", (rec["record_id"],)).fetchone()
            if existing and rec["version"] != existing["version"] + 1:
                raise ToolError("VERSION_CONFLICT", f"Stored version is {existing['version']}. Read the record again, apply your change, and send version {existing['version'] + 1}.",
                                stored_version=existing["version"])
            warnings = [{"path": i.path, "message": i.message} for i in res.warnings]
            for h in rec.get("holds", []):
                live = self.db.execute("SELECT caller FROM holds WHERE hold_id=?", (h["hold_id"],)).fetchone()
                if not live:
                    warnings.append({"path": "/holds", "message": f"Hold {h['hold_id']} is not in this inventory."})
                elif live["caller"] != caller:
                    raise ToolError("NOT_YOUR_HOLD", f"Hold {h['hold_id']} belongs to another caller.")
            self.db.execute("INSERT OR REPLACE INTO trip_records VALUES (?,?,?,?,?)", (rec["record_id"], rec["version"], json.dumps(rec), now, caller))
            return {"ok": True, "record_id": rec["record_id"], "version": rec["version"], "updated_at": iso(now), "warnings": warnings}
        return self._run(caller, "put_trip_record", {"record_id": rid, "version": ver}, work)

    # ----- staff side (admin.py). Not exposed as MCP tools.
    def pending_confirmations(self) -> list[dict[str, Any]]:
        def work(now: float) -> dict[str, Any]:
            rows = self.db.execute(
                "SELECT c.*, h.product_id, h.date, h.departure, h.seats, h.expires_ts, h.record_id FROM confirmations c "
                "JOIN holds h ON h.hold_id=c.hold_id WHERE c.status='pending' ORDER BY h.expires_ts").fetchall()
            return {"ok": True, "items": [{
                "confirmation_id": r["confirmation_id"], "hold_id": r["hold_id"], "caller": r["caller"], "product_id": r["product_id"],
                "date": r["date"], "departure": r["departure"], "seats": r["seats"], "requested_at": iso(r["requested_ts"]),
                "expires_at": iso(r["expires_ts"]), "minutes_left": max(0, int((r["expires_ts"] - now) // 60)),
                "record_id": r["record_id"], "note": r["note"]} for r in rows]}
        return self._run("staff", "admin.pending", {}, work)["items"]

    def list_holds(self, include_closed: bool = False) -> list[dict[str, Any]]:
        def work(now: float) -> dict[str, Any]:
            where = "" if include_closed else f"WHERE status IN {SEAT_STATES}"
            rows = self.db.execute(f"SELECT * FROM holds {where} ORDER BY placed_ts").fetchall()
            return {"ok": True, "items": [{**self._hold_view(r), "caller": r["caller"]} for r in rows]}
        return self._run("staff", "admin.holds", {"include_closed": include_closed}, work)["items"]

    def decide(self, confirmation_id: str, by: str, approve: bool, note: str = "") -> dict[str, Any]:
        who = (by or "").strip()[:40]

        def work(now: float) -> dict[str, Any]:
            if not who:
                raise ToolError("WHO", "Say who is deciding (initials or role).")
            c = self.db.execute("SELECT * FROM confirmations WHERE confirmation_id=?", (str(confirmation_id).strip(),)).fetchone()
            if not c:
                raise ToolError("NOT_FOUND", f"No confirmation {confirmation_id!r}.")
            if c["status"] != "pending":
                raise ToolError("NOT_PENDING", f"Confirmation {c['confirmation_id']} is {c['status']}. If it expired, the agent has to place a new hold.", status=c["status"])
            clean = _check_free_text(note, "note")
            new_hold, new_conf = ("confirmed", "confirmed") if approve else ("declined", "declined")
            self.db.execute("UPDATE confirmations SET status=?, decided_ts=?, decided_by=?, decision_note=? WHERE confirmation_id=?",
                            (new_conf, now, who, clean, c["confirmation_id"]))
            self.db.execute("UPDATE holds SET status=?, ended_ts=? WHERE hold_id=?", (new_hold, now if not approve else None, c["hold_id"]))
            return {"ok": True, "confirmation_id": c["confirmation_id"], "hold_id": c["hold_id"], "status": new_conf, "decided_by": who}
        return self._run("staff:" + (who or "?"), "admin.confirm" if approve else "admin.decline", {"confirmation_id": confirmation_id}, work)

    def sweep(self) -> int:
        with self._lock:
            now = self.clock()
            self.db.execute("BEGIN IMMEDIATE")
            n = self._sweep(now)
            self.db.execute("COMMIT")
            self._log("staff", "admin.sweep", {}, {"ok": True, "status": f"{n} expired"})
            return n

    def stats(self) -> dict[str, Any]:
        def work(now: float) -> dict[str, Any]:
            counts = {r["status"]: r["n"] for r in self.db.execute("SELECT status, COUNT(*) AS n FROM holds GROUP BY status")}
            placed = sum(counts.values())
            confirmed = counts.get("confirmed", 0)
            return {"ok": True, "holds_placed": placed, "by_status": counts,
                    "hold_to_book_rate": round(confirmed / placed, 3) if placed else None}
        return self._run("staff", "admin.stats", {}, work)
