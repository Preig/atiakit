"""Treatment versus holdout report for Number 4: in-window changes and cancellations.

Bookings are compared by the arm they were assigned to (intention to treat), whether or not a
draft was approved and sent. Operator cancellations (for example a marine warning) are not guest
decisions, so they are counted separately and left out of the rate.
"""
from __future__ import annotations

import csv
import datetime as dt
import os

from retention.stats import required_sample, wilson

EVENTS = ("changed_in_window", "cancelled_in_window")
SEGMENTS = (
    ("All eligible bookings", lambda r: True),
    ("Flexible rate", lambda r: r.get("rate_type") == "flexible"),
    ("Non-refundable rate", lambda r: r.get("rate_type") == "non_refundable"),
)
CSV_FIELDS = [
    "segment", "arm", "assigned", "with_outcome", "operator_cancelled_excluded", "n",
    "changed_in_window", "cancelled_in_window", "events", "rate", "ci95_low", "ci95_high",
    "value_of_in_window_cancellations_usd", "read",
]


def _money(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def arm_stats(rows: list[dict], outcomes: dict) -> dict:
    assigned = len(rows)
    with_outcome = [r for r in rows if outcomes.get(r["booking_id"])]
    op = [r for r in with_outcome if outcomes[r["booking_id"]] == "operator_cancelled"]
    counted = [r for r in with_outcome if outcomes[r["booking_id"]] != "operator_cancelled"]
    changed = sum(1 for r in counted if outcomes[r["booking_id"]] == "changed_in_window")
    cancelled = sum(1 for r in counted if outcomes[r["booking_id"]] == "cancelled_in_window")
    events = changed + cancelled
    rate, lo, hi = wilson(events, len(counted))
    value = sum(_money(r.get("booking_value_usd")) for r in counted
                if outcomes[r["booking_id"]] == "cancelled_in_window")
    return {
        "assigned": assigned, "with_outcome": len(with_outcome), "operator_cancelled_excluded": len(op),
        "n": len(counted), "changed_in_window": changed, "cancelled_in_window": cancelled,
        "events": events, "rate": rate, "ci95_low": lo, "ci95_high": hi,
        "value_of_in_window_cancellations_usd": round(value, 2),
    }


def read_label(t: dict, h: dict, need: dict) -> str:
    if t["n"] == 0 or h["n"] == 0:
        return "NO DATA"
    if min(t["n"], h["n"]) < 30:
        return "TOO SMALL TO READ: counts only"
    if t["n"] < need["treatment"] or h["n"] < need["holdout"]:
        return "DIRECTIONAL ONLY"
    return "SAMPLE SIZE REACHED (still read the intervals)"


def pct(v) -> str:
    return "n/a" if v is None else "%.1f%%" % (100 * v)


def build(assignments: list[dict], outcome_rows: list[dict], rules: dict, queue: list[dict] | None = None,
          all_bookings: list[dict] | None = None, fictional: bool = False):
    """Return (markdown_text, csv_rows, summary_dict)."""
    outcomes = {r["booking_id"]: r.get("outcome", "") for r in outcome_rows}
    p = rules["power"]
    share = float(rules["holdout"]["share"])
    need = required_sample(p["baseline_rate"], p["target_rate"], share, p.get("alpha", 0.05), p.get("power", 0.8))
    csv_rows, blocks, summary = [], [], {}
    for seg_name, keep in SEGMENTS:
        seg = [r for r in assignments if keep(r)]
        t = arm_stats([r for r in seg if r["arm"] == "treatment"], outcomes)
        h = arm_stats([r for r in seg if r["arm"] == "holdout"], outcomes)
        label = read_label(t, h, need)
        summary[seg_name] = {"treatment": t, "holdout": h, "read": label}
        for arm, s in (("treatment", t), ("holdout", h)):
            row = {"segment": seg_name, "arm": arm, "read": label}
            row.update({k: ("" if s[k] is None else (round(s[k], 4) if isinstance(s[k], float) else s[k]))
                        for k in s})
            csv_rows.append(row)
        diff = ""
        if t["rate"] is not None and h["rate"] is not None:
            diff = "%+.1f points (treatment minus holdout)" % (100 * (t["rate"] - h["rate"]))
        lines = [
            "### %s" % seg_name,
            "",
            "| Arm | Assigned | Counted (n) | Changed in window | Cancelled in window | Rate | 95% interval | Value of in-window cancellations |",
            "|---|---:|---:|---:|---:|---:|---|---:|",
        ]
        for arm, s in (("Treatment", t), ("Holdout", h)):
            ci = "n/a" if s["rate"] is None else "%s to %s" % (pct(s["ci95_low"]), pct(s["ci95_high"]))
            lines.append("| %s | %d | %d | %d | %d | %s | %s | $%s |" % (
                arm, s["assigned"], s["n"], s["changed_in_window"], s["cancelled_in_window"],
                pct(s["rate"]), ci, format(s["value_of_in_window_cancellations_usd"], ",.0f")))
        lines.append("")
        lines.append(("**Read: %s.** %s" % (label, diff)).rstrip())
        if t["operator_cancelled_excluded"] or h["operator_cancelled_excluded"]:
            lines.append("")
            lines.append("Left out as operator cancellations: %d treatment, %d holdout."
                         % (t["operator_cancelled_excluded"], h["operator_cancelled_excluded"]))
        waiting = (t["assigned"] - t["with_outcome"]) + (h["assigned"] - h["with_outcome"])
        if waiting:
            lines.append("")
            lines.append("No outcome yet for %d assigned booking(s); they are not counted." % waiting)
        blocks.append("\n".join(lines))

    today = dt.date.today().isoformat()
    md = [
        "# Retention pilot report",
        "",
        "Generated %s. Holdout share %s, seed `%s`." % (today, rules["holdout"]["share"], rules["holdout"]["seed"]),
    ]
    if fictional:
        md += ["", "**FICTIONAL TEACHING DATA: Bay Light Day Cruises, Seward. The outcomes were simulated and the booking values are invented.**"]
    md += [
        "",
        "## How to read this",
        "",
        "- Number 4 = bookings changed or cancelled inside the free-cancellation window, divided by bookings with an outcome. Flexible and non-refundable are shown separately.",
        "- Bookings are compared by assigned arm, whether or not a draft was approved and sent.",
        "- Operator cancellations (for example a marine warning) are left out of the rate.",
        "- The 95% interval is a Wilson interval. If the treatment and holdout intervals overlap a lot, there is no clear difference.",
        "- A confirmatory read at a %d/%d treatment/holdout split needs about %s holdout and %s treatment bookings (%s%% to %s%%, alpha %s, power %s). Below that, a result is directional: worth noting, not evidence to scale on."
        % (round(100 * (1 - share)), round(100 * share), format(need["holdout"], ","), format(need["treatment"], ","),
           round(100 * p["baseline_rate"], 1), round(100 * p["target_rate"], 1), p.get("alpha", 0.05), p.get("power", 0.8)),
        "",
        "## Results",
        "",
    ]
    md += ["\n\n".join(blocks)]

    if queue is not None:
        counts: dict = {}
        for q in queue:
            counts[q.get("status", "")] = counts.get(q.get("status", ""), 0) + 1
        md += ["", "## Approval queue", ""]
        if counts:
            md += ["- %s: %d" % (k or "(blank)", v) for k, v in sorted(counts.items())]
        else:
            md += ["- The queue is empty."]
        md += ["", "Status values: PENDING (drafted, not reviewed), APPROVED, REJECTED, SENT_BY_STAFF (a person sent it from the booking platform)."]

    if all_bookings:
        md += ["", "## Context: every booking in the file", "",
               "Use this to choose the baseline rate for the power command.", ""]
        for label, keep in (("Flexible", "flexible"), ("Non-refundable", "non_refundable")):
            rows = [b for b in all_bookings if b.get("rate_type") == keep and outcomes.get(b["booking_id"])
                    and outcomes[b["booking_id"]] != "operator_cancelled"]
            ev = sum(1 for b in rows if outcomes[b["booking_id"]] in EVENTS)
            r, lo, hi = wilson(ev, len(rows))
            md.append("- %s: %d of %d bookings changed or cancelled in window (%s, 95%% interval %s to %s)."
                      % (label, ev, len(rows), pct(r), pct(lo), pct(hi)))
    md += ["", "This report counts what happened. It does not show why. A person decides what to keep, change or stop."]
    return "\n".join(md) + "\n", csv_rows, summary


def write(md: str, csv_rows: list[dict], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, "report.md")
    csv_path = os.path.join(out_dir, "report.csv")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in csv_rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return md_path, csv_path
