"""Model providers for drafting only. Pick one with the PROVIDER environment variable.

  PROVIDER=mock       no network, no key (default for tests and teaching)
  PROVIDER=anthropic  Claude through the official anthropic SDK (pip install anthropic)
  PROVIDER=openai     OpenAI Responses API (pip install openai). Not tested against a live API here.
  PROVIDER=gemini     Google Gen AI SDK (pip install google-genai). Not tested against a live API here.

Model names are set by environment variables with defaults in each provider file.
Model names change: check the provider's current model list before a real run.
"""
from __future__ import annotations

import os

from providers.base import DraftResult  # noqa: F401  (re-exported)


def get_provider(name: str | None = None):
    name = (name or os.environ.get("PROVIDER") or "mock").strip().lower()
    if name == "mock":
        from providers.mock_p import MockProvider
        return MockProvider()
    if name == "anthropic":
        from providers.anthropic_p import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from providers.openai_p import OpenAIProvider
        return OpenAIProvider()
    if name == "gemini":
        from providers.gemini_p import GeminiProvider
        return GeminiProvider()
    raise ValueError("Unknown PROVIDER %r. Use mock, anthropic, openai or gemini." % name)
