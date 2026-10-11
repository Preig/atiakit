"""OpenAI provider (Responses API). NOT TESTED AGAINST A LIVE API in this kit.

Before a real run, check the current OpenAI Python SDK docs and model list, then test on fictional data.
Settings:
  OPENAI_API_KEY   your key (never in a shared file)
  OPENAI_MODEL     default gpt-5.5. Configurable default: check current model names before use.
"""
from __future__ import annotations

import os

from providers.base import DraftResult

DEFAULT_MODEL = "gpt-5.5"  # configurable default; check current model names before use


class OpenAIProvider:
    name = "openai"

    def __init__(self, client=None, model: str | None = None):
        if client is None:
            from openai import OpenAI  # pip install openai
            client = OpenAI()
        self.client = client
        self.model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL

    def draft(self, system: str, user: str) -> DraftResult:
        tag = "openai:%s" % self.model
        try:
            resp = self.client.responses.create(model=self.model, instructions=system, input=user)
        except Exception as exc:  # SDK not verified here; report the class name only, never the key
            return DraftResult(status="ERROR", detail=type(exc).__name__, model=tag)
        text = getattr(resp, "output_text", "") or ""
        if getattr(resp, "status", "completed") == "incomplete":
            return DraftResult(text=text, status="TRUNCATED", detail="response incomplete", model=tag)
        if not text.strip():
            return DraftResult(status="EMPTY", detail="no text (possible refusal)", model=tag)
        return DraftResult(text=text, status="OK", model=tag)
