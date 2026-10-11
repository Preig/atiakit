"""Shared result type for every provider."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DraftResult:
    text: str = ""
    status: str = "OK"      # OK | REFUSED | TRUNCATED | EMPTY | ERROR
    detail: str = ""        # short reason for anything other than OK; never contains keys
    model: str = ""         # provider:model that produced the text

    @property
    def ok(self) -> bool:
        return self.status == "OK" and bool(self.text.strip())
