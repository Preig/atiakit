"""Provider adapters: request shape, response parsing, pause_turn, refusals, errors.

Every test is offline. Fake clients stand in for the SDKs; where the real anthropic or
openai SDK is installed, an in-memory HTTP transport checks the exact request body the
SDK would send and that the SDK's own response objects parse. No keys, no network.
"""
import importlib.util
import json
import threading
import unittest
import unittest.mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

from tests._util import HERE, clean_env, no_network
from providers import anthropic_p, gemini_p, openai_p
from matching import Watched, find_mentions


def fixture(week, provider, pid):
    data = json.loads((HERE / "fixtures" / week / f"{provider}.json").read_text(encoding="utf-8"))
    return data["responses"][pid]


class FakeResp:
    def __init__(self, d):
        self._d = d
        self.content = d.get("content")

    def model_dump(self, mode=None):
        return self._d


class FakeMessages:
    def __init__(self, responses=None, exc=None):
        self.calls, self.responses, self.exc = [], list(responses or []), exc

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        return FakeResp(self.responses.pop(0))


class FakeAnthropic:
    def __init__(self, responses=None, exc=None):
        self.messages = FakeMessages(responses, exc)
        self.beta = SimpleNamespace(messages=self.messages)


def msg(stop_reason, content, usage=None, **extra):
    d = {"type": "message", "role": "assistant", "model": "mock-claude", "stop_reason": stop_reason,
         "content": content, "usage": usage or {"input_tokens": 10, "output_tokens": 5,
                                                 "server_tool_use": {"web_search_requests": 1}}}
    d.update(extra)
    return d


