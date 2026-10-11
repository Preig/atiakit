"""Cost from what each provider reports, times the prices you set in .env.

Nothing here is an estimate from assumptions: cost = reported input tokens x input price
+ reported output tokens x output price + billed searches x search price. The provider's
billing page is the real bill; use this to watch the trend and to stop a runaway run.
"""
from __future__ import annotations

from collections import defaultdict

from providers.common import env_float, env_str

PRICE_VARS = {
    "anthropic": ("ANTHROPIC_PRICE_INPUT_PER_MTOK", "ANTHROPIC_PRICE_OUTPUT_PER_MTOK",
                  "ANTHROPIC_PRICE_PER_1K_SEARCHES"),
    "openai": ("OPENAI_PRICE_INPUT_PER_MTOK", "OPENAI_PRICE_OUTPUT_PER_MTOK",
               "OPENAI_PRICE_PER_1K_SEARCHES"),
    "gemini": ("GEMINI_PRICE_INPUT_PER_MTOK", "GEMINI_PRICE_OUTPUT_PER_MTOK",
               "GEMINI_PRICE_PER_1K_SEARCHES"),
}
FREE_SEARCH_VARS = {"gemini": "GEMINI_FREE_SEARCHES_PER_MONTH"}
BILLABLE_MODES = ("live", "dry")      # mock runs spend nothing


def prices_for(provider: str) -> dict:
    i, o, s = PRICE_VARS[provider]
    free_var = FREE_SEARCH_VARS.get(provider)
    return {"input": env_float(i), "output": env_float(o), "search": env_float(s),
            "free_searches": (env_float(free_var) or 0.0) if free_var else 0.0}


def missing_prices(provider: str) -> list[str]:
    return [var for var in PRICE_VARS[provider] if env_float(var) is None]


def answer_cost(provider: str, input_tokens: int, output_tokens: int, search_calls: int,
                free_searches_left: float = 0.0) -> tuple[float | None, int]:
    """Returns (cost in USD or None if any needed price is missing, billable searches)."""
    p = prices_for(provider)
    billable = max(0, int(search_calls - max(0.0, free_searches_left)))
    if p["input"] is None or p["output"] is None or (billable and p["search"] is None):
        return None, billable
    cost = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
    cost += billable * (p["search"] or 0.0) / 1000
    return round(cost, 6), billable


def budget_from_env() -> float | None:
    """MONTHLY_BUDGET in USD (default 25). 'none' turns the stop off."""
    raw = env_str("MONTHLY_BUDGET", "25")
    if raw.lower() in ("none", "off", "no"):
        return None
    try:
        return float(raw)
    except ValueError:
        return 25.0


def month_of(record: dict) -> str:
    return str(record.get("date") or "")[:7]


def month_spend(answers: list[dict], month: str) -> float:
    return round(sum(float(a.get("cost_usd_measured") or 0.0) for a in answers
                     if month_of(a) == month and a.get("mode") in BILLABLE_MODES), 6)


def month_searches(answers: list[dict], month: str, provider: str) -> int:
    return sum(int(a.get("search_calls") or 0) for a in answers
               if month_of(a) == month and a.get("provider") == provider and a.get("mode") in BILLABLE_MODES)


def estimate_next_call(answers: list[dict], provider: str, default: float) -> float:
    """Average measured cost of this provider's last 10 priced answers, else the default."""
    costs = [float(a["cost_usd_measured"]) for a in answers
             if a.get("provider") == provider and a.get("cost_usd_measured") not in (None, "")
             and a.get("mode") in BILLABLE_MODES][-10:]
    return sum(costs) / len(costs) if costs else default


def _money(v: float | None) -> str:
    return "n/a" if v is None else f"${v:,.2f}"


def cost_report(answers: list[dict], prompts_count: int, today_month: str) -> str:
    """Markdown summary by month and provider, plus a projection from measured averages."""
    lines = ["# Cost report", "", "DRAFT - PENDING OWNER REVIEW", "",
             "Measured from the usage each provider reported, times the prices set in your .env. "
             "Your provider billing pages are the actual bill. Mock runs are listed but cost nothing.", ""]
    if not answers:
        return "\n".join(lines + ["No answers recorded yet. Run `python monitor.py run --mock` to try it.", ""])
    by = defaultdict(lambda: {"answers": 0, "in": 0, "out": 0, "search": 0, "cost": 0.0, "unpriced": 0})
    for a in answers:
        key = (month_of(a), a.get("mode") or "live", a.get("provider") or "?")
        b = by[key]
        b["answers"] += 1
        b["in"] += int(a.get("input_tokens") or 0)
        b["out"] += int(a.get("output_tokens") or 0)
        b["search"] += int(a.get("search_calls") or 0)
        if a.get("cost_usd_measured") in (None, ""):
            b["unpriced"] += 1
        else:
            b["cost"] += float(a["cost_usd_measured"])
    lines += ["| Month | Mode | Provider | Answers | Input tokens | Output tokens | Searches | Cost | Answers without a price |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for (month, mode, prov), b in sorted(by.items()):
        if b["unpriced"] == b["answers"]:
            cost_cell = "n/a (price not set)"
        elif mode == "mock":
            cost_cell = f"{_money(b['cost'])} (not spent)"
        else:
            cost_cell = _money(b["cost"])
        lines.append(f"| {month} | {mode} | {prov} | {b['answers']} | {b['in']:,} | {b['out']:,} | "
                     f"{b['search']} | {cost_cell} | {b['unpriced']} |")
    spent = month_spend(answers, today_month)
    budget = budget_from_env()
    lines += ["", f"**Spent this month ({today_month}, live and dry runs):** {_money(spent)}"
              + (f" of a {_money(budget)} MONTHLY_BUDGET." if budget is not None else " (no budget stop set).")]
    # Projection from measured averages per provider (live and dry only).
    avgs = {}
    for prov in PRICE_VARS:
        priced = [float(a["cost_usd_measured"]) for a in answers if a.get("provider") == prov
                  and a.get("mode") in BILLABLE_MODES and a.get("cost_usd_measured") not in (None, "")]
        if priced:
            avgs[prov] = sum(priced) / len(priced)
    if avgs:
        per_run = sum(avgs.values()) * prompts_count
        lines += ["", "**Projection from measured averages** (estimate): "
                  f"{prompts_count} prompts x {len(avgs)} providers is about {_money(per_run)} a weekly run, "
                  f"about {_money(per_run * 4.33)} a month."]
        for prov, v in sorted(avgs.items()):
            lines.append(f"- {prov}: about {_money(v)} an answer")
    else:
        lines += ["", "No priced live answers yet, so there is no projection. "
                  "Run `python monitor.py run --dry-run` after setting prices in .env."]
    for prov in PRICE_VARS:
        miss = missing_prices(prov)
        if miss:
            lines.append(f"- Prices not set for {prov}: {', '.join(miss)}")
    lines.append("")
    return "\n".join(lines)
