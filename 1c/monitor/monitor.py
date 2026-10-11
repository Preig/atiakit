#!/usr/bin/env python3
"""AI answer monitor: ask Claude, ChatGPT (OpenAI API) and Gemini the same traveler
questions every week, with live web search, and record whether each watched business
is named (Appear) and whether its website is among the sources (Cited).

Commands
  python monitor.py check              one tiny call per provider: is the model and search tool accepted?
  python monitor.py run --mock         no keys, no network: replays recorded fictional answers
  python monitor.py run --dry-run      real calls, first 2 prompts only
  python monitor.py run                real calls, every prompt in prompts.csv
  python monitor.py diff               write weekly_diff.md (gains, losses, new sources, quarterly trend)
  python monitor.py cost               write cost_report.md (measured cost, budget, projection)

Settings are read from, highest first: your environment, .env, settings.env, .env.example.
Keys belong in .env (never committed) or in GitHub Secrets.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import providers  # noqa: E402
from costs import (answer_cost, budget_from_env, cost_report, estimate_next_call,  # noqa: E402
                   missing_prices, month_searches, month_spend, prices_for)
from matching import find_mentions, load_names  # noqa: E402
from providers.common import env_bool, env_float, env_str  # noqa: E402
from report import build_diff  # noqa: E402
from storage import (SchemaMismatch, append_answer, append_results, read_answers,  # noqa: E402
                     read_results, write_text)

ENV_FILES = (".env.example", "settings.env", ".env")   # lowest precedence first
STORE_TEXT_DEFAULTS = {"anthropic": True, "openai": True, "gemini": False}


# ---------------------------------------------------------------- settings
def parse_env_file(path: Path) -> dict:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if " #" in value and not value.startswith(('"', "'")):
            value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def load_settings(base: Path = HERE) -> None:
    if os.environ.get("MONITOR_SKIP_ENV_FILES") == "1":
        return
    merged: dict[str, str] = {}
    for name in ENV_FILES:
        merged.update(parse_env_file(base / name))
    for k, v in merged.items():
        if k not in os.environ:          # the real environment always wins
            os.environ[k] = v


def load_prompts(path: Path) -> list[dict]:
    import csv
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pid, text = (r.get("prompt_id") or "").strip(), (r.get("prompt") or "").strip()
            if pid and text and not pid.startswith("#"):
                rows.append({"prompt_id": pid, "prompt": text, "intent": (r.get("intent") or "").strip(),
                             "locale": (r.get("locale") or "").strip()})
    return rows


def out_dir(args) -> Path:
    if getattr(args, "out", None):
        p = Path(args.out)
        return p if p.is_absolute() else Path.cwd() / p
    return HERE / ("output_mock" if getattr(args, "mock", False) else env_str("OUTPUT_DIR", "output"))


def selected_providers(arg: str | None) -> list:
    raw = arg or env_str("PROVIDERS", ",".join(providers.ALL))
    return [providers.get(p) for p in raw.split(",") if p.strip()]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def say(msg: str = "") -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- run
def load_fixtures(folder: Path) -> dict:
    out = {}
    for name in providers.ALL:
        f = folder / f"{name}.json"
        if f.exists():
            out[name] = json.loads(f.read_text(encoding="utf-8")).get("responses", {})
    if not out:
        raise SystemExit(f"No fixtures found in {folder}")
    return out


def fixture_for(fixtures: dict, provider: str, prompt_id: str):
    table = fixtures.get(provider) or {}
    return table.get(prompt_id) if prompt_id in table else table.get("_default")


def answer_rows(run_id: str, date: str, ans, prompt_id: str, names: list, cost: float | None) -> list[dict]:
    mentions = find_mentions(ans.text, names, ans.citations) if not ans.error else {}
    rows = []
    for i, w in enumerate(names):
        m = mentions.get(w.name)
        row = {"run_id": run_id, "date": date, "provider": ans.provider, "model": ans.model,
               "tool_version": ans.tool_version, "user_location": ans.user_location,
               "prompt_id": prompt_id, "name": w.name, "error": ans.error}
        if m is not None:
            row.update({"appears": int(m.appears), "first_offset": m.first_offset,
                        "rank_among_watched": m.rank_among_watched, "mention_count": m.mention_count,
                        "cited": int(m.cited), "cited_urls": "; ".join(m.cited_urls)})
        if i == 0:
            # Usage and cost appear once per answer, so a column sum is the true total.
            row.update({"input_tokens": ans.input_tokens, "output_tokens": ans.output_tokens,
                        "search_calls": ans.search_calls,
                        "cost_usd_measured": "" if cost is None else f"{cost:.6f}"})
        rows.append(row)
    return rows


def cmd_run(args) -> int:
    mode = "mock" if args.mock else ("dry" if args.dry_run else "live")
    out = out_dir(args)
    prompts = load_prompts(Path(args.prompts))
    if args.dry_run:
        prompts = prompts[:2]
    if args.limit:
        prompts = prompts[:args.limit]
    names = load_names(Path(args.names))
    if not prompts or not names:
        say("prompts.csv and names.csv need at least one row each.")
        return 2
    results_path, answers_path = out / "results.csv", out / "answers.jsonl"
    history = read_answers(answers_path)
    now = utc_now()
    suffix = {"mock": "-mock", "dry": "-dry", "live": ""}[mode]
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    taken = {a.get("run_id") for a in history}
    run_id, n = stamp + suffix, 1
    while run_id in taken:          # two runs in the same second stay distinct
        n += 1
        run_id = f"{stamp}-{n}{suffix}"
    date = now.strftime("%Y-%m-%d")
    month = date[:7]
    budget = budget_from_env()
    fixtures = load_fixtures(Path(args.fixtures)) if mode == "mock" else {}

    active = []
    for mod in selected_providers(args.providers):
        if mode != "mock":
            if not mod.available():
                say(f"[{mod.NAME}] skipped: no API key. Set {mod.KEY_ENV} in .env to include it.")
                continue
            miss = missing_prices(mod.NAME)
            if miss and budget is not None and not env_bool("ALLOW_UNPRICED", False):
                say(f"[{mod.NAME}] skipped: prices not set ({', '.join(miss)}). The budget stop cannot "
                    f"count spending without them. Set them in .env from the provider's pricing page.")
                continue
        active.append(mod)
    if not active:
        say("Nothing to run. Try `python monitor.py run --mock` first, or add keys and prices to .env.")
        return 2
    cfgs = {mod.NAME: mod.config() for mod in active}
    pause = env_float("SLEEP_BETWEEN_CALLS")
    if pause is None or mode == "mock":
        pause = 0.0 if mode == "mock" else 1.0
    default_est = env_float("EST_COST_PER_ANSWER")
    if default_est is None:
        default_est = 0.10

    spent = month_spend(history, month)
    free_used = {mod.NAME: month_searches(history, month, mod.NAME) for mod in active}
    say(f"Run {run_id}: {len(prompts)} prompts x {len(active)} providers ({', '.join(m.NAME for m in active)}), "
        f"{len(names)} watched names, mode {mode}. Output: {out}")
    if mode != "mock" and budget is not None:
        say(f"Spent this month so far: ${spent:.2f} of ${budget:.2f} MONTHLY_BUDGET.")

    stopped = False
    run_cost = 0.0
    n_answers = 0
    new_records: list[dict] = []
    for pr in prompts:
        for mod in active:
            if mode != "mock" and budget is not None:
                est = estimate_next_call(history + new_records, mod.NAME, default_est)
                if spent + est > budget:
                    say(f"BUDGET STOP: ${spent:.2f} spent this month; the next answer would pass "
                        f"${budget:.2f}. Raise MONTHLY_BUDGET in .env or wait for next month.")
                    stopped = True
                    break
            if mode == "mock":
                raw = fixture_for(fixtures, mod.NAME, pr["prompt_id"])
                if raw is None:
                    continue
                ans = mod.parse_fixture(raw)
            else:
                ans = mod.ask(pr["prompt"], cfgs[mod.NAME])
                if pause:
                    time.sleep(pause)
            free_left = max(0.0, prices_for(mod.NAME)["free_searches"] - free_used.get(mod.NAME, 0))
            cost, _ = answer_cost(mod.NAME, ans.input_tokens, ans.output_tokens, ans.search_calls, free_left)
            free_used[mod.NAME] = free_used.get(mod.NAME, 0) + ans.search_calls
            if mode != "mock" and cost:
                spent += cost
            run_cost += cost or 0.0
            store_text = env_bool(f"STORE_FULL_TEXT_{mod.NAME.upper()}", STORE_TEXT_DEFAULTS[mod.NAME])
            record = {"run_id": run_id, "date": date, "mode": mode, "provider": mod.NAME, "model": ans.model,
                      "tool_version": ans.tool_version, "user_location": ans.user_location,
                      "prompt_id": pr["prompt_id"], "prompt": pr["prompt"], "stop_reason": ans.stop_reason,
                      "text": ans.text if store_text else None, "text_stored": store_text,
                      "text_chars": len(ans.text), "citations": ans.citations, "sources": ans.sources,
                      "search_queries": ans.search_queries, "input_tokens": ans.input_tokens,
                      "output_tokens": ans.output_tokens, "search_calls": ans.search_calls,
                      "cost_usd_measured": cost, "usage_reported": ans.usage_reported,
                      "error": ans.error, "notes": ans.notes}
            rows = answer_rows(run_id, date, ans, pr["prompt_id"], names, cost)
            try:
                append_results(results_path, rows)
            except SchemaMismatch as exc:
                say(str(exc))
                return 2
            append_answer(answers_path, record)
            new_records.append(record)
            n_answers += 1
            named = [r["name"] + (" (cited)" if r.get("cited") == 1 else "") for r in rows if r.get("appears") == 1]
            status = ("ERROR " + ans.error) if ans.error else ("named: " + (", ".join(named) or "none of the watched names"))
            say(f"  [{mod.NAME}] {pr['prompt_id']}: {status}")
        if stopped:
            break
    if mode == "mock":
        say(f"Done: {n_answers} recorded answers. Nothing was spent. At your .env prices these recorded "
            f"answers would have cost ${run_cost:.2f} (priced providers only).")
    else:
        say(f"Done: {n_answers} answers. Measured cost this run: ${run_cost:.2f}.")
    say(f"Next: python monitor.py diff{' --mock' if mode == 'mock' else ''}")
    return 3 if stopped else 0


# ---------------------------------------------------------------- diff, cost, check
def cmd_diff(args) -> int:
    out = out_dir(args)
    names_order = [w.name for w in load_names(Path(args.names))] if Path(args.names).exists() else None
    md = build_diff(read_results(out / "results.csv"), read_answers(out / "answers.jsonl"), names_order,
                    new_run=args.run, old_run=args.against, include_dry=args.include_dry,
                    generated=utc_now().strftime("%Y-%m-%d %H:%M UTC"))
    write_text(out / "weekly_diff.md", md)
    say(md)
    say(f"Saved {out / 'weekly_diff.md'}")
    return 0


def cmd_cost(args) -> int:
    out = out_dir(args)
    answers = read_answers(out / "answers.jsonl")
    prompts_count = len(load_prompts(Path(args.prompts))) if Path(args.prompts).exists() else 0
    md = cost_report(answers, prompts_count, utc_now().strftime("%Y-%m"))
    write_text(out / "cost_report.md", md)
    say(md)
    say(f"Saved {out / 'cost_report.md'}")
    return 0


def cmd_check(args) -> int:
    ok_all = True
    if args.mock:
        fixtures = load_fixtures(Path(args.fixtures))
        for prov, table in fixtures.items():
            mod = providers.get(prov)
            for pid, raw in table.items():
                ans = mod.parse_fixture(raw)
                if not ans.text and not ans.error:
                    ok_all = False
                    say(f"[{prov}] fixture {pid}: no text parsed")
            say(f"[{prov}] {len(table)} fixtures parse")
        return 0 if ok_all else 1
    for mod in selected_providers(args.providers):
        if not mod.available():
            say(f"[{mod.NAME}] SKIP: no key. Set {mod.KEY_ENV} in .env.")
            continue
        ok, msg = mod.check()
        ok_all &= ok
        say(f"[{mod.NAME}] {'OK' if ok else 'PROBLEM'}: {msg}")
        miss = missing_prices(mod.NAME)
        if miss:
            say(f"[{mod.NAME}] prices not set: {', '.join(miss)} (needed for cost and the budget stop)")
    budget = budget_from_env()
    say(f"MONTHLY_BUDGET: {'off' if budget is None else f'${budget:.2f}'}")
    return 0 if ok_all else 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # Windows consoles
    except (AttributeError, ValueError):
        pass
    load_settings()
    ap = argparse.ArgumentParser(prog="monitor.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, fixtures=False):
        p.add_argument("--out", help="output folder (default: output, or output_mock with --mock)")
        p.add_argument("--prompts", default=str(HERE / "prompts.csv"))
        p.add_argument("--names", default=str(HERE / "names.csv"))
        p.add_argument("--providers", help="comma list, e.g. anthropic,openai (default: PROVIDERS or all)")
        p.add_argument("--mock", action="store_true", help="no network; use recorded fixtures")
        if fixtures:
            p.add_argument("--fixtures", default=str(HERE / "fixtures" / "week1"),
                           help="fixture folder for --mock (fixtures/week1 or fixtures/week2)")

    p_run = sub.add_parser("run", help="ask every prompt and record the results")
    common(p_run, fixtures=True)
    p_run.add_argument("--dry-run", action="store_true", help="real calls, first 2 prompts only")
    p_run.add_argument("--limit", type=int, default=0, help="only the first N prompts")
    p_check = sub.add_parser("check", help="one tiny call per provider")
    common(p_check, fixtures=True)
    p_diff = sub.add_parser("diff", help="write weekly_diff.md")
    common(p_diff)
    p_diff.add_argument("--run", help="run_id to report (default: latest)")
    p_diff.add_argument("--against", help="run_id to compare with (default: the one before)")
    p_diff.add_argument("--include-dry", action="store_true", help="count dry runs too")
    p_cost = sub.add_parser("cost", help="write cost_report.md")
    common(p_cost)

    args = ap.parse_args(argv)
    if args.cmd == "run" and args.mock and args.dry_run:
        say("Note: --mock with --dry-run replays 2 recorded prompts.")
    return {"run": cmd_run, "diff": cmd_diff, "cost": cmd_cost, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
