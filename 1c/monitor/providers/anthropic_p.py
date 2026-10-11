"""Claude through the Anthropic Messages API with the server-side web search tool.

Model id, tool type and prices come from the environment (see .env.example).
Names change over time: after any change run `python monitor.py check`, and compare
with the current Anthropic docs (models overview and the web search tool page).

What this adapter handles:
  * stop_reason "pause_turn": the server-side search loop paused. We resend the
    user turn plus the assistant turn so far, and the API resumes it.
  * stop_reason "refusal": recorded as an error, partial text discarded.
  * search errors arrive as a web_search_tool_result whose content is an error
    object (HTTP 200), not as a raised exception. They are kept as notes.
  * citations are web_search_result_location entries on text blocks.
  * searches billed = usage.server_tool_use.web_search_requests.
  * server-side refusal fallback: usage.iterations lists every attempt (a
    "fallback_message" entry means a fallback model served the answer); tokens are
    summed over the iterations so a declined attempt is not left out of the cost.
"""
from __future__ import annotations

import os

from .common import (Answer, as_int, describe_location, env_int, env_str,
                     panel_instruction, short_error, to_dict, unique,
                     user_location_from_env)

NAME = "anthropic"
KEY_ENV = "ANTHROPIC_API_KEY"
# Tried by `check` when the configured tool type is rejected (newest first).
FALLBACK_TOOL_TYPES = ("web_search_20260209", "web_search_20250305")
# Server-side refusal fallback (opt-out with ANTHROPIC_FALLBACKS=off).
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def config() -> dict:
    return {
        # Configurable default. Check the current model id in the Anthropic models overview.
        "model": env_str("ANTHROPIC_MODEL", "claude-opus-5-5"),
        # Configurable default. Check the current tool type on the web search tool page.
        # Older fallback that every current model accepts: web_search_20250305.
        "tool_type": env_str("ANTHROPIC_WEB_SEARCH_TOOL", "web_search_20260318"),
        "max_uses": env_int("ANTHROPIC_MAX_SEARCHES", 5),
        "max_tokens": env_int("ANTHROPIC_MAX_TOKENS", 16000),
        # Effort is the cost/depth control on current models. Blank = leave it out
        # (some older models reject the field).
        "effort": os.environ.get("ANTHROPIC_EFFORT", "medium").strip(),
        # "default" lets the API rerun a declined request on its recommended fallback
        # model; the served model is recorded in the model column. "off" disables it.
        "fallbacks": env_str("ANTHROPIC_FALLBACKS", "default"),
        "max_continuations": env_int("ANTHROPIC_MAX_CONTINUATIONS", 5),
        "user_location": user_location_from_env(),
    }


def available() -> bool:
    return bool(os.environ.get(KEY_ENV, "").strip())


def make_client():
    import anthropic  # imported only for live calls; mock mode never needs it

    return anthropic.Anthropic(max_retries=4)


def build_tool(cfg: dict, tool_type: str | None = None) -> dict:
    tool = {"type": tool_type or cfg["tool_type"], "name": "web_search", "max_uses": cfg["max_uses"]}
    if cfg.get("user_location"):
        tool["user_location"] = cfg["user_location"]
    return tool


def _create(client, cfg: dict, messages: list, tools: list, max_tokens: int):
    kwargs = dict(model=cfg["model"], max_tokens=max_tokens, system=panel_instruction(),
                  messages=messages, tools=tools)
    extra: dict = {}
    if cfg.get("effort"):
        extra["output_config"] = {"effort": cfg["effort"]}
    fallbacks = (cfg.get("fallbacks") or "").strip()
    if fallbacks and fallbacks.lower() != "off":
        extra["fallbacks"] = fallbacks
        # extra_body keeps this working on SDK versions that predate the typed parameter.
        return client.beta.messages.create(betas=[FALLBACK_BETA], extra_body=extra, **kwargs)
    if extra:
        kwargs["extra_body"] = extra
    return client.messages.create(**kwargs)


