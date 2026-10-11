"""Shared types and helpers for the three provider adapters.

Each adapter (anthropic_p, openai_p, gemini_p) exposes the same small surface:
    NAME, KEY_ENV, config(), available(), ask(prompt, cfg, client),
    check(cfg, client), parse_fixture(raw)
so monitor.py can treat them alike. Nothing here talks to the network.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

# The same instruction goes to every provider so answers stay comparable.
# Keep it neutral: the monitor measures what the tools say, not what we want them to say.
PANEL_INSTRUCTION_DEFAULT = (
    "You are a helpful travel planning assistant. "
    "Use web search for current information before you answer."
)


def panel_instruction() -> str:
    return os.environ.get("PANEL_INSTRUCTION", "").strip() or PANEL_INSTRUCTION_DEFAULT


@dataclass
class Answer:
    """One provider's answer to one prompt, reduced to what the monitor needs."""

    provider: str
    model: str = ""              # model that served the answer, as the API reported it
    tool_version: str = ""       # search tool type string that was sent
    user_location: str = ""      # approximate location sent with the search tool
    text: str = ""
    citations: list[dict] = field(default_factory=list)   # [{"url", "title", "resolved_url"}]
    sources: list[str] = field(default_factory=list)       # URLs retrieved, cited or not
    search_queries: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    search_calls: int = 0
    stop_reason: str = ""
    error: str = ""
    notes: list[str] = field(default_factory=list)
    usage_reported: bool = True

    def add_citation(self, url: str, title: str = "") -> None:
        if not url:
            return
        if any(c["url"] == url for c in self.citations):
            return
        self.citations.append({"url": url, "title": title or "", "resolved_url": ""})

    def add_source(self, url: str) -> None:
        if url and url not in self.sources:
            self.sources.append(url)


def to_dict(obj: Any) -> Any:
    """Turn an SDK response object (pydantic) or a plain dict into plain dicts and lists."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except TypeError:
            return dump()
    to_json = getattr(obj, "to_json", None)
    if callable(to_json):
        try:
            return json.loads(to_json())
        except (TypeError, ValueError):
            pass
    if hasattr(obj, "__dict__"):
        return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def get_any(d: dict | None, *keys: str, default: Any = None) -> Any:
    """First present, non-empty value among several key spellings (snake_case or camelCase)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def as_int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env_str(name, str(default)))
    except ValueError:
        return default


def env_float(name: str) -> float | None:
    v = env_str(name, "")
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def env_bool(name: str, default: bool) -> bool:
    v = env_str(name, "")
    if v == "":
        return default
    return v.lower() in ("1", "true", "yes", "on", "y")


def user_location_from_env() -> dict:
    """Approximate location sent with the search tool. USER_LOCATION=off sends none."""
    if env_str("USER_LOCATION", "").lower() in ("off", "none", "0"):
        return {}
    loc: dict[str, str] = {"type": "approximate"}
    for key, var in (("city", "USER_CITY"), ("region", "USER_REGION"),
                     ("country", "USER_COUNTRY"), ("timezone", "USER_TIMEZONE")):
        v = env_str(var, "")
        if v:
            loc[key] = v
    loc.setdefault("country", "US")
    return loc


def describe_location(loc: dict) -> str:
    if not loc:
        return "none"
    parts = [loc.get("city", ""), loc.get("region", ""), loc.get("country", "")]
    return ", ".join(p for p in parts if p) or "none"


def short_error(exc: BaseException, limit: int = 300) -> str:
    msg = " ".join(str(exc).split())
    return msg[:limit]


def unique(seq: Iterable[str]) -> list[str]:
    out: list[str] = []
    for s in seq:
        if s and s not in out:
            out.append(s)
    return out
