"""Provider adapters. Each one is isolated in its own file so it can be swapped or fixed alone."""
from __future__ import annotations

from . import anthropic_p, gemini_p, openai_p

REGISTRY = {m.NAME: m for m in (anthropic_p, openai_p, gemini_p)}
ALL = list(REGISTRY)


def get(name: str):
    try:
        return REGISTRY[name.strip().lower()]
    except KeyError:
        raise SystemExit(f"Unknown provider '{name}'. Use one of: {', '.join(ALL)}")
