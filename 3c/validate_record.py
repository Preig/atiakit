#!/usr/bin/env python3
"""Check an agent-ready trip record (tool 3.c, ATIA AI Take-Home Kit, Alaska SBDC).

Standard library only. Python 3.10 or newer. Nothing is sent anywhere.

    python validate_record.py trip-record.example.json
    python validate_record.py my-record.json --json
    python validate_record.py - < my-record.json

Three layers of checks:
  1. Schema: the rules in trip-record.schema.json (the subset of JSON Schema
     2020-12 that the schema uses: $ref, type, enum, const, required,
     properties, additionalProperties, items, min/max, pattern, format, not, anyOf).
  2. Personal data: field names and text that look like names, emails, phone,
     card, account or ID numbers, street addresses (errors) or health details (warnings).
  3. Record rules the schema cannot express: age-band counts add up to the party,
     depart is not before arrive, a hold expires after it was placed, and so on.

Exit code 0 = valid, 1 = not valid, 2 = could not read the input.

A regex scan is a guard rail, not a guarantee. It misses names written in plain
text, for example. Keep guest names, contact details, payment data and health
details out of trip records in the first place.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA_FILE = HERE / "trip-record.schema.json"

__all__ = ["Issue", "Result", "load_schema", "validate", "scan_personal_data", "main"]


@dataclass
class Issue:
    path: str      # JSON Pointer, for example /holds/0/expires_at ("" is the whole record)
    message: str
    kind: str      # "schema", "personal-data" or "rule"
    level: str = "error"   # "error" or "warning"


class Result:
    def __init__(self) -> None:
        self.errors: list[Issue] = []
        self.warnings: list[Issue] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, issue: Issue) -> None:
        bucket = self.errors if issue.level == "error" else self.warnings
        if not any(i.path == issue.path and i.message == issue.message for i in bucket):
            bucket.append(issue)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.ok,
            "errors": [asdict(i) for i in self.errors],
            "warnings": [asdict(i) for i in self.warnings],
        }

    def summary(self) -> str:
        e, w = len(self.errors), len(self.warnings)
        word = "VALID" if self.ok else "NOT VALID"
        return f"{word} ({e} error{'s' if e != 1 else ''}, {w} warning{'s' if w != 1 else ''})"


# --------------------------------------------------------------------------- schema

def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    with open(path or SCHEMA_FILE, encoding="utf-8") as fh:
        return json.load(fh)


PATTERN_HINTS = {
    "^TR-[A-Z0-9]+(-[A-Z0-9]+)*$": "Use an opaque id like TR-DEMO-0714. Never a name, email or booking reference.",
    "^[A-Z0-9]+(-[A-Z0-9]+)*$": "Use capital letters, digits and hyphens, like BL-CRUISE-4H.",
    "^([01][0-9]|2[0-3]):[0-5][0-9]$": "Use 24-hour time, like 09:00.",
    "^Q[0-9]{1,3}$": "Use Q plus a number, like Q1.",
    "^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$": "Use letters, digits, hyphens or underscores (3 to 64 characters).",
}
FORMAT_HINTS = {
    "date": "Use a real date like 2027-07-15.",
    "date-time": "Use a real date and time with a time zone, like 2026-10-10T18:30:00Z.",
}
PERSONAL_DATA_REF = "#/$defs/looksLikePersonalData"
GENERIC_PERSONAL = "This text looks like personal data (an email, phone, card or ID number). Remove it."


def _json_type(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _is_type(v: Any, t: str) -> bool:
    jt = _json_type(v)
    if t == "number":
        return jt in ("integer", "number")
    if t == "integer":
        return jt == "integer" or (jt == "number" and float(v).is_integer())
    return jt == t


def _canon(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _resolve(ref: str, root: dict[str, Any]) -> Any:
    if not ref.startswith("#/"):
        raise ValueError(f"Only local $ref values are supported, not {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})", re.ASCII)
_DATETIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-](\d{2}):(\d{2}))", re.ASCII)


def _valid_date(value: str) -> bool:
    m = _DATE_RE.fullmatch(value)
    if not m:
        return False
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return True


def _valid_date_time(value: str) -> bool:
    # RFC 3339 only: hour 00 to 23 (no 24:00), a time zone is required. Same rules as trip-record-check.js.
    m = _DATETIME_RE.fullmatch(value)
    if not m or not _valid_date(m.group(1)):
        return False
    if int(m.group(2)) > 23 or int(m.group(3)) > 59 or (m.group(4) is not None and int(m.group(4)) > 59):
        return False
    if m.group(6) is not None and (int(m.group(6)) > 23 or int(m.group(7)) > 59):
        return False
    return True


def _valid_format(value: str, fmt: str) -> bool:
    if fmt == "date":
        return _valid_date(value)
    if fmt == "date-time":
        return _valid_date_time(value)
    return True


def _ptr(path: str, key: str | int) -> str:
    return f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}"


def _check(inst: Any, sch: Any, path: str, root: dict[str, Any], out: list[Issue]) -> None:
    if sch is True:
        return
    if sch is False:
        out.append(Issue(path, "No value is allowed here.", "schema"))
        return
    if "$ref" in sch:
        _check(inst, _resolve(sch["$ref"], root), path, root, out)

    if "type" in sch:
        types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is_type(inst, t) for t in types):
            out.append(Issue(path, f"Expected {' or '.join(types)}, found {_json_type(inst)}.", "schema"))
            return

    if "const" in sch and _canon(inst) != _canon(sch["const"]):
        msg = f"Use {json.dumps(sch['const'])}."
        if path.endswith("/agent_may_confirm"):
            msg = "Use false. In this design an agent may hold and ask; a person at the business confirms."
        out.append(Issue(path, msg, "schema"))
    if "enum" in sch and all(_canon(inst) != _canon(e) for e in sch["enum"]):
        out.append(Issue(path, "Use one of: " + ", ".join(json.dumps(e) for e in sch["enum"]) + ".", "schema"))

    if isinstance(inst, str):
        n = len(inst)
        if "minLength" in sch and n < sch["minLength"]:
            out.append(Issue(path, f"Too short (at least {sch['minLength']} characters).", "schema"))
        if "maxLength" in sch and n > sch["maxLength"]:
            out.append(Issue(path, f"Too long ({n} characters; the limit is {sch['maxLength']}).", "schema"))
        fmt_bad = "format" in sch and not _valid_format(inst, sch["format"])
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            hint = FORMAT_HINTS.get(sch.get("format", "")) or PATTERN_HINTS.get(sch["pattern"], "The format is not allowed here.")
            out.append(Issue(path, hint, "schema"))
        elif fmt_bad:
            out.append(Issue(path, FORMAT_HINTS.get(sch["format"], "Wrong format."), "schema"))

    if _json_type(inst) in ("integer", "number"):
        if "minimum" in sch and inst < sch["minimum"]:
            out.append(Issue(path, f"Too small (the minimum is {sch['minimum']}).", "schema"))
        if "maximum" in sch and inst > sch["maximum"]:
            out.append(Issue(path, f"Too large (the maximum is {sch['maximum']}).", "schema"))

    if isinstance(inst, list):
        if "minItems" in sch and len(inst) < sch["minItems"]:
            out.append(Issue(path, f"Needs at least {sch['minItems']} item{'s' if sch['minItems'] != 1 else ''}.", "schema"))
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            out.append(Issue(path, f"Too many items ({len(inst)}; the limit is {sch['maxItems']}).", "schema"))
        if sch.get("uniqueItems") and len({_canon(x) for x in inst}) != len(inst):
            out.append(Issue(path, "An item is repeated.", "schema"))
        if "items" in sch:
            for i, item in enumerate(inst):
                _check(item, sch["items"], _ptr(path, i), root, out)

    if isinstance(inst, dict):
        for key in sch.get("required", []):
            if key not in inst:
                out.append(Issue(path, f"Missing required field \"{key}\".", "schema"))
        props = sch.get("properties", {})
        for key, val in inst.items():
            if key in props:
                _check(val, props[key], _ptr(path, key), root, out)
            elif "additionalProperties" in sch:
                ap = sch["additionalProperties"]
                if ap is False:
                    if not _personal_key(key):   # the personal-data scan reports those with a clearer message
                        out.append(Issue(_ptr(path, key), f"Field \"{key}\" is not part of the trip record. Remove it or rename it to a schema field.", "schema"))
                else:
                    _check(val, ap, _ptr(path, key), root, out)

    if "allOf" in sch:
        for sub in sch["allOf"]:
            _check(inst, sub, path, root, out)
    if "anyOf" in sch:
        branches = []
        for sub in sch["anyOf"]:
            tmp: list[Issue] = []
            _check(inst, sub, path, root, tmp)
            branches.append(tmp)
        if all(branches):
            out.append(Issue(path, "Does not match any allowed form.", "schema"))
    if "not" in sch:
        tmp = []
        _check(inst, sch["not"], path, root, tmp)
        if not tmp:
            if sch["not"] == {"$ref": PERSONAL_DATA_REF}:
                out.append(Issue(path, GENERIC_PERSONAL, "personal-data"))
            else:
                out.append(Issue(path, "This value is not allowed here.", "schema"))


# --------------------------------------------------------------------------- personal data

# Field names that never belong in a trip record (compared after removing case, spaces, _ and -).
PERSONAL_KEYS_EXACT = {
    "name", "firstname", "lastname", "fullname", "surname", "givenname", "familyname", "guestname",
    "travelername", "leadname", "contactname", "passengername", "contact", "address", "street",
    "streetaddress", "homeaddress", "zip", "zipcode", "postcode", "postalcode", "dob", "birthday",
    "gender", "nationality", "ip", "ipaddress", "deviceid", "medical", "health",
    "allergies", "allergy", "diet", "dietary", "disability", "medication", "medications",
}
PERSONAL_KEY_TOKENS = (
    "email", "phone", "mobile", "telephone", "cell", "sms", "whatsapp", "card", "cvv", "cvc",
    "iban", "routing", "account", "payment", "billing", "passport", "license", "licence", "ssn",
    "socialsecurity", "birth", "loyalty", "membership", "password", "token",
)


def _personal_key(key: str) -> bool:
    k = re.sub(r"[\s_\-]", "", key.lower())
    return k in PERSONAL_KEYS_EXACT or any(t in k for t in PERSONAL_KEY_TOKENS)


RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_PHONE = re.compile(r"(?:^|[^0-9A-Za-z])((?:\+?1[ .-]?)?\(?[2-9][0-9]{2}\)?[ .-]?[0-9]{3}[ .-]?[0-9]{4})(?![0-9A-Za-z])")
RE_LONGNUM = re.compile(r"(?:^|[^0-9])((?:[0-9][ -]?){12,18}[0-9])(?![0-9])")
RE_SSN = re.compile(r"(?:^|[^0-9])([0-9]{3}-[0-9]{2}-[0-9]{4})(?![0-9])")
RE_STREET = re.compile(
    r"\b[0-9]{1,6}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Hwy|Highway|Pl|Place|Loop|Cir|Circle)\b"
)
RE_LABEL = re.compile(
    r"\b(name|first name|last name|full name|guest|e-?mail|phone|cell|mobile|tel|card|cvv|cvc|passport|"
    r"driver'?s license|license no|date of birth|dob|ssn|address|account)\s*(?:#|:|=)",
    re.IGNORECASE,
)
RE_TITLE_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Mx|Miss)\.?\s+[A-Z][a-z]+")
RE_FAMILY_NAME = re.compile(r"\b[Tt]he\s+([A-Z][a-z]+)\s+(?:family|party|group)\b")
RE_HEALTH = re.compile(
    r"\b(allerg\w*|anaphyla\w*|diabet\w*|epi-?pen|insulin|medication\w*|medicine|pregnan\w*|seizure\w*|"
    r"epilep\w*|asthma\w*|wheelchair|disabilit\w*|disabled|diagnos\w*|heart condition|surgery|medical)\b",
    re.IGNORECASE,
)


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _scan_text(text: str, path: str, res: Result) -> None:
    if RE_EMAIL.search(text):
        res.add(Issue(path, "Looks like an email address. Remove it: the record never holds contact details.", "personal-data"))
    if RE_SSN.search(text):
        res.add(Issue(path, "Looks like a Social Security number. Remove it.", "personal-data"))
    elif RE_PHONE.search(text):
        res.add(Issue(path, "Looks like a phone number. Remove it: the record never holds contact details.", "personal-data"))
    for m in RE_LONGNUM.finditer(text):
        digits = re.sub(r"[^0-9]", "", m.group(1))
        if 13 <= len(digits) <= 19:
            what = "a payment card number" if _luhn_ok(digits) else "a card, account or ID number"
            res.add(Issue(path, f"Looks like {what} ({len(digits)} digits). Remove it: the record never holds payment data.", "personal-data"))
            break
    if RE_STREET.search(text):
        res.add(Issue(path, "Looks like a street address. Remove it.", "personal-data"))
    m = RE_LABEL.search(text)
    if m:
        res.add(Issue(path, f"Looks like a label for personal data (\"{m.group(0).strip()}\"). Remove the label and the value.", "personal-data"))
    if RE_TITLE_NAME.search(text):
        res.add(Issue(path, "Looks like a person's name (a title such as Mr or Ms followed by a name). Remove it.", "personal-data"))
    fm = RE_FAMILY_NAME.search(text)
    if fm and fm.group(1) not in ("Bay", "Harbor", "Mile"):
        res.add(Issue(path, f"\"{fm.group(0)}\" may be a family name. Describe the party by counts and age bands instead.", "personal-data", "warning"))
    hm = RE_HEALTH.search(text)
    if hm:
        res.add(Issue(path, f"\"{hm.group(0)}\" may be health information about a person. Record a question about the business instead (for example: Is the vessel step-free?), never a person's condition.", "personal-data", "warning"))


def scan_personal_data(record: Any, res: Result | None = None, path: str = "") -> Result:
    """Walk every key and string value and flag anything that looks like personal data."""
    res = res or Result()
    if isinstance(record, dict):
        for key, val in record.items():
            p = _ptr(path, key)
            if _personal_key(key):
                res.add(Issue(p, f"Field \"{key}\" looks like personal data. The trip record never holds names, contact details, payment data, IDs or health details.", "personal-data"))
            scan_personal_data(val, res, p)
    elif isinstance(record, list):
        for i, val in enumerate(record):
            scan_personal_data(val, res, _ptr(path, i))
    elif isinstance(record, str):
        _scan_text(record, path, res)
    return res


# --------------------------------------------------------------------------- record rules

def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not _valid_date_time(value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_d(value: Any) -> date | None:
    return date.fromisoformat(value) if isinstance(value, str) and _valid_date(value) else None


def _int(value: Any) -> bool:
    """A JSON integer (4 or 4.0), never a boolean. Same rule as isInt in trip-record-check.js."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or (isinstance(value, float) and value.is_integer())


