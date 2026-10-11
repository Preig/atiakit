"""OpenAI through the Responses API with the web_search tool.

Model id, tool type and prices come from the environment (see .env.example).
Check the current names in the OpenAI web search guide and model list after any change,
then run `python monitor.py check`.

Shape handled (Responses API):
  output[] items of type "web_search_call" (action.type "search", "open_page" or
  "find_in_page"; action.sources when include=["web_search_call.action.sources"])
  and type "message" whose content[] has "output_text" parts with "url_citation"
  annotations (url, title, start_index, end_index).
Searches billed = web_search_call items whose action is a search.
"""
from __future__ import annotations

import os

from .common import (Answer, as_int, describe_location, env_bool, env_int, env_str,
                     panel_instruction, short_error, to_dict, unique,
                     user_location_from_env)

NAME = "openai"
KEY_ENV = "OPENAI_API_KEY"


def config() -> dict:
    return {
        # Configurable default. Check the current model id in the OpenAI docs.
        "model": env_str("OPENAI_MODEL", "gpt-5.5"),
        # Configurable default. "web_search_preview" is the older name.
        "tool_type": env_str("OPENAI_WEB_SEARCH_TOOL", "web_search"),
        "search_context_size": env_str("OPENAI_SEARCH_CONTEXT_SIZE", ""),
        "include_sources": env_bool("OPENAI_INCLUDE_SOURCES", True),
        "max_output_tokens": env_int("OPENAI_MAX_OUTPUT_TOKENS", 16000),
        "user_location": user_location_from_env(),
    }


def available() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())


def make_client():
    from openai import OpenAI  # imported only for live calls

    return OpenAI(max_retries=4)


def build_request(cfg: dict, prompt: str) -> dict:
    tool: dict = {"type": cfg["tool_type"]}
    if cfg.get("user_location"):
        tool["user_location"] = cfg["user_location"]
    if cfg.get("search_context_size"):
        tool["search_context_size"] = cfg["search_context_size"]
    req = {"model": cfg["model"], "instructions": panel_instruction(), "input": prompt,
           "tools": [tool], "max_output_tokens": cfg["max_output_tokens"]}
    if cfg.get("include_sources"):
        req["include"] = ["web_search_call.action.sources"]
    return req


def parse_response(raw, ans: Answer) -> Answer:
    d = to_dict(raw) or {}
    ans.model = d.get("model") or ans.model
    status = d.get("status") or ""
    ans.stop_reason = status
    texts: list[str] = []
    queries: list[str] = []
    for item in d.get("output") or []:
        if not isinstance(item, dict):
            continue
        itype = item.get("type")
        if itype == "web_search_call":
            action = item.get("action") or {}
            atype = action.get("type") or "search"
            if atype == "search":
                ans.search_calls += 1
                if action.get("query"):
                    queries.append(str(action["query"]))
                queries.extend(str(q) for q in (action.get("queries") or []) if q)
            for s in action.get("sources") or []:
                if isinstance(s, dict):
                    ans.add_source(s.get("url") or "")
        elif itype == "message":
            for part in item.get("content") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                    for a in part.get("annotations") or []:
                        if isinstance(a, dict) and a.get("type") == "url_citation":
                            ans.add_citation(a.get("url") or "", a.get("title") or "")
                elif part.get("type") == "refusal":
                    ans.error = "refusal: " + short_error(Exception(part.get("refusal") or ""), 200)
    if not texts and d.get("output_text"):
        texts = [d["output_text"]]
    ans.text = "\n\n".join(t for t in texts if t)
    ans.search_queries = unique(queries)
    usage = d.get("usage") or {}
    ans.usage_reported = bool(usage)
    # output_tokens already includes reasoning tokens on the Responses API.
    ans.input_tokens = as_int(usage.get("input_tokens"))
    ans.output_tokens = as_int(usage.get("output_tokens"))
    if status == "incomplete":
        reason = (d.get("incomplete_details") or {}).get("reason") or "unknown"
        ans.notes.append("incomplete:" + str(reason))
    if d.get("error"):
        err = d["error"]
        ans.error = "api_error: " + (err.get("message", "") if isinstance(err, dict) else str(err))[:300]
    return ans


def _blank_answer(cfg: dict) -> Answer:
    return Answer(provider=NAME, model=cfg["model"], tool_version=cfg["tool_type"],
                  user_location=describe_location(cfg.get("user_location") or {}))


def classify_error(exc: BaseException) -> str:
    try:
        import openai
    except ImportError:
        return f"{type(exc).__name__}: {short_error(exc)}"
    if isinstance(exc, openai.NotFoundError):
        return "not_found (check OPENAI_MODEL): " + short_error(exc)
    if isinstance(exc, openai.AuthenticationError):
        return "authentication_failed (check OPENAI_API_KEY)"
    if isinstance(exc, openai.PermissionDeniedError):
        return "permission_denied: " + short_error(exc)
    if isinstance(exc, openai.BadRequestError):
        return "bad_request (check OPENAI_MODEL and OPENAI_WEB_SEARCH_TOOL): " + short_error(exc)
    if isinstance(exc, openai.RateLimitError):
        return "rate_limited_after_retries"
    if isinstance(exc, openai.APIStatusError):
        return f"api_error_{exc.status_code}: " + short_error(exc)
    if isinstance(exc, openai.APIConnectionError):
        return "connection_error: " + short_error(exc)
    return f"{type(exc).__name__}: {short_error(exc)}"


def ask(prompt: str, cfg: dict | None = None, client=None) -> Answer:
    cfg = cfg or config()
    ans = _blank_answer(cfg)
    try:
        client = client or make_client()
        resp = client.responses.create(**build_request(cfg, prompt))
    except Exception as exc:
        ans.error = classify_error(exc)
        return ans
    return parse_response(resp, ans)


def parse_fixture(raw) -> Answer:
    return parse_response(raw, _blank_answer(config()))


def check(cfg: dict | None = None, client=None) -> tuple[bool, str]:
    cfg = dict(cfg or config(), max_output_tokens=2048)
    try:
        client = client or make_client()
        resp = client.responses.create(**build_request(cfg, "Reply with the single word OK. Do not search."))
    except Exception as exc:
        return False, classify_error(exc)
    d = to_dict(resp) or {}
    return True, f"model {d.get('model')} answered with tool {cfg['tool_type']} (status {d.get('status')})"
