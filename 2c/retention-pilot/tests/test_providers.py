"""Provider tests with fake clients. No network, no keys, no real API calls."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from providers import get_provider  # noqa: E402
from providers.anthropic_p import DEFAULT_MODEL, FALLBACK_BETA, AnthropicProvider  # noqa: E402
from providers.gemini_p import GeminiProvider  # noqa: E402
from providers.mock_p import MockProvider  # noqa: E402
from providers.openai_p import OpenAIProvider  # noqa: E402

try:
    import anthropic  # noqa: F401
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False


def response(stop="end_turn", text="DRAFT - PENDING OWNER REVIEW\nSubject: Hi\n\nHello,", category=None):
    content = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
    details = SimpleNamespace(category=category, explanation="") if stop == "refusal" else None
    return SimpleNamespace(stop_reason=stop, content=content if stop != "refusal" else [],
                           stop_details=details, model=DEFAULT_MODEL)


class FakeCreate:
    def __init__(self, resp=None, exc=None):
        self.calls = []
        self.resp, self.exc = resp or response(), exc

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.resp


class TypedCreate(FakeCreate):
    """Mimics an SDK version whose create() has a named fallbacks argument."""

    def __call__(self, *, model, max_tokens, messages, system=None, output_config=None, betas=None, fallbacks=None):
        return super().__call__(model=model, max_tokens=max_tokens, messages=messages, system=system,
                                output_config=output_config, betas=betas, fallbacks=fallbacks)


def fake_client(create=None, beta_create=None):
    return SimpleNamespace(messages=SimpleNamespace(create=create or FakeCreate()),
                           beta=SimpleNamespace(messages=SimpleNamespace(create=beta_create or FakeCreate())))


CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "PROVIDER", "MOCK_"))}


@mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
class AnthropicProviderTests(unittest.TestCase):
    def test_defaults_and_fallback_via_extra_body(self):
        client = fake_client()
        p = AnthropicProvider(client=client)
        res = p.draft("system", "user")
        self.assertTrue(res.ok)
        self.assertEqual(res.text, "DRAFT - PENDING OWNER REVIEW\nSubject: Hi\n\nHello,")
        call = client.beta.messages.create.calls[0]
        self.assertEqual(call["model"], DEFAULT_MODEL)
        self.assertEqual(call["betas"], [FALLBACK_BETA])
        self.assertEqual(call["extra_body"], {"fallbacks": "default"})
        self.assertEqual(call["output_config"], {"effort": "medium"})
        self.assertNotIn("thinking", call)
        self.assertEqual(call["messages"], [{"role": "user", "content": "user"}])
        self.assertEqual(client.messages.create.calls, [])

    def test_typed_fallbacks_argument_used_when_sdk_has_it(self):
        typed = TypedCreate()
        p = AnthropicProvider(client=fake_client(beta_create=typed))
        self.assertTrue(p.draft("s", "u").ok)
        self.assertEqual(typed.calls[0]["fallbacks"], "default")
        self.assertNotIn("extra_body", typed.calls[0])

    def test_fallbacks_off_and_effort_blank(self):
        client = fake_client()
        p = AnthropicProvider(client=client, fallbacks="off", effort="")
        self.assertTrue(p.draft("s", "u").ok)
        call = client.messages.create.calls[0]
        self.assertNotIn("betas", call)
        self.assertNotIn("output_config", call)

    def test_model_from_env(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_MODEL": "some-other-model"}):
            self.assertEqual(AnthropicProvider(client=fake_client()).model, "some-other-model")

    def test_refusal(self):
        client = fake_client(beta_create=FakeCreate(response(stop="refusal", category="cyber")))
        res = AnthropicProvider(client=client).draft("s", "u")
        self.assertEqual(res.status, "REFUSED")
        self.assertIn("cyber", res.detail)
        self.assertFalse(res.ok)

    def test_max_tokens(self):
        client = fake_client(beta_create=FakeCreate(response(stop="max_tokens", text="partial")))
        res = AnthropicProvider(client=client).draft("s", "u")
        self.assertEqual(res.status, "TRUNCATED")
        self.assertFalse(res.ok)

    def test_empty_text(self):
        client = fake_client(beta_create=FakeCreate(response(text="   ")))
        self.assertEqual(AnthropicProvider(client=client).draft("s", "u").status, "EMPTY")

    @unittest.skipUnless(HAVE_SDK, "anthropic SDK not installed")
    def test_connection_error_is_reported_not_raised(self):
        import anthropic
        exc = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
        client = fake_client(beta_create=FakeCreate(exc=exc))
        res = AnthropicProvider(client=client).draft("s", "u")
        self.assertEqual(res.status, "ERROR")
        self.assertIn("network", res.detail)


class OtherProviders(unittest.TestCase):
    def test_openai_shape(self):
        create = FakeCreate(SimpleNamespace(output_text="DRAFT - PENDING OWNER REVIEW\nHi", status="completed"))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        res = OpenAIProvider(client=client, model="m").draft("sys", "usr")
        self.assertTrue(res.ok)
        self.assertEqual(create.calls[0], {"model": "m", "instructions": "sys", "input": "usr"})

    def test_gemini_shape(self):
        create = FakeCreate(SimpleNamespace(text="DRAFT - PENDING OWNER REVIEW\nHi"))
        client = SimpleNamespace(models=SimpleNamespace(generate_content=create))
        res = GeminiProvider(client=client, model="g").draft("sys", "usr")
        self.assertTrue(res.ok)
        self.assertEqual(create.calls[0]["contents"], "usr")

    def test_mock_behaviors(self):
        user = "x\n<template>\nDRAFT - PENDING OWNER REVIEW\nHello,\n</template>\n"
        self.assertTrue(MockProvider("ok").draft("s", user).ok)
        for b, status in (("refuse", "REFUSED"), ("truncate", "TRUNCATED"), ("error", "ERROR")):
            self.assertEqual(MockProvider(b).draft("s", user).status, status)

    def test_get_provider(self):
        self.assertIsInstance(get_provider("mock"), MockProvider)
        with self.assertRaises(ValueError):
            get_provider("nope")


if __name__ == "__main__":
    unittest.main()