def _rules(rec: dict[str, Any], res: Result, now: datetime) -> None:
    party = rec.get("party") if isinstance(rec.get("party"), dict) else {}
    bands = party.get("age_bands") if isinstance(party.get("age_bands"), list) else []
    if _int(party.get("count")) and bands and all(isinstance(b, dict) and _int(b.get("count")) for b in bands):
        total = int(sum(b["count"] for b in bands))
        if total != party["count"]:
            res.add(Issue("/party", f"The age-band counts add up to {total}, but party.count is {int(party['count'])}.", "rule"))
        names = [b.get("band") for b in bands]
        if len(set(names)) != len(names):
            res.add(Issue("/party/age_bands", "An age band is listed twice. Combine the counts.", "rule"))

    dates = rec.get("dates") if isinstance(rec.get("dates"), dict) else {}
    arrive, depart = _parse_d(dates.get("arrive")), _parse_d(dates.get("depart"))
    if arrive and depart:
        if depart < arrive:
            res.add(Issue("/dates", "depart is before arrive.", "rule"))
        elif (depart - arrive).days > 60:
            res.add(Issue("/dates", "The trip is longer than 60 days. Check the dates.", "rule", "warning"))

    def outside(d: date | None) -> bool:
        return bool(d and arrive and depart and (d < arrive or d > depart))

    for list_name in ("shortlisted", "rejected", "holds"):
        items = rec.get(list_name) if isinstance(rec.get(list_name), list) else []
        for i, it in enumerate(items):
            if isinstance(it, dict) and outside(_parse_d(it.get("date"))):
                res.add(Issue(f"/{list_name}/{i}/date", "This date is outside the trip dates.", "rule", "warning"))

    short = rec.get("shortlisted") if isinstance(rec.get("shortlisted"), list) else []
    rej = rec.get("rejected") if isinstance(rec.get("rejected"), list) else []
    key = lambda it: (it.get("product_id"), it.get("date"), it.get("departure"))  # noqa: E731
    rej_keys = {key(r) for r in rej if isinstance(r, dict)}
    for i, s in enumerate(short):
        if isinstance(s, dict) and key(s) in rej_keys:
            res.add(Issue(f"/shortlisted/{i}", "The same option is both short-listed and rejected. Keep it in one list.", "rule", "warning"))

    holds = rec.get("holds") if isinstance(rec.get("holds"), list) else []
    seen: set[str] = set()
    for i, h in enumerate(holds):
        if not isinstance(h, dict):
            continue
        hid = h.get("hold_id")
        if isinstance(hid, str):
            if hid in seen:
                res.add(Issue(f"/holds/{i}/hold_id", f"Hold {hid} is listed twice.", "rule"))
            seen.add(hid)
        placed, expires = _parse_dt(h.get("placed_at")), _parse_dt(h.get("expires_at"))
        if placed and expires and expires <= placed:
            res.add(Issue(f"/holds/{i}/expires_at", "The hold expires before it was placed.", "rule"))
        if h.get("status") in ("active", "pending_staff_confirmation") and expires and expires <= now:
            res.add(Issue(f"/holds/{i}/expires_at",
                          f"Hold {hid} was set to expire at {h.get('expires_at')}, which has passed. A live server reports it as expired "
                          "and the seats go back on sale. That is how a reversible hold works.", "rule", "warning"))
        if h.get("status") == "pending_staff_confirmation" and not h.get("confirmation_id"):
            res.add(Issue(f"/holds/{i}", "A hold waiting for staff has no confirmation_id.", "rule", "warning"))
        if _int(h.get("seats")) and _int(party.get("count")) and h["seats"] > party["count"]:
            res.add(Issue(f"/holds/{i}/seats", "The hold has more seats than the party has people.", "rule", "warning"))

    consent = rec.get("consent") if isinstance(rec.get("consent"), dict) else {}
    live = [h for h in holds if isinstance(h, dict) and h.get("status") in ("active", "pending_staff_confirmation", "confirmed")]
    if live and consent.get("agent_may_place_holds") is False:
        res.add(Issue("/consent/agent_may_place_holds", "The record has holds, but consent says the agent may not place holds.", "rule"))
    if consent.get("traveler_reviewed") is False and live:
        res.add(Issue("/consent/traveler_reviewed", "There are holds the traveler has not reviewed yet. Review comes before confirmation.", "rule", "warning"))

    qs = rec.get("open_questions") if isinstance(rec.get("open_questions"), list) else []
    qids: set[str] = set()
    for i, q in enumerate(qs):
        if not isinstance(q, dict):
            continue
        if q.get("status") == "answered" and not q.get("answer"):
            res.add(Issue(f"/open_questions/{i}", "Marked answered, but there is no answer.", "rule", "warning"))
        qid = q.get("id")
        if isinstance(qid, str):
            if qid in qids:
                res.add(Issue(f"/open_questions/{i}/id", f"Question id {qid} is used twice.", "rule"))
            qids.add(qid)


