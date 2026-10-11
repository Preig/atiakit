"""Message planning, template filling, model prompts, local checks and the approval queue.

Three message types, and nothing else:
  A  Confidence note: what to expect, the weather plan, how to review or change the booking,
     and a named person who can step in.
  B  One add-on from approved_addons.csv.
  C  Lock-in offer, only on terms the owner writes into rules.json.

Every draft starts with DRAFT - PENDING OWNER REVIEW and lands in approval_queue.csv as PENDING.
This module has no code that sends anything.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import re

from retention import DRAFT_MARKER
from retention.pii import EMAIL_RE, PHONE_RE, find_cards
from retention.rules import all_true

MESSAGE_INFO = {
    "A": ("Confidence note",
          "what to expect, the weather plan, how to review or change the booking, "
          "and a named person who can step in"),
    "B": ("One add-on", "one relevant add-on from the approved list, clearly optional"),
    "C": ("Lock-in offer", "an offer to switch to a non-refundable booking, only on the owner's written terms"),
}
TEMPLATE_FILES = {"A": "A_confidence.md", "B": "B_addon.md", "C": "C_lockin.md"}

QUEUE_FIELDS = [
    "queue_id", "created_on", "booking_id", "arm", "message_type", "message_name",
    "suggested_send_date", "trip_date", "subject", "draft_text", "drafted_by", "checks",
    "status", "approved_by", "approved_on", "reviewer_notes",
]

FILL_RE = re.compile(r"\[FILL[^\]]*\]")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z]+)\.([a-z0-9_]+)\s*\}\}|\{\{\s*(terms)\s*\}\}")
NUMBER_RE = re.compile(r"\d[\d,]*(?:[.:]\d+)?")
FACT_LINE_RE = re.compile(r"^\s*-\s*([a-z][a-z0-9_]*)\s*:\s*(.+?)\s*$")


# ---------------------------------------------------------------- loading

def load_facts(path: str):
    """Read approved_facts.md. Lines like '- meeting_point: ...' become keys. Returns (dict, full_text)."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    facts = {}
    for line in text.splitlines():
        m = FACT_LINE_RE.match(line)
        if m and not m.group(2).startswith("[FILL"):
            facts[m.group(1)] = m.group(2)
    return facts, text


def load_addons(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("addon_id") or "").strip()]


