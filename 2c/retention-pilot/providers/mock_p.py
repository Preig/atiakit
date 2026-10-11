"""A stand-in model for teaching and tests. No network, no key.

It returns the filled template from the prompt with one sentence reworded, so the whole
draft path (prompt, response, checks, queue) runs without an API.
Set MOCK_BEHAVIOR=refuse, truncate or error to see how the pipeline handles each case.
"""
from __future__ import annotations

import os
import re

from providers.base import DraftResult


class MockProvider:
    name = "mock"

    def __init__(self, behavior: str | None = None):
        self.behavior = (behavior or os.environ.get("MOCK_BEHAVIOR") or "ok").lower()
        self.model = "mock-model"
        self.calls = 0

    def draft(self, system: str, user: str) -> DraftResult:
        self.calls += 1
        tag = "mock:%s" % self.model
        if self.behavior == "refuse":
            return DraftResult(status="REFUSED", detail="mock refusal", model=tag)
        if self.behavior == "truncate":
            return DraftResult(status="TRUNCATED", detail="mock max_tokens", model=tag)
        if self.behavior == "error":
            return DraftResult(status="ERROR", detail="mock connection error", model=tag)
        m = re.search(r"<template>\n(.*?)\n</template>", user, re.S)
        text = m.group(1) if m else ""
        text = text.replace("Here is what to expect, so there are no surprises.",
                            "Here is what to expect on the day, so nothing surprises you.")
        return DraftResult(text=text, status="OK", model=tag)