# --------------------------------------------------------------------------- entry points

def validate(record: Any, schema: dict[str, Any] | None = None, now: datetime | None = None) -> Result:
    """Return a Result with errors and warnings. `now` is for tests; it defaults to the current UTC time."""
    schema = schema or load_schema()
    now = now or datetime.now(timezone.utc)
    res = Result()
    found: list[Issue] = []
    _check(record, schema, "", schema, found)
    for issue in found:
        res.add(issue)
    scan_personal_data(record, res)
    # Keep the schema's generic personal-data message only where the scan found nothing more specific.
    specific = {i.path for i in res.errors if i.kind == "personal-data" and i.message != GENERIC_PERSONAL}
    res.errors = [i for i in res.errors if not (i.message == GENERIC_PERSONAL and i.path in specific)]
    if isinstance(record, dict):
        _rules(record, res, now)
    return res


def _print_human(name: str, res: Result) -> None:
    print(f"{name}: {res.summary()}")
    for i in res.errors:
        print(f"  error    {i.path or '/'}  {i.message}")
    for i in res.warnings:
        print(f"  warning  {i.path or '/'}  {i.message}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check a trip record against trip-record.schema.json and scan it for personal data. Nothing is sent anywhere.")
    ap.add_argument("files", nargs="+", help="JSON file(s) to check, or - to read from standard input")
    ap.add_argument("--schema", default=str(SCHEMA_FILE), help="path to trip-record.schema.json (default: next to this script)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)

    try:
        schema = load_schema(args.schema)
    except (OSError, ValueError) as exc:
        print(f"Could not read the schema: {exc}", file=sys.stderr)
        return 2

    worst = 0
    report = {}
    for name in args.files:
        try:
            text = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8-sig")
            record = json.loads(text)
        except OSError as exc:
            print(f"{name}: could not read the file ({exc})", file=sys.stderr)
            worst = 2
            continue
        except json.JSONDecodeError as exc:
            print(f"{name}: not valid JSON (line {exc.lineno}, column {exc.colno}: {exc.msg})", file=sys.stderr)
            worst = 2
            continue
        res = validate(record, schema)
        failed = not res.ok or (args.strict and res.warnings)
        if failed and worst == 0:
            worst = 1
        if args.json:
            report[name] = res.to_dict()
        else:
            _print_human(name, res)
    if args.json:
        print(json.dumps(report, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())