def load_template(path: str):
    """Template format: 'Subject: ...' on the first line, a line with '---', then the body."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, _, body = text.partition("\n---\n")
    subject = head.strip()
    if subject.lower().startswith("subject:"):
        subject = subject[len("subject:"):].strip()
    return subject, body.strip("\n"), text


# ---------------------------------------------------------------- booking context

def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _date(v):
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def typed_booking(row: dict) -> dict:
    """Assignment-store rows are text; give rules the types they expect."""
    b = dict(row)
    for k in ("party_size", "addons_count", "price_alert_flag", "lead_time_days", "score_at_assignment"):
        b[k] = _int(row.get(k))
    for k in ("trip_date", "booked_date"):
        b[k] = _date(row.get(k))
    return b


def long_date(d: dt.date | None) -> str:
    if not d:
        return ""
    return "%s, %s %d, %d" % (d.strftime("%A"), d.strftime("%B"), d.day, d.year)


def booking_context(b: dict) -> dict:
    """Only non-personal booking fields are ever placed in a draft or a prompt."""
    return {
        "booking_id": b.get("booking_id", ""),
        "trip_date_long": long_date(b.get("trip_date")),
        "trip_date": b["trip_date"].isoformat() if b.get("trip_date") else "",
        "departure_time": b.get("departure_time") or "",
        "party_size": "" if b.get("party_size") is None else str(b["party_size"]),
        "rate_type": {"flexible": "flexible", "non_refundable": "non-refundable"}.get(b.get("rate_type"), ""),
        "channel": b.get("channel") or "",
    }


# ---------------------------------------------------------------- planning

def parse_fits(text: str) -> list[dict]:
    """'departure_time==9:00; party_size<=6' -> conditions. 'any' or blank -> []."""
    conds = []
    for part in (text or "").split(";"):
        part = part.strip()
        if not part or part.lower() == "any":
            continue
        m = re.match(r"^([a-z_]+)\s*(>=|<=|==|!=|>|<)\s*(.+)$", part)
        if not m:
            continue
        value = m.group(3).strip()
        if re.fullmatch(r"-?\d+", value):
            value = int(value)
        conds.append({"field": m.group(1), "op": m.group(2), "value": value})
    return conds


def choose_addon(b: dict, addons: list[dict]):
    for a in addons:
        if all_true(b, parse_fits(a.get("fits_when", ""))):
            return a
    return None


def plan_messages(b: dict, rules: dict, addons: list[dict]):
    """Return a list of planned messages for one treatment booking.

    Each item: {"type", "send_date", "addon"} or {"type", "skip": reason}. A always comes first
    (confidence first). At most one follow-up: B or C, in the order listed in rules.json.
    """
    m = rules["messages"]
    plans = []
    booked, trip = b.get("booked_date"), b.get("trip_date")
    if not booked or not trip:
        return [{"type": "A", "skip": "booking has no valid dates"}]
    first = m["first"]
    a_date = booked + dt.timedelta(days=int(first.get("days_after_booking", 1)))
    if (trip - a_date).days < int(first.get("min_days_before_trip", 3)):
        return [{"type": "A", "skip": "trip is too soon after booking for an extra message"}]
    plans.append({"type": "A", "send_date": a_date, "addon": None})

    f_date = a_date + dt.timedelta(days=int(m.get("followup_days_after_first", 14)))
    terms = (m.get("lockin_terms") or "").strip()
    for f in m.get("followups", []):
        if not all_true(b, f.get("when", [])):
            continue
        ftype = f["type"]
        chans = f.get("channels")
        if chans and b.get("channel") not in chans:
            plans.append({"type": ftype, "skip": "message %s goes only to %s bookings; this one is %s (Contractual: check your OTA or hotel-desk agreement)"
                          % (ftype, " or ".join(chans), b.get("channel") or "unknown")})
            continue
        addon = None
        if f.get("needs") == "matching_addon":
            addon = choose_addon(b, addons)
            if not addon:
                plans.append({"type": ftype, "skip": "no approved add-on fits this booking"})
                continue
        if f.get("needs") == "lockin_terms" and not terms:
            plans.append({"type": ftype, "skip": "no owner lock-in terms in rules.json (Policy choice)"})
            continue
        if (trip - f_date).days < int(m.get("followup_min_days_before_trip", 10)):
            plans.append({"type": ftype, "skip": "trip is too close for a follow-up"})
            continue
        plans.append({"type": ftype, "send_date": f_date, "addon": addon})
        break
    return plans


# ---------------------------------------------------------------- templates

def render(text: str, facts: dict, ctx: dict, addon: dict | None, terms: str) -> str:
    def repl(m):
        if m.group(3) == "terms":
            return terms.strip() if terms and terms.strip() else "[FILL: owner lock-in terms]"
        ns, key = m.group(1), m.group(2)
        src = {"fact": facts, "booking": ctx, "addon": addon or {}}.get(ns, {})
        val = (src.get(key) or "").strip() if isinstance(src.get(key), str) else src.get(key)
        if val in (None, ""):
            return "[FILL: %s]" % key.replace("_", " ")
        return str(val)
    return PLACEHOLDER_RE.sub(repl, text)


def dry_run_draft(mtype: str, template_dir: str, facts: dict, ctx: dict, addon, terms: str):
    subject_t, body_t, _ = load_template(os.path.join(template_dir, TEMPLATE_FILES[mtype]))
    subject = render(subject_t, facts, ctx, addon, terms)
    body = render(body_t, facts, ctx, addon, terms)
    return subject, "%s\nSubject: %s\n\n%s" % (DRAFT_MARKER, subject, body)


# ---------------------------------------------------------------- model prompt

SYSTEM_PROMPT = """You draft one post-booking message for a small tour business. A person reviews every draft before anything is sent. You never send anything.