def _content_for_resend(resp) -> list:
    content = getattr(resp, "content", None)
    if isinstance(content, list):
        return list(content)          # SDK block objects, sent back unchanged
    return list((to_dict(resp) or {}).get("content") or [])


def run_turn(client, cfg: dict, prompt: str) -> list:
    """Send one prompt; follow pause_turn continuations. Returns every raw response."""
    tools = [build_tool(cfg)]
    messages: list = [{"role": "user", "content": prompt}]
    assistant_so_far: list = []
    responses: list = []
    for _ in range(max(0, cfg.get("max_continuations", 5)) + 1):
        resp = _create(client, cfg, messages, tools, cfg["max_tokens"])
        responses.append(resp)
        if (to_dict(resp) or {}).get("stop_reason") != "pause_turn":
            break
        # Resend the user turn and the whole assistant turn so far. No extra
        # "continue" message: the API sees the trailing server tool use and resumes.
        assistant_so_far.extend(_content_for_resend(resp))
        messages = [{"role": "user", "content": prompt},
                    {"role": "assistant", "content": list(assistant_so_far)}]
    return responses


def _note(ans: Answer, note: str) -> None:
    if note not in ans.notes:
        ans.notes.append(note)


def parse_responses(responses: list, ans: Answer) -> Answer:
    texts: list[str] = []
    queries: list[str] = []
    last: dict = {}
    for resp in responses:
        d = to_dict(resp) or {}
        last = d
        ans.model = d.get("model") or ans.model
        usage = d.get("usage") or {}
        if not usage:
            ans.usage_reported = False
        # Cache fields are counted at the input price (the monitor does not use caching).
        in_tok = (as_int(usage.get("input_tokens"))
                  + as_int(usage.get("cache_creation_input_tokens"))
                  + as_int(usage.get("cache_read_input_tokens")))
        out_tok = as_int(usage.get("output_tokens"))
        # With server-side fallbacks, top-level usage covers only the attempt that produced
        # the message; usage.iterations lists every attempt. Sum the iterations when present
        # (never less than the top level), so a declined attempt is not left out of the cost.
        iters = [it for it in (usage.get("iterations") or []) if isinstance(it, dict)]
        if iters:
            in_tok = max(in_tok, sum(as_int(it.get("input_tokens"))
                                     + as_int(it.get("cache_creation_input_tokens"))
                                     + as_int(it.get("cache_read_input_tokens")) for it in iters))
            out_tok = max(out_tok, sum(as_int(it.get("output_tokens")) for it in iters))
            if any(it.get("type") == "fallback_message" for it in iters):
                # The served-by signal (a fallback block is not sent on sticky-routed turns).
                _note(ans, "served_by_fallback_model")
                _note(ans, "fallback_tokens_priced_at_ANTHROPIC_prices")
        ans.input_tokens += in_tok
        ans.output_tokens += out_tok
        ans.search_calls += as_int((usage.get("server_tool_use") or {}).get("web_search_requests"))
        for block in d.get("content") or []:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                texts.append(block.get("text") or "")
                for c in block.get("citations") or []:
                    if isinstance(c, dict) and c.get("type") == "web_search_result_location":
                        ans.add_citation(c.get("url") or "", c.get("title") or "")
            elif btype == "server_tool_use" and block.get("name") == "web_search":
                q = (block.get("input") or {}).get("query")
                if q:
                    queries.append(str(q))
            elif btype == "web_search_tool_result":
                content = block.get("content")
                if isinstance(content, list):          # success: a list of results
                    for r in content:
                        if isinstance(r, dict) and r.get("type") == "web_search_result":
                            ans.add_source(r.get("url") or "")
                elif isinstance(content, dict):        # error: a single object
                    ans.notes.append("web_search_error:" + str(content.get("error_code") or "unknown"))
            elif btype == "fallback":
                _note(ans, "served_by_fallback_model")
    ans.search_queries = unique(queries)
    ans.stop_reason = last.get("stop_reason") or ""
    # Text blocks are split at citation boundaries, so join them without a separator.
    ans.text = "".join(texts)
    if ans.stop_reason == "refusal":
        details = last.get("stop_details") or {}
        ans.error = "refusal:" + str(details.get("category") or "unspecified")
        ans.text, ans.citations = "", []
    elif ans.stop_reason == "pause_turn":
        ans.notes.append("still_paused_after_max_continuations")
    elif ans.stop_reason == "max_tokens":
        ans.notes.append("truncated_at_max_tokens")
    return ans


