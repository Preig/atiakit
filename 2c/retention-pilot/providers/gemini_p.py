"""Gemini provider (Google Gen AI SDK). NOT TESTED AGAINST A LIVE API in this kit.

Before a real run, check the current google-genai SDK docs and model list, then test on fictional data.
Settings:
  GEMINI_API_KEY   your key (never in a shared file)
  GEMINI_MODEL     default gemini-3.8-flash. Configurable default: check current model names before use.
"""
from __future__ import annotations

import os

from providers.base import DraftResult

DEFAULT_MODEL = "gemini-3.8-flash"  # configurable default; check current model names before use


class GeminiProvider:
    name = "gemini"

    def __init__(self, client=None, model: str | None = None):
        self._types = None
        if client is None:
            from google import genai  # pip install google-genai
            from google.genai import types
            client = genai.Client()
            self._types = types
        self.client = client
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL

    def draft(self, system: str, user: str) -> DraftResult:
        tag = "gemini:%s" % self.model
        try:
            if self._types is not None:
                config = self._types.GenerateContentConfig(system_instruction=system)
            else:
                config = {"system_instruction": system}
            resp = self.client.models.generate_content(model=self.model, contents=user, config=config)
        except Exception as exc:  # SDK not verified here; report the class name only, never the key
            return DraftResult(status="ERROR", detail=type(exc).__name__, model=tag)
        text = getattr(resp, "text", "") or ""
        if not text.strip():
            return DraftResult(status="EMPTY", detail="no text (possible safety block)", model=tag)
        return DraftResult(text=text, status="OK", model=tag)