Rules:
1. Use only the APPROVED FACTS, the APPROVED ADD-ON and the OWNER TERMS below. They are the only facts you may state.
2. Write message type {mtype} ({mname}) only: {mpurpose}. Keep the structure of the template.
3. If the template or the guest would need a fact that is not supplied, write [FILL: what is missing]. Keep every [FILL] from the template that you cannot fill from the approved sources. Do not guess.
4. Do not state any price, date, time, number, discount, refund, credit or policy that is not in the approved sources.
5. Do not mention competitors, other prices, price matching or price drops. Do not offer refunds, credits, upgrades or exceptions beyond the owner terms.
6. Do not promise wildlife sightings, weather or safety outcomes. Weather and go/no-go decisions belong to the captain.
7. No guest names or personal details. Start with "Hello," because the booking platform adds names on its side.
8. Plain, warm, short sentences in American English. Body under {max_words} words.
9. First line exactly: {marker}
   Second line: Subject: (a short subject line)
   Then a blank line and the message body. Output only the message."""


def model_prompt(mtype: str, facts_text: str, dry_text: str, ctx: dict, addon, terms: str, max_words: int):
    name, purpose = MESSAGE_INFO[mtype]
    system = SYSTEM_PROMPT.format(mtype=mtype, mname=name, mpurpose=purpose, max_words=max_words, marker=DRAFT_MARKER)
    parts = [
        "APPROVED FACTS:\n<facts>\n%s\n</facts>" % facts_text.strip(),
        "BOOKING (no personal data):\n" + "\n".join("- %s: %s" % (k, v) for k, v in ctx.items() if v),
    ]
    if addon:
        parts.append("APPROVED ADD-ON:\n" + "\n".join(
            "- %s: %s" % (k, v) for k, v in addon.items() if k in ("name", "description", "price_line", "how_to_book") and v))
    if mtype == "C":
        parts.append("OWNER TERMS (quote them exactly, do not change them):\n%s" % (terms or "[FILL: owner lock-in terms]"))
    parts.append("TEMPLATE, already filled from the approved facts. Improve the wording only; keep the facts and every [FILL]:\n<template>\n%s\n</template>" % dry_text)
    return system, "\n\n".join(parts)


def split_model_text(text: str, fallback_subject: str):
    """Pull the subject from the model's text. Returns (subject, full_text_with_marker, marker_added)."""
    text = (text or "").strip()
    marker_added = False
    if not text.startswith(DRAFT_MARKER):
        text = "%s\n%s" % (DRAFT_MARKER, text)
        marker_added = True
    subject = fallback_subject
    for line in text.splitlines()[1:4]:
        if line.lower().startswith("subject:"):
            subject = line[len("subject:"):].strip() or fallback_subject
            break
    return subject, text, marker_added


# ---------------------------------------------------------------- checks

def _tokens(text: str) -> list:
    out = []
    for tok in NUMBER_RE.findall(text or ""):
        tok = tok.replace(",", "").rstrip(".:")
        if tok:
            out.append(tok)
    return out


def _variants(tok: str) -> set:
    """'9:00' -> {'9:00', '9', '0'}; '0142' -> {'0142', '142'}."""
    v = {tok}
    for part in re.split(r"[.:]", tok):
        if part:
            v.add(part)
            if part.isdigit():
                v.add(str(int(part)))
    if tok.isdigit():
        v.add(str(int(tok)))
    return v


def _numbers(text: str) -> set:
    out = set()
    for tok in _tokens(text):
        out |= _variants(tok)
    return out


def check_draft(text: str, allowed_text: str, rules: dict, max_words: int | None = None) -> list[str]:
    """Local checks on a draft. Returns a list of flags; an empty list means no flags (not 'approved')."""
    flags = []
    body = text or ""
    low, allowed_low = body.lower(), (allowed_text or "").lower()
    if not body.startswith(DRAFT_MARKER):
        flags.append("missing the DRAFT marker")
    fills = FILL_RE.findall(body)
    if fills:
        flags.append("%d open [FILL] item(s): a person fills or removes them" % len(fills))
    allowed_nums = _numbers(allowed_text)
    body_wo_fills = FILL_RE.sub(" ", body)
    new_nums = []
    for tok in _tokens(body_wo_fills):
        norm = str(int(tok)) if tok.isdigit() else tok
        if tok not in allowed_nums and norm not in allowed_nums and tok not in new_nums:
            new_nums.append(tok)
    if new_nums:
        flags.append("number(s) not in the approved sources: %s" % ", ".join(new_nums[:8]))
    for phrase in rules["checks"].get("banned_phrases", []):
        p = phrase.lower()
        if p in low and p not in allowed_low:
            flags.append("banned phrase: '%s'" % phrase)
    for phrase in rules["checks"].get("promise_phrases", []):
        p = phrase.lower()
        if p in low and p not in allowed_low:
            flags.append("promise wording, check it: '%s'" % phrase)
    for m in EMAIL_RE.findall(body):
        if m.lower() not in allowed_low:
            flags.append("an email address that is not in the approved facts")
            break
    for m in PHONE_RE.findall(body):
        if m not in (allowed_text or ""):
            flags.append("a phone number that is not in the approved facts")
            break
    if find_cards(body):
        flags.append("a number that looks like a card number")
    if max_words:
        words = len(re.findall(r"\b\w+\b", body.split("\n", 2)[-1]))
        if words > max_words:
            flags.append("about %d words, over the %d-word limit" % (words, max_words))
    return flags


# ---------------------------------------------------------------- queue

def read_queue(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_queue(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=QUEUE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in QUEUE_FIELDS})
