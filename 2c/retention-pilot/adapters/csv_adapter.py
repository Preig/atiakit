"""CSV adapter: read a booking-platform export and keep only allow-listed columns.

What it does on load:
  1. Normalizes header names ("Booking ID" becomes booking_id) and maps common aliases.
  2. Drops every column that is not on the allow-list, and logs the column NAME (never its values).
  3. Drops any column whose name looks like personal or payment data, even if it is allow-listed.
  4. Blanks any free-text value that looks like an email, phone or card number, and logs where.
  5. Converts dates, numbers, rate types and channels to a standard form.

Guest names, emails, phones, addresses and payment data never enter the pilot.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import re

from retention.pii import column_looks_personal, pii_kinds

# The allow-list. Adding a column here is a Policy choice: write down why.
BOOKING_COLUMNS = {
    "booking_id": "id",
    "booked_date": "date",
    "trip_date": "date",
    "departure_time": "time",
    "product": "text",
    "rate_type": "rate",
    "channel": "channel",
    "party_size": "int",
    "addons_count": "int",
    "price_alert_flag": "flag",
    "booking_value_usd": "money",
    "status": "text",
}
BOOKING_REQUIRED = ("booking_id", "booked_date", "trip_date", "rate_type", "channel")

OUTCOME_COLUMNS = {
    "booking_id": "id",
    "outcome": "outcome",
    "outcome_date": "date",
}
OUTCOME_REQUIRED = ("booking_id", "outcome")

OUTCOME_CODES = (
    "kept",
    "changed_in_window",
    "cancelled_in_window",
    "cancelled_late",
    "operator_cancelled",
)

ALIASES = {
    "id": "booking_id", "booking": "booking_id", "booking_number": "booking_id",
    "reservation_id": "booking_id", "confirmation_id": "booking_id",
    "created": "booked_date", "created_at": "booked_date", "created_date": "booked_date",
    "booking_date": "booked_date", "date_booked": "booked_date",
    "activity_date": "trip_date", "start_date": "trip_date", "tour_date": "trip_date",
    "arrival_date": "trip_date", "check_in": "trip_date",
    "start_time": "departure_time", "time": "departure_time",
    "item": "product", "activity": "product", "tour": "product", "product_name": "product",
    "item_name": "product", "activity_name": "product", "tour_name": "product",
    "rate": "rate_type", "rate_plan": "rate_type", "cancellation_type": "rate_type",
    "source": "channel", "sales_channel": "channel", "booking_channel": "channel",
    "guests": "party_size", "pax": "party_size", "guest_count": "party_size",
    "addons": "addons_count", "add_ons": "addons_count", "add_on_count": "addons_count",
    "price_alert": "price_alert_flag", "value_usd": "booking_value_usd", "total_usd": "booking_value_usd",
    "result": "outcome", "final_status": "outcome",
}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")


class AdapterError(ValueError):
    """The file cannot be used (for example, a required column is missing)."""


def normalize_header(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return ALIASES.get(key, key)


def _parse_date(value: str) -> dt.date | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_rate(value: str) -> str:
    v = re.sub(r"[^a-z]", "", (value or "").lower())
    if v in ("flexible", "flex", "refundable", "freecancellation", "standard"):
        return "flexible"
    if v in ("nonrefundable", "nonref", "nr", "prepaid", "advancepurchase"):
        return "non_refundable"
    return "unknown"


def _parse_channel(value: str) -> str:
    v = (value or "").strip().lower()
    if v in ("direct", "website", "web", "own website", "phone", "walk-in", "walk in", "office"):
        return "direct"
    if v in ("ota", "viator", "getyourguide", "expedia", "tripadvisor", "booking.com", "klook", "airbnb"):
        return "ota"
    if v in ("hotel desk", "hotel_desk", "hoteldesk", "concierge"):
        return "hotel_desk"
    return "other" if v else "unknown"


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_flag(value: str) -> int | None:
    v = (value or "").strip().lower()
    if v in ("1", "true", "yes", "y"):
        return 1
    if v in ("0", "false", "no", "n"):
        return 0
    return None


def _parse_money(value: str) -> float | None:
    v = re.sub(r"[^0-9.]", "", value or "")
    try:
        return round(float(v), 2) if v else None
    except ValueError:
        return None


def _parse_time(value: str) -> str:
    v = (value or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", v)
    if m:
        return "%d:%s" % (int(m.group(1)), m.group(2))
    return ""


class LoadLog:
    """Collects what the adapter dropped. Holds column names and row numbers, never values."""

    def __init__(self, source: str):
        self.source = source
        self.lines: list[str] = []

    def add(self, msg: str) -> None:
        self.lines.append(msg)

    def write(self, log_dir: str | None) -> str | None:
        if not log_dir:
            return None
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "adapter-log.txt")
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("%s  loaded %s\n" % (stamp, os.path.basename(self.source)))
            for line in self.lines:
                fh.write("%s  %s\n" % (stamp, line))
        return path


def _load(path: str, allowed: dict, required: tuple, kind: str, log_dir: str | None):
    log = LoadLog(path)
    if not os.path.exists(path):
        raise AdapterError("File not found: %s" % path)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise AdapterError("The file is empty: %s" % path)
        keep: dict[int, str] = {}
        for idx, raw in enumerate(header):
            name = normalize_header(raw)
            if column_looks_personal(name) and name not in ("booking_id",):
                log.add("dropped column '%s': looks like personal or payment data" % raw.strip())
                continue
            if name not in allowed:
                log.add("dropped column '%s': not on the allow-list" % raw.strip())
                continue
            if name in keep.values():
                log.add("dropped column '%s': duplicate of %s" % (raw.strip(), name))
                continue
            keep[idx] = name
        missing = [c for c in required if c not in keep.values()]
        if missing:
            raise AdapterError(
                "%s file is missing required column(s): %s. Rename the export's columns or add an alias."
                % (kind, ", ".join(missing))
            )
        rows = []
        seen = set()
        for line_no, raw_row in enumerate(reader, start=2):
            if not any(cell.strip() for cell in raw_row):
                continue
            row: dict = {}
            for idx, name in keep.items():
                value = raw_row[idx] if idx < len(raw_row) else ""
                typ = allowed[name]
                if typ in ("text", "id", "outcome"):
                    kinds = pii_kinds(value) if typ != "id" else []
                    if kinds:
                        log.add("blanked a value in column '%s' on line %d: looked like %s"
                                % (name, line_no, " and ".join(kinds)))
                        value = ""
                if typ == "id":
                    value = value.strip()
                    if not ID_RE.match(value) or pii_kinds(value):
                        log.add("skipped line %d: booking_id is missing or not a plain ID" % line_no)
                        row = None
                        break
                    row[name] = value
                elif typ == "date":
                    row[name] = _parse_date(value)
                elif typ == "time":
                    row[name] = _parse_time(value)
                elif typ == "rate":
                    row[name] = _parse_rate(value)
                elif typ == "channel":
                    row[name] = _parse_channel(value)
                elif typ == "int":
                    row[name] = _parse_int(value)
                elif typ == "flag":
                    row[name] = _parse_flag(value)
                elif typ == "money":
                    row[name] = _parse_money(value)
                elif typ == "outcome":
                    v = value.strip().lower()
                    row[name] = v if v in OUTCOME_CODES else ""
                    if not row[name]:
                        log.add("line %d: unknown outcome code, left blank" % line_no)
                else:
                    row[name] = value.strip()[:80]
            if row is None:
                continue
            if kind == "Bookings" and (row.get("booked_date") is None or row.get("trip_date") is None):
                log.add("skipped line %d: booked_date or trip_date is not a date" % line_no)
                continue
            if row["booking_id"] in seen:
                log.add("skipped line %d: duplicate booking_id" % line_no)
                continue
            seen.add(row["booking_id"])
            rows.append(row)
    log.write(log_dir)
    return rows, log


def load_bookings(path: str, log_dir: str | None = None):
    """Return (rows, log). Rows hold allow-listed, typed fields only."""
    return _load(path, BOOKING_COLUMNS, BOOKING_REQUIRED, "Bookings", log_dir)


def load_outcomes(path: str, log_dir: str | None = None):
    """Return (rows, log) for an outcomes export (booking_id, outcome, outcome_date)."""
    return _load(path, OUTCOME_COLUMNS, OUTCOME_REQUIRED, "Outcomes", log_dir)