class AnthropicAdapter(unittest.TestCase):
    def test_pause_turn_is_resumed_without_extra_user_message(self):
        first, second = fixture("week1", "anthropic", "P01")
        client = FakeAnthropic([first, second])
        with clean_env(), no_network():
            ans = anthropic_p.ask("Fairbanks question", client=client)
        calls = client.messages.calls
        self.assertEqual(len(calls), 2)
        resent = calls[1]["messages"]
        self.assertEqual([m["role"] for m in resent], ["user", "assistant"])
        self.assertEqual(resent[0]["content"], "Fairbanks question")
        self.assertEqual(resent[1]["content"], first["content"])
        self.assertEqual(ans.error, "")
        self.assertEqual(ans.input_tokens, 9100 + 12400)
        self.assertEqual(ans.output_tokens, 310 + 880)
        self.assertEqual(ans.search_calls, 2)
        self.assertIn("aurora", ans.text)
        self.assertEqual(len(ans.citations), 2)
        self.assertEqual(len(ans.search_queries), 2)

    def test_stops_after_max_continuations(self):
        paused = msg("pause_turn", [{"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "q"}}])
        client = FakeAnthropic([paused] * 3)
        with clean_env(ANTHROPIC_MAX_CONTINUATIONS="2"), no_network():
            ans = anthropic_p.ask("q", client=client)
        self.assertEqual(len(client.messages.calls), 3)
        self.assertIn("still_paused_after_max_continuations", ans.notes)

    def test_request_shape_with_fallbacks_default(self):
        client = FakeAnthropic([msg("end_turn", [{"type": "text", "text": "OK"}])])
        with clean_env(USER_CITY="Seattle", USER_REGION="Washington"), no_network():
            anthropic_p.ask("q", client=client)
        kw = client.messages.calls[0]
        self.assertEqual(kw["betas"], [anthropic_p.FALLBACK_BETA])
        self.assertEqual(kw["extra_body"]["fallbacks"], "default")
        self.assertEqual(kw["extra_body"]["output_config"], {"effort": "medium"})
        tool = kw["tools"][0]
        self.assertEqual(tool["name"], "web_search")
        self.assertEqual(tool["type"], "web_search_20260318")
        self.assertEqual(tool["max_uses"], 5)
        self.assertEqual(tool["user_location"], {"type": "approximate", "city": "Seattle",
                                                 "region": "Washington", "country": "US"})
        self.assertNotIn("thinking", kw)

    def test_env_overrides_and_fallbacks_off(self):
        client = FakeAnthropic([msg("end_turn", [{"type": "text", "text": "OK"}])])
        with clean_env(ANTHROPIC_FALLBACKS="off", ANTHROPIC_EFFORT="", ANTHROPIC_MODEL="model-from-env",
                       ANTHROPIC_WEB_SEARCH_TOOL="web_search_20250305", USER_LOCATION="off"), no_network():
            anthropic_p.ask("q", client=client)
        kw = client.messages.calls[0]
        self.assertNotIn("betas", kw)
        self.assertNotIn("extra_body", kw)
        self.assertEqual(kw["model"], "model-from-env")
        self.assertEqual(kw["tools"][0]["type"], "web_search_20250305")
        self.assertNotIn("user_location", kw["tools"][0])

    def test_refusal_discards_partial_text(self):
        r = msg("refusal", [{"type": "text", "text": "partial"}], stop_details={"type": "refusal", "category": None})
        with clean_env(), no_network():
            ans = anthropic_p.ask("q", client=FakeAnthropic([r]))
        self.assertEqual(ans.error, "refusal:unspecified")
        self.assertEqual(ans.text, "")

    def test_search_error_object_is_a_note_not_an_exception(self):
        raw = fixture("week1", "anthropic", "P05")
        with clean_env():
            ans = anthropic_p.parse_fixture(raw)
        self.assertEqual(ans.error, "")
        self.assertIn("web_search_error:max_uses_exceeded", ans.notes)
        self.assertTrue(ans.text)

    def test_api_exception_is_recorded(self):
        with clean_env(), no_network():
            ans = anthropic_p.ask("q", client=FakeAnthropic(exc=RuntimeError("boom")))
        self.assertIn("boom", ans.error)

    def test_fallback_block_noted(self):
        r = msg("end_turn", [{"type": "fallback"}, {"type": "text", "text": "Hi"}])
        with clean_env():
            ans = anthropic_p.parse_fixture(r)
        self.assertIn("served_by_fallback_model", ans.notes)

    def test_fallback_seen_in_usage_iterations_and_attempts_summed(self):
        # Sticky-routed turns carry no fallback block; usage.iterations is the served-by signal
        # and lists every attempt, while top-level usage covers only the final one.
        usage = {"input_tokens": 100, "output_tokens": 40, "server_tool_use": {"web_search_requests": 1},
                 "iterations": [{"type": "message", "input_tokens": 90, "output_tokens": 0},
                                {"type": "fallback_message", "input_tokens": 100, "output_tokens": 40}]}
        r = msg("end_turn", [{"type": "text", "text": "Hi"}], usage=usage)
        with clean_env():
            ans = anthropic_p.parse_fixture(r)
        self.assertEqual(ans.notes.count("served_by_fallback_model"), 1)
        self.assertEqual(ans.input_tokens, 190)
        self.assertEqual(ans.output_tokens, 40)
        # Without iterations the top-level usage is used unchanged.
        with clean_env():
            plain = anthropic_p.parse_fixture(msg("end_turn", [{"type": "text", "text": "Hi"}]))
        self.assertEqual((plain.input_tokens, plain.output_tokens), (10, 5))
        self.assertNotIn("served_by_fallback_model", plain.notes)

    def test_check_tries_fallback_tool_types(self):
        class BadRequest(Exception):
            status_code = 400
        calls = []

        class Msgs:
            def create(self, **kw):
                calls.append(kw["tools"][0]["type"])
                if kw["tools"][0]["type"] != "web_search_20250305":
                    raise BadRequest("unknown tool type")
                return FakeResp(msg("end_turn", [{"type": "text", "text": "OK"}]))
        client = SimpleNamespace(messages=Msgs(), beta=SimpleNamespace(messages=Msgs()))
        with clean_env(), no_network(), unittest.mock.patch.object(anthropic_p, "_is_bad_request",
                                                                    lambda e: isinstance(e, BadRequest)):
            ok, message = anthropic_p.check(client=client)
        self.assertFalse(ok)
        self.assertIn("ANTHROPIC_WEB_SEARCH_TOOL=web_search_20250305", message)
        self.assertEqual(calls, ["web_search_20260318", "web_search_20260209", "web_search_20250305"])


def _httpx():
    if importlib.util.find_spec("httpx2"):
        import httpx2 as httpx
    else:
        import httpx
    return httpx


@unittest.skipUnless(importlib.util.find_spec("anthropic") and
                     (importlib.util.find_spec("httpx") or importlib.util.find_spec("httpx2")),
                     "anthropic SDK not installed")
class AnthropicRealSdkOffline(unittest.TestCase):
    """The installed SDK builds the request; an in-memory transport answers it."""

    def test_sdk_request_body_and_response_objects(self):
        import anthropic
        httpx = _httpx()
        seen = []
        first, second = fixture("week1", "anthropic", "P01")
        queue = [first, second]

        def handler(request):
            seen.append((dict(request.headers), json.loads(request.content)))
            body = dict(queue.pop(0), id="msg_test")
            return httpx.Response(200, json=body)

        http_client = getattr(anthropic, "DefaultHttpxClient", httpx.Client)(transport=httpx.MockTransport(handler))
        client = anthropic.Anthropic(api_key="test-key-not-real", http_client=http_client, max_retries=0)
        with clean_env():
            ans = anthropic_p.ask("Fairbanks question", client=client)
        self.assertEqual(ans.error, "")
        self.assertEqual(len(seen), 2)
        headers, body = seen[0]
        self.assertIn(anthropic_p.FALLBACK_BETA, headers.get("anthropic-beta", ""))
        self.assertEqual(body["fallbacks"], "default")
        self.assertEqual(body["output_config"], {"effort": "medium"})
        self.assertEqual(body["tools"][0]["type"], "web_search_20260318")
        # The paused assistant turn is sent back as-is, as SDK objects serialized by the SDK
        resent = seen[1][1]["messages"]
        self.assertEqual(resent[1]["role"], "assistant")
        self.assertEqual(resent[1]["content"][0]["type"], "server_tool_use")
        self.assertEqual(ans.search_calls, 2)
        self.assertEqual(len(ans.citations), 2)


class OpenAIAdapter(unittest.TestCase):
    def test_parse_fixture(self):
        with clean_env():
            ans = openai_p.parse_fixture(fixture("week1", "openai", "P02"))
        self.assertEqual(ans.search_calls, 1)
        self.assertEqual(ans.input_tokens, 9800)
        self.assertEqual(len(ans.citations), 2)
        self.assertIn("https://reviews.example/seward", ans.sources)
        self.assertIn("Bay Light Day Cruises", ans.text)

    def test_request_shape(self):
        with clean_env():
            req = openai_p.build_request(openai_p.config(), "q")
        self.assertEqual(req["tools"][0]["type"], "web_search")
        self.assertEqual(req["tools"][0]["user_location"]["country"], "US")
        self.assertEqual(req["include"], ["web_search_call.action.sources"])
        self.assertEqual(req["input"], "q")
        self.assertTrue(req["instructions"])

    def test_open_page_actions_are_not_billed_searches(self):
        raw = {"model": "m", "status": "completed", "output": [
            {"type": "web_search_call", "action": {"type": "search", "query": "a"}},
            {"type": "web_search_call", "action": {"type": "open_page", "url": "https://x.example"}},
            {"type": "message", "content": [{"type": "output_text", "text": "t", "annotations": []}]}],
            "usage": {"input_tokens": 1, "output_tokens": 2}}
        with clean_env():
            ans = openai_p.parse_fixture(raw)
        self.assertEqual(ans.search_calls, 1)

    def test_incomplete_and_refusal(self):
        raw = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
               "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]}
        with clean_env():
            ans = openai_p.parse_fixture(raw)
        self.assertIn("incomplete:max_output_tokens", ans.notes)
        self.assertTrue(ans.error.startswith("refusal"))
        self.assertFalse(ans.usage_reported)


@unittest.skipUnless(importlib.util.find_spec("openai") and
                     (importlib.util.find_spec("httpx") or importlib.util.find_spec("httpx2")),
                     "openai SDK not installed")
class OpenAIRealSdkOffline(unittest.TestCase):
    def test_sdk_request_body_and_response_objects(self):
        import openai
        httpx = _httpx()
        seen = []

        def handler(request):
            seen.append(json.loads(request.content))
            body = dict(fixture("week1", "openai", "P06"), created_at=0, object="response")
            return httpx.Response(200, json=body)

        client = openai.OpenAI(api_key="test-key-not-real", max_retries=0,
                               http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        with clean_env():
            ans = openai_p.ask("kayak question", client=client)
        self.assertEqual(ans.error, "")
        body = seen[0]
        self.assertEqual(body["tools"][0]["type"], "web_search")
        self.assertEqual(body["include"], ["web_search_call.action.sources"])
        self.assertIn("Harbor Kayak", ans.text)
        self.assertEqual(len(ans.citations), 1)


class FakeGemini:
    def __init__(self, interaction=None, generated=None):
        self.calls = []
        self.interactions = SimpleNamespace(create=self._ic)
        self.models = SimpleNamespace(generate_content=self._gc)
        self._i, self._g = interaction, generated

    def _ic(self, **kw):
        self.calls.append(("interactions", kw))
        return self._i

    def _gc(self, **kw):
        self.calls.append(("generate_content", kw))
        return self._g


class GeminiAdapter(unittest.TestCase):
    def test_interactions_parse_counts_non_empty_queries(self):
        with clean_env():
            ans = gemini_p.parse_fixture(fixture("week1", "gemini", "_default"))
        self.assertEqual(ans.search_calls, 1)          # one empty query is not billed
        self.assertEqual(ans.input_tokens, 4100)
        self.assertEqual(ans.citations[0]["title"], "visitseward.example")

    def test_generate_content_parse(self):
        with clean_env():
            ans = gemini_p.parse_fixture(fixture("week1", "gemini", "P07"))
        self.assertIn("Mile 12 Kennel", ans.text)
        self.assertEqual(ans.search_calls, 1)
        self.assertEqual(ans.citations[0]["title"], "mile12kennel.example")
        self.assertEqual(ans.output_tokens, 520)

    def test_live_path_resolves_redirects_with_injected_resolver(self):
        raw = dict(fixture("week1", "gemini", "P02"))
        client = FakeGemini(interaction=raw)
        with clean_env(), no_network():
            ans = gemini_p.ask("q", client=client, resolver=lambda url: "https://ota.example/listing")
        self.assertEqual(client.calls[0][0], "interactions")
        self.assertEqual(client.calls[0][1]["tools"], [{"type": "google_search"}])
        self.assertTrue(all(c["resolved_url"] == "https://ota.example/listing" for c in ans.citations))
        w = Watched("Bay Light Day Cruises", [], ["baylight.example"])
        self.assertFalse(find_mentions(ans.text, [w], ans.citations)[w.name].cited)  # resolved URL wins

    def test_generate_content_style_request(self):
        raw = dict(fixture("week1", "gemini", "P07"))
        client = FakeGemini(generated=raw)
        with clean_env(GEMINI_API_STYLE="generate_content", GEMINI_RESOLVE_REDIRECTS="0"), no_network():
            ans = gemini_p.ask("q", client=client)
        name, kw = client.calls[0]
        self.assertEqual(name, "generate_content")
        self.assertEqual(kw["config"]["tools"], [{"google_search": {}}])
        self.assertEqual(ans.citations[0]["resolved_url"], "")

    def test_missing_sdk_method_is_explained(self):
        client = SimpleNamespace()  # no .interactions
        with clean_env(), no_network():
            ans = gemini_p.ask("q", client=client)
        self.assertIn("sdk_mismatch", ans.error)


class RedirectResolver(unittest.TestCase):
    """resolve_redirect sends one HEAD request and reads Location. Tested against a local server."""

    def setUp(self):
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", "https://baylight.example/cruise")
                else:
                    self.send_response(404)
                self.end_headers()

            def log_message(self, *a):
                pass
        self.srv = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.srv.server_address[1]
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_reads_location_without_following(self):
        url = f"http://127.0.0.1:{self.port}/redirect/abc"
        self.assertEqual(gemini_p.resolve_redirect(url, timeout=3), "https://baylight.example/cruise")

    def test_failure_returns_empty(self):
        self.assertEqual(gemini_p.resolve_redirect(f"http://127.0.0.1:{self.port}/missing", timeout=3), "")


if __name__ == "__main__":
    unittest.main()