def _blank_answer(cfg: dict) -> Answer:
    return Answer(provider=NAME, model=cfg["model"], tool_version=cfg["tool_type"],
                  user_location=describe_location(cfg.get("user_location") or {}))


def classify_error(exc: BaseException) -> str:
    try:
        import anthropic
    except ImportError:
        return f"{type(exc).__name__}: {short_error(exc)}"
    # Most specific first: these are all subclasses of APIStatusError.
    if isinstance(exc, anthropic.NotFoundError):
        return "not_found (check ANTHROPIC_MODEL): " + short_error(exc)
    if isinstance(exc, anthropic.AuthenticationError):
        return "authentication_failed (check ANTHROPIC_API_KEY)"
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "permission_denied: " + short_error(exc)
    if isinstance(exc, anthropic.BadRequestError):
        return ("bad_request (check ANTHROPIC_MODEL, ANTHROPIC_WEB_SEARCH_TOOL, "
                "ANTHROPIC_EFFORT, ANTHROPIC_FALLBACKS): " + short_error(exc))
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limited_after_retries"
    if isinstance(exc, anthropic.APIStatusError):
        return f"api_error_{exc.status_code}: " + short_error(exc)
    if isinstance(exc, anthropic.APIConnectionError):
        return "connection_error: " + short_error(exc)
    return f"{type(exc).__name__}: {short_error(exc)}"


def ask(prompt: str, cfg: dict | None = None, client=None) -> Answer:
    cfg = cfg or config()
    ans = _blank_answer(cfg)
    try:
        client = client or make_client()
        responses = run_turn(client, cfg, prompt)
    except Exception as exc:  # recorded in the error column; the run continues
        ans.error = classify_error(exc)
        return ans
    return parse_responses(responses, ans)


def parse_fixture(raw) -> Answer:
    """Mock mode: a fixture is one recorded response or a list (pause_turn sequence)."""
    cfg = config()
    responses = raw if isinstance(raw, list) else [raw]
    return parse_responses(responses, _blank_answer(cfg))


def _is_bad_request(exc: BaseException) -> bool:
    try:
        import anthropic
        return isinstance(exc, anthropic.BadRequestError)
    except ImportError:
        return getattr(exc, "status_code", None) == 400


def check(cfg: dict | None = None, client=None) -> tuple[bool, str]:
    """One tiny call (at most one search) to confirm the model and the tool are accepted."""
    cfg = dict(cfg or config(), max_uses=1)
    client = client or make_client()
    tried: list[str] = []
    candidates = [cfg["tool_type"]] + [t for t in FALLBACK_TOOL_TYPES if t != cfg["tool_type"]]
    for tool_type in candidates:
        try:
            resp = _create(client, cfg,
                           [{"role": "user", "content": "Reply with the single word OK. Do not search."}],
                           [build_tool(cfg, tool_type)], 2048)
        except Exception as exc:
            tried.append(f"{tool_type}: {classify_error(exc)}")
            if _is_bad_request(exc):
                continue
            return False, " | ".join(tried)
        d = to_dict(resp) or {}
        msg = f"model {d.get('model')} answered with tool {tool_type} (stop_reason {d.get('stop_reason')})"
        if tool_type != cfg["tool_type"]:
            return False, (f"{msg}. Your configured tool was rejected: set "
                           f"ANTHROPIC_WEB_SEARCH_TOOL={tool_type} in .env. Tried: " + " | ".join(tried))
        return True, msg
    return False, " | ".join(tried)
