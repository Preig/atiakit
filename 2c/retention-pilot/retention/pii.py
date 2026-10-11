"""Pattern checks for personal data. Used on column names, cell values and drafts.

These are guards, not guarantees. A person still reviews every export and every draft.
"""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# North American phone numbers: 907-555-0100, (907) 555 0100, +1 907.555.0100
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

# Column names that suggest personal or payment data. A match is always dropped,
# even if someone adds the column to the allow-list by mistake.
PII_COLUMN_RE = re.compile(
    r"name|e-?mail|phone|mobile|cellular|^cell$|cell_|card|cc_|cvv|cvc|payment|iban|routing|account|"
    r"address|street|zip|postal|passport|dob|birth|licen[cs]e|ssn|medical|allerg|diet|"
    r"health|note|comment|message|special_request",
    re.IGNORECASE,
)


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def find_cards(text: str) -> list[str]:
    hits = []
    for m in CARD_CANDIDATE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            hits.append(m.group(0))
    return hits


def pii_kinds(text: str) -> list[str]:
    """Return the kinds of personal data found in text, never the values."""
    kinds = []
    if not text:
        return kinds
    if EMAIL_RE.search(text):
        kinds.append("email")
    if PHONE_RE.search(text):
        kinds.append("phone")
    if find_cards(text):
        kinds.append("card number")
    return kinds


def column_looks_personal(normalized_name: str) -> bool:
    return bool(PII_COLUMN_RE.search(normalized_name))
