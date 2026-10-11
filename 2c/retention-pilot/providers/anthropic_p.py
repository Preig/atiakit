"""Claude provider, through the official anthropic Python SDK (pip install anthropic).

Settings (environment variables, or a .env file next to pilot.py):
  ANTHROPIC_API_KEY     your key. Never put it in a file you share or commit.
  ANTHROPIC_MODEL       default claude-opus-5-5. Model names change: check
                        https://platform.claude.com/docs/en/about-claude/models before a real run.
  ANTHROPIC_EFFORT      default medium. low | medium | high. Set it empty to leave it out
                        (needed for older models that do not accept effort).
  ANTHROPIC_FALLBACKS   default "default": if the model declines a request for a safety reason,
                        the API retries it on a fallback model it chooses. Set "off" to disable.
  ANTHROPIC_MAX_TOKENS  default 16000. Covers the model's thinking plus the short draft.

The provider only drafts. It cannot send anything.
"""
from __future__ import annotations

import inspect
import os

from providers.base import DraftResult

DEFAULT_MODEL = "claude-opus-5-5"  # configurable default; check current model names before use
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _api_errors() -> tuple:
    try:
        import anthropic
    except ImportError:
        return ()
    return (anthropic.APIStatusError, anthropic.APIConnectionError)


def _explain(exc: Exception) -> str:
    """Short, key-free description, most specific first."""
    try:
        import anthropic
    except ImportError:
        return type(exc).__name__
    if isinstance(exc, anthropic.AuthenticationError):
        return "authentication failed: check ANTHROPIC_API_KEY"
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "the key lacks permission for this model or feature"
    if isinstance(exc, anthropic.NotFoundError):
        return "model not found: check ANTHROPIC_MODEL"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate limited: wait and run draft again (finished drafts are kept)"
    if isinstance(exc, anthropic.BadRequestError):
        return "bad request (%s): check ANTHROPIC_MODEL, ANTHROPIC_EFFORT and ANTHROPIC_FALLBACKS" % getattr(exc, "status_code", 400)
    if isinstance(exc, anthropic.APIStatusError):
        code = getattr(exc, "status_code", 0) or 0
        return "server error %s: try again later" % code if code >= 500 else "API error %s" % code
    if isinstance(exc, anthropic.APIConnectionError):
        return "network error: check the internet connection"
    return type(exc).__name__


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client=None, model: str | None = None, effort: str | None = None,
                 fallbacks: str | None = None, max_tokens: int | None = None):
        if client is None:
            import anthropic  # imported here so dry runs and tests never need the SDK
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY (or another configured credential)
        self.client = client
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
        self.effort = (os.environ.get("ANTHROPIC_EFFORT", "medium") if effort is None else effort).strip()
        fb = (os.environ.get("ANTHROPIC_FALLBACKS", "default") if fallbacks is None else fallbacks).strip()
        self.fallbacks = "" if fb.lower() in ("", "off", "none", "false", "0") else fb
        self.max_tokens = int(max_tokens or os.environ.get("ANTHROPIC_MAX_TOKENS") or 16000)

    def _request(self, system: str, user: str):
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        if not self.fallbacks:
            return self.client.messages.create(**kwargs)
        create = self.client.beta.messages.create
        kwargs["betas"] = [FALLBACK_BETA]
        try:
            params = inspect.signature(create).parameters
        except (TypeError, ValueError):
            params = {}
        if "fallbacks" in params:
            kwargs["fallbacks"] = self.fallbacks
        else:  # SDK versions without a typed fallbacks argument
            kwargs["extra_body"] = {"fallbacks": self.fallbacks}
        return create(**kwargs)

    def draft(self, system: str, user: str) -> DraftResult:
        tag = "anthropic:%s" % self.model
        try:
            resp = self._request(system, user)
        except _api_errors() as exc:
            return DraftResult(status="ERROR", detail=_explain(exc), model=tag)
        served = getattr(resp, "model", None) or self.model
        tag = "anthropic:%s" % served
        stop = getattr(resp, "stop_reason", None)
        if stop == "refusal":
            details = getattr(resp, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            return DraftResult(status="REFUSED", detail="model declined (%s)" % (category or "no category"), model=tag)
        text = "".join(getattr(b, "text", "") for b in (getattr(resp, "content", None) or [])
                       if getattr(b, "type", "") == "text")
        if stop == "max_tokens":
            return DraftResult(text=text, status="TRUNCATED",
                               detail="hit ANTHROPIC_MAX_TOKENS before finishing", model=tag)
        if not text.strip():
            return DraftResult(status="EMPTY", detail="no text in the response", model=tag)
        return DraftResult(text=text, status="OK", model=tag)
