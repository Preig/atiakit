"""Gemini through the google-genai SDK with Grounding with Google Search.

Two request styles, chosen with GEMINI_API_STYLE:
  "interactions"     client.interactions.create(model, input, tools=[{"type": "google_search"}])
                     Steps: google_search_call (arguments.queries), google_search_result,
                     model_output (content[].text with url_citation annotations).
                     This is the style the current Gemini docs show.
  "generate_content" client.models.generate_content(..., config={"tools": [{"google_search": {}}]})
                     with candidates[0].grounding_metadata (web_search_queries,
                     grounding_chunks[].web.uri/title). Kept as a fallback; confirm it
                     against your installed SDK before relying on it.

Model id, style and prices come from the environment (see .env.example).
Check current names in the Gemini docs, then run `python monitor.py check`.

Citation URLs may be Google redirect links (vertexaisearch.cloud.google.com). The
monitor resolves them with one HEAD request (no page download). If that fails it
falls back to the citation title, which is usually the source domain.
Billing (Gemini 3 and newer): per search query, with a monthly free allowance.
Empty queries are not counted.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request

from .common import (Answer, as_int, describe_location, env_bool, env_str, get_any,
                     panel_instruction, short_error, to_dict, unique)

NAME = "gemini"
KEY_ENV = "GEMINI_API_KEY"
REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)


def config() -> dict:
    return {
        # Configurable default. Check the current model id in the Gemini models list.
        "model": env_str("GEMINI_MODEL", "gemini-3.8-flash"),
        "api_style": env_str("GEMINI_API_STYLE", "interactions").lower(),
        "tool_type": env_str("GEMINI_SEARCH_TOOL", "google_search"),
        "resolve_redirects": env_bool("GEMINI_RESOLVE_REDIRECTS", True),
        # The Gemini search tool takes no user location here; recorded as "not sent".
        "user_location": {},
    }


def available() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip())


def make_client():
    from google import genai  # imported only for live calls

    return genai.Client()


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_redirect(url: str) -> bool:
    return _host(url) in REDIRECT_HOSTS


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None  # stop: we only want the Location header


def resolve_redirect(url: str, timeout: float = 5.0) -> str:
    """Return the target of a Google grounding redirect, or "" if it cannot be read."""
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ai-answer-monitor"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.headers.get("Location") or ""
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location") if e.code in (301, 302, 303, 307, 308) else ""
        e.close()
        return location or ""
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def parse_interaction(d: dict, ans: Answer) -> Answer:
    texts: list[str] = []
    queries: list[str] = []
    for step in get_any(d, "steps", "outputs", default=[]) or []:
        if not isinstance(step, dict):
            continue
        stype = step.get("type")
        if stype == "google_search_call":
            qs = (step.get("arguments") or {}).get("queries") or []
            qs = [str(q) for q in qs if q and str(q).strip()]
            queries.extend(qs)
            ans.search_calls += len(qs)          # billed per non-empty query
        elif stype == "model_output":
            for part in step.get("content") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("text") and part.get("type") in (None, "text"):
                    texts.append(part["text"])
                for a in part.get("annotations") or []:
                    if isinstance(a, dict) and a.get("type") == "url_citation":
                        ans.add_citation(a.get("url") or "", a.get("title") or "")
    if not texts and d.get("output_text"):
        texts = [d["output_text"]]
    ans.text = "".join(texts)
    ans.search_queries = unique(queries)
    ans.stop_reason = str(d.get("status") or "")
    usage = get_any(d, "usage", "usage_metadata", "usageMetadata", default={}) or {}
    _read_usage(usage, ans)
    return ans


def parse_generate_content(d: dict, ans: Answer) -> Answer:
    cands = d.get("candidates") or []
    c0 = cands[0] if cands and isinstance(cands[0], dict) else {}
    parts = (c0.get("content") or {}).get("parts") or []
    ans.text = "".join(p.get("text") or "" for p in parts if isinstance(p, dict) and not p.get("thought"))
    gm = get_any(c0, "grounding_metadata", "groundingMetadata", default={}) or {}
    qs = [str(q) for q in (get_any(gm, "web_search_queries", "webSearchQueries", default=[]) or []) if q and str(q).strip()]
    ans.search_queries = unique(qs)
    ans.search_calls = len(qs)
    for ch in get_any(gm, "grounding_chunks", "groundingChunks", default=[]) or []:
        web = (ch or {}).get("web") or {}
        ans.add_citation(web.get("uri") or "", web.get("title") or "")
    ans.stop_reason = str(get_any(c0, "finish_reason", "finishReason", default="") or "")
    if ans.stop_reason.upper() in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
        ans.error = "refusal:" + ans.stop_reason.lower()
    usage = get_any(d, "usage_metadata", "usageMetadata", default={}) or {}
    _read_usage(usage, ans)
    return ans


def _read_usage(usage: dict, ans: Answer) -> None:
    ans.usage_reported = bool(usage)

    def first(*keys):
        return as_int(get_any(usage, *keys, default=0))

    ans.input_tokens = (first("total_input_tokens", "input_tokens", "prompt_token_count", "promptTokenCount")
                        + first("total_tool_use_tokens", "tool_use_prompt_token_count", "toolUsePromptTokenCount"))
    ans.output_tokens = (first("total_output_tokens", "output_tokens", "candidates_token_count", "candidatesTokenCount")
                         + first("total_thought_tokens", "thoughts_token_count", "thoughtsTokenCount"))


def parse_raw(raw, ans: Answer) -> Answer:
    d = to_dict(raw) or {}
    ans.model = d.get("model") or d.get("model_version") or ans.model
    style = d.get("_style") or ("generate_content" if "candidates" in d else "interactions")
    if style == "generate_content":
        return parse_generate_content(d, ans)
    return parse_interaction(d, ans)


def resolve_citations(ans: Answer, resolver=resolve_redirect) -> None:
    for c in ans.citations:
        if is_redirect(c["url"]) and not c.get("resolved_url"):
            c["resolved_url"] = resolver(c["url"]) or ""


def _blank_answer(cfg: dict) -> Answer:
    return Answer(provider=NAME, model=cfg["model"], tool_version=cfg["tool_type"],
                  user_location=describe_location(cfg.get("user_location") or {}) + " (not sent)")


def classify_error(exc: BaseException) -> str:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 404:
        return "not_found (check GEMINI_MODEL): " + short_error(exc)
    if code in (401, 403):
        return "authentication_or_permission (check GEMINI_API_KEY): " + short_error(exc)
    if code == 400:
        return "bad_request (check GEMINI_MODEL, GEMINI_API_STYLE, GEMINI_SEARCH_TOOL): " + short_error(exc)
    if code == 429:
        return "rate_limited"
    if isinstance(exc, (AttributeError, TypeError)):
        return ("sdk_mismatch (this google-genai version may not have the selected API style; "
                "try GEMINI_API_STYLE=generate_content or upgrade google-genai): " + short_error(exc))
    return f"{type(exc).__name__}: {short_error(exc)}"


def _call(client, cfg: dict, prompt: str):
    if cfg["api_style"] == "generate_content":
        resp = client.models.generate_content(
            model=cfg["model"], contents=prompt,
            config={"tools": [{cfg["tool_type"]: {}}], "system_instruction": panel_instruction()})
        d = to_dict(resp) or {}
        d["_style"] = "generate_content"
        return d
    resp = client.interactions.create(model=cfg["model"], input=prompt,
                                      tools=[{"type": cfg["tool_type"]}],
                                      system_instruction=panel_instruction())
    d = to_dict(resp) or {}
    d["_style"] = "interactions"
    return d


def ask(prompt: str, cfg: dict | None = None, client=None, resolver=resolve_redirect) -> Answer:
    cfg = cfg or config()
    ans = _blank_answer(cfg)
    try:
        client = client or make_client()
        d = _call(client, cfg, prompt)
    except Exception as exc:
        ans.error = classify_error(exc)
        return ans
    parse_raw(d, ans)
    if not ans.usage_reported:
        ans.notes.append("usage_not_reported: token cost not counted")
    if cfg.get("resolve_redirects"):
        resolve_citations(ans, resolver)
    return ans


def parse_fixture(raw) -> Answer:
    # Mock mode never resolves redirects: no network.
    return parse_raw(raw, _blank_answer(config()))


def check(cfg: dict | None = None, client=None) -> tuple[bool, str]:
    cfg = cfg or config()
    try:
        client = client or make_client()
        d = _call(client, cfg, "Reply with the single word OK. Do not search.")
    except Exception as exc:
        return False, classify_error(exc)
    ans = parse_raw(d, _blank_answer(cfg))
    msg = f"model {ans.model} answered with tool {cfg['tool_type']} ({cfg['api_style']} style)"
    if not ans.usage_reported:
        msg += ". Warning: no token usage found in the response; costs will count searches only"
    return True, msg

