"""Weekly diff: who gained or lost mentions, which sources are new, and the quarterly trend.

Week-over-week changes are mostly noise. The quarterly table is the one to act on.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from matching import citation_domain

HEADER_NOTES = [
    "DRAFT - PENDING OWNER REVIEW",
    "",
    "Read this first:",
    "- One week is noise. The same question asked twice can get different answers. "
    "Act on the quarterly table at the end, not on one week's change.",
    "- API answers are a proxy panel. They are not what the consumer apps show a given traveler "
    "(different settings, location, history and features).",
    "- Appear and Cited are counted here. Described and Current stay human: read the answers listed "
    "under \"Read by hand\" and score them with the audit rubric.",
    "- If you share answers with members or staff, show their citations with them "
    "(Contractual: check the Anthropic and OpenAI usage terms, and the Gemini API terms).",
]


def _quarter(date: str) -> str:
    try:
        y, m = int(date[:4]), int(date[5:7])
    except (ValueError, TypeError):
        return "unknown"
    return f"{y}-Q{(m - 1) // 3 + 1}"


def _n(k: int, word: str) -> str:
    return f"{k} {word}" + ("" if k == 1 else "s")


def _pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{n} of {d} ({round(100 * n / d)}%)"


def run_ids(answers: list[dict], include_dry: bool = False) -> list[str]:
    seen: list[str] = []
    for a in answers:
        rid = a.get("run_id")
        if not rid or rid in seen:
            continue
        if a.get("mode") == "dry" and not include_dry:
            continue
        seen.append(rid)
    return seen


def build_diff(results: list[dict], answers: list[dict], names_order: list[str] | None = None,
               new_run: str | None = None, old_run: str | None = None,
               include_dry: bool = False, generated: str = "") -> str:
    runs = run_ids(answers, include_dry)
    lines = ["# Weekly AI answer diff", ""] + HEADER_NOTES + [""]
    if generated:
        lines.insert(2, f"Generated {generated}.")
        lines.insert(3, "")
    if not runs:
        return "\n".join(lines + ["No runs recorded yet.", ""])
    new_run = new_run or runs[-1]
    if old_run is None:
        earlier = [r for r in runs if r != new_run and runs.index(r) < runs.index(new_run)] if new_run in runs else runs[:-1]
        old_run = earlier[-1] if earlier else None

    ans_by_run: dict[str, list[dict]] = defaultdict(list)
    for a in answers:
        ans_by_run[a.get("run_id", "")].append(a)
    flags: dict[tuple, dict] = {}
    names: list[str] = list(names_order or [])
    for r in results:
        key = (r.get("run_id"), r.get("provider"), r.get("prompt_id"), r.get("name"))
        flags[key] = {"appears": r.get("appears") == "1", "cited": r.get("cited") == "1"}
        if r.get("name") and r["name"] not in names:
            names.append(r["name"])

    def valid_keys(run: str | None) -> set:
        return {(a.get("provider"), a.get("prompt_id")) for a in ans_by_run.get(run or "", []) if not a.get("error")}

    def count(run: str | None, name: str, what: str, keys: set) -> int:
        return sum(1 for (p, q) in keys if flags.get((run, p, q, name), {}).get(what))

    new_keys, old_keys = valid_keys(new_run), valid_keys(old_run)
    new_meta = ans_by_run[new_run][0] if ans_by_run.get(new_run) else {}
    lines += ["## Runs compared", "",
              f"- This run: `{new_run}` ({new_meta.get('date', '')}, {new_meta.get('mode', '')}), "
              f"{len(new_keys)} answers without errors"]
    if old_run:
        old_meta = ans_by_run[old_run][0] if ans_by_run.get(old_run) else {}
        lines.append(f"- Previous run: `{old_run}` ({old_meta.get('date', '')}, {old_meta.get('mode', '')}), "
                     f"{len(old_keys)} answers without errors")
    else:
        lines.append("- Previous run: none yet. Run again next week to see changes.")
    lines.append("")

    lines += ["## Who was named and cited", "",
              "| Name | Named this run | Named last run | Cited this run | Cited last run |",
              "|---|---|---|---|---|"]
    for n in names:
        lines.append(f"| {n} | {_pct(count(new_run, n, 'appears', new_keys), len(new_keys))} | "
                     f"{_pct(count(old_run, n, 'appears', old_keys), len(old_keys)) if old_run else 'n/a'} | "
                     f"{_pct(count(new_run, n, 'cited', new_keys), len(new_keys))} | "
                     f"{_pct(count(old_run, n, 'cited', old_keys), len(old_keys)) if old_run else 'n/a'} |")
    lines.append("")

    if old_run:
        both = sorted(new_keys & old_keys)
        gained, lost = [], []
        for n in names:
            for (p, q) in both:
                a_new = flags.get((new_run, p, q, n), {}).get("appears", False)
                a_old = flags.get((old_run, p, q, n), {}).get("appears", False)
                if a_new and not a_old:
                    gained.append(f"- {n}: {p}, prompt {q}")
                elif a_old and not a_new:
                    lost.append(f"- {n}: {p}, prompt {q}")
        lines += ["## Gained mentions (same prompt and tool, named now, not last run)", ""]
        lines += gained or ["- None"]
        lines += ["", "## Lost mentions (named last run, not now)", ""]
        lines += lost or ["- None"]
        lines.append("")

    # Sources
    def domains_of(ans_list: list[dict]) -> Counter:
        c: Counter = Counter()
        for a in ans_list:
            ds = {citation_domain(x) for x in a.get("citations") or []}
            c.update(d for d in ds if d)
        return c

    new_domains = domains_of(ans_by_run.get(new_run, []))
    earlier_runs = runs[:runs.index(new_run)] if new_run in runs else []
    earlier_answers = [a for r in earlier_runs for a in ans_by_run.get(r, [])]
    seen_before = set(domains_of(earlier_answers))
    first_time = [(d, k) for d, k in new_domains.most_common() if d not in seen_before]
    lines += ["## Sources cited for the first time", ""]
    if not earlier_runs:
        lines.append("- First run: every source is new. This list starts next run.")
    else:
        lines += [f"- {d} (cited in {_n(k, 'answer')})" for d, k in first_time] or ["- None"]
    lines += ["", "## Most-cited sources this run", "",
              "Where the AI tools get their facts. If these are listing sites, keep those listings current.", ""]
    lines += [f"- {d}: {_n(k, 'answer')}" for d, k in new_domains.most_common(10)] or ["- No citations recorded"]
    lines.append("")

    # Read by hand
    member_named = []
    for a in ans_by_run.get(new_run, []):
        if a.get("error"):
            continue
        who = [n for n in names if flags.get((new_run, a.get("provider"), a.get("prompt_id"), n), {}).get("appears")]
        if who:
            member_named.append(f"- {a.get('provider')}, prompt {a.get('prompt_id')}: {', '.join(who)}"
                                + ("" if a.get("text_stored", True) else " (text not stored; rerun by hand)"))
    lines += ["## Read by hand: Described and Current", "",
              "Open these answers in answers.jsonl. Is the business in the right category, place and promise? "
              "Are prices and policies today's? Score with the audit rubric (0 no, 1 partly, 2 yes).", ""]
    lines += member_named[:30] or ["- No watched name was named this run."]
    lines.append("")

    # Errors
    errs = [a for a in ans_by_run.get(new_run, []) if a.get("error")]
    if errs:
        lines += ["## Errors this run", ""]
        by_p: dict[str, list[str]] = defaultdict(list)
        for a in errs:
            by_p[a.get("provider", "?")].append(a.get("error", ""))
        for p, es in by_p.items():
            lines.append(f"- {p}: {_n(len(es), 'answer')} failed. First error: {es[0]}")
        lines.append("")

    # Quarterly trend
    q_keys: dict[str, set] = defaultdict(set)
    q_runs: dict[str, set] = defaultdict(set)
    for rid in runs:
        for a in ans_by_run.get(rid, []):
            if not a.get("error"):
                q = _quarter(a.get("date", ""))
                q_keys[q].add((rid, a.get("provider"), a.get("prompt_id")))
                q_runs[q].add(rid)
    quarters = sorted(q_keys)[-4:]
    lines += ["## Quarterly trend (act on this table)", "",
              "Share of answers that named each business, all tools and prompts pooled. "
              "Report this once a quarter; a change of a few points is still within noise.", ""]
    lines.append("| Name | " + " | ".join(f"{q} ({len(q_runs[q])} runs)" for q in quarters) + " |")
    lines.append("|---|" + "---|" * len(quarters))
    for n in names:
        cells = []
        for q in quarters:
            ks = q_keys[q]
            k = sum(1 for (rid, p, pr) in ks if flags.get((rid, p, pr, n), {}).get("appears"))
            cells.append(_pct(k, len(ks)))
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)
