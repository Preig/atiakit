#!/usr/bin/env python3
"""Post-booking retention pilot (ATIA 2026 kit, tool 2.c). Teaching code. Python 3.10+, standard library.

Commands (run them in this order the first time):
  python pilot.py demo                 run everything on the fictional data, no keys, no network
  python pilot.py score                score open bookings with rules.json, mark the top share eligible
  python pilot.py assign               put eligible bookings in treatment or holdout, stored once
  python pilot.py draft --dry-run      fill the A/B/C templates for treatment bookings, no API call
  python pilot.py draft                same, but a model API improves the wording (PROVIDER in .env)
  python pilot.py report               treatment versus holdout, with Wilson 95% intervals
  python pilot.py power                how many bookings a clear answer needs

Nothing here sends a message. Drafts go to output/approval_queue.csv with status PENDING,
and a person approves and sends them from the booking platform.
Bay Light Day Cruises, Seward is a FICTIONAL TEACHING BUSINESS.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from adapters.csv_adapter import AdapterError, load_bookings, load_outcomes  # noqa: E402
from retention import DRAFT_MARKER  # noqa: E402
from retention import assign as assign_mod  # noqa: E402
from retention import drafting, report, stats  # noqa: E402
from retention.envfile import load_env  # noqa: E402
from retention.rules import RulesError, load_rules, score_all  # noqa: E402

DEFAULT_BOOKINGS = os.path.join(HERE, "data", "baylight-bookings-mock.csv")
DEFAULT_OUTCOMES = os.path.join(HERE, "data", "baylight-outcomes-mock.csv")
SCORE_FIELDS = [
    "booking_id", "score", "eligible", "rules_hit", "lead_time_days", "rate_type", "channel",
    "booked_date", "trip_date", "departure_time", "party_size", "addons_count", "price_alert_flag",
    "booking_value_usd",
]


def say(msg: str = "") -> None:
    print(msg)


def paths(args) -> dict:
    base = os.path.abspath(args.workdir) if args.workdir else HERE
    return {
        "state": os.path.join(base, "state"),
        "out": os.path.join(base, "output"),
        "logs": os.path.join(base, "logs"),
        "scores": os.path.join(base, "state", "scores.csv"),
        "assignments": os.path.join(base, "state", "assignments.csv"),
        "queue": os.path.join(base, "output", "approval_queue.csv"),
    }


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, dt.date):
        return v.isoformat()
    return str(v)


# ------------------------------------------------------------------ score

def cmd_score(args, rules) -> int:
    p = paths(args)
    try:
        rows, log = load_bookings(args.bookings, p["logs"])
    except AdapterError as exc:
        say("Could not load bookings: %s" % exc)
        return 2
    say("Loaded %d bookings from %s" % (len(rows), os.path.basename(args.bookings)))
    for line in log.lines:
        say("  adapter: %s" % line)
    if log.lines:
        say("  (logged in %s)" % os.path.join(p["logs"], "adapter-log.txt"))
    scored, info = score_all(rows, rules)
    os.makedirs(p["state"], exist_ok=True)
    with open(p["scores"], "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in scored:
            w.writerow({k: _cell(r.get(k)) for k in SCORE_FIELDS})
    dist: dict = {}
    for r in scored:
        dist[r["score"]] = dist.get(r["score"], 0) + 1
    say("Open bookings scored: %d (skipped by status: %d)" % (info["open"], info["skipped_status"]))
    say("Score counts: " + ", ".join("%d pts: %d" % (k, dist[k]) for k in sorted(dist, reverse=True)))
    say("Eligible (top %d%%): %d bookings, cutoff score %s"
        % (round(100 * rules["eligibility"]["top_share"]), info["eligible"], info["cutoff_score"]))
    if info["tied_at_cutoff_not_selected"]:
        say("  %d more bookings had the cutoff score; ties went to the longest lead time, then booking_id."
            % info["tied_at_cutoff_not_selected"])
    say("Wrote %s" % p["scores"])
    return 0


# ------------------------------------------------------------------ assign

def cmd_assign(args, rules) -> int:
    p = paths(args)
    if not os.path.exists(p["scores"]):
        say("Run 'python pilot.py score' first.")
        return 2
    with open(p["scores"], newline="", encoding="utf-8") as fh:
        eligible = [r for r in csv.DictReader(fh) if r.get("eligible") == "1"]
    seed, share = rules["holdout"]["seed"], float(rules["holdout"]["share"])
    new, kept, warnings = assign_mod.assign(eligible, p["assignments"], seed, share)
    for w in warnings:
        say("Note: %s" % w)
    allrows = assign_mod.read_assignments(p["assignments"])
    t = sum(1 for r in allrows if r["arm"] == "treatment")
    h = sum(1 for r in allrows if r["arm"] == "holdout")
    say("Eligible bookings in this run: %d. Newly assigned: %d. Already assigned (kept their arm): %d."
        % (len(eligible), len(new), kept))
    say("All assignments so far: %d treatment, %d holdout (target holdout share %s, seed '%s')."
        % (t, h, share, seed))
    say("Wrote %s. Do not edit or redraw it during the pilot." % p["assignments"])
    return 0


# ------------------------------------------------------------------ draft

def cmd_draft(args, rules) -> int:
    p = paths(args)
    if not os.path.exists(p["assignments"]):
        say("Run 'python pilot.py score' and 'python pilot.py assign' first.")
        return 2
    facts, facts_text = drafting.load_facts(args.facts)
    addons = drafting.load_addons(args.addons)
    terms = (rules["messages"].get("lockin_terms") or "").strip()
    max_words = int(rules["messages"].get("max_words", 160))
    provider = None
    if not args.dry_run:
        from providers import get_provider
        try:
            provider = get_provider(args.provider)
        except (ImportError, ValueError) as exc:
            say("Could not start the model provider: %s" % exc)
            say("Use --dry-run for template-only drafts, or install the SDK named in requirements.txt.")
            return 2
    queue = drafting.read_queue(p["queue"])
    if args.redraft:
        queue = [q for q in queue if q.get("status") != "PENDING"]
    else:
        # A PENDING row with no text is a draft that failed earlier (refused, cut off, error).
        # Retry it; rows a person has reviewed, or filled in by hand, are kept as they are.
        retry = [q for q in queue if q.get("status") == "PENDING" and not (q.get("draft_text") or "").strip()]
        if retry:
            queue = [q for q in queue if q.get("status") != "PENDING" or (q.get("draft_text") or "").strip()]
            say("Retrying %d earlier draft(s) that came back with no text." % len(retry))
    have = {(q["booking_id"], q["message_type"]) for q in queue}
    next_id = 1 + max([int(q["queue_id"].split("-")[-1]) for q in queue if q.get("queue_id", "").startswith("Q-")] or [0])
    assignments = assign_mod.read_assignments(p["assignments"])
    treatment = [r for r in assignments if r["arm"] == "treatment"]
    holdout = len(assignments) - len(treatment)
    made: dict = {}
    failed = 0
    skipped: dict = {}
    calls, call_cap = 0, (args.max_calls if provider else None)
    today = dt.date.today().isoformat()
    template_raw = {k: drafting.load_template(os.path.join(args.templates, f))[2]
                    for k, f in drafting.TEMPLATE_FILES.items()}
    for row in treatment:
        b = drafting.typed_booking(row)
        ctx = drafting.booking_context(b)
        for plan in drafting.plan_messages(b, rules, addons):
            mtype = plan["type"]
            if plan.get("skip"):
                skipped[plan["skip"]] = skipped.get(plan["skip"], 0) + 1
                continue
            if (b["booking_id"], mtype) in have:
                skipped["already in the queue"] = skipped.get("already in the queue", 0) + 1
                continue
            addon = plan.get("addon")
            subject, text = drafting.dry_run_draft(mtype, args.templates, facts, ctx, addon,
                                                   terms if mtype == "C" else "")
            drafted_by = "template (dry run)"
            extra_flags = []
            if provider is not None:
                if call_cap is not None and calls >= call_cap:
                    skipped["over --max-calls for this run"] = skipped.get("over --max-calls for this run", 0) + 1
                    continue
                system, user = drafting.model_prompt(mtype, facts_text, text, ctx, addon,
                                                     terms if mtype == "C" else "", max_words)
                calls += 1
                res = provider.draft(system, user)
                drafted_by = res.model
                if res.ok:
                    subject, text, marker_added = drafting.split_model_text(res.text, subject)
                    if marker_added:
                        extra_flags.append("DRAFT marker added by the code")
                else:
                    text = ""
                    extra_flags.append("NO DRAFT (%s: %s). Write this one by hand, or run draft again to retry it."
                                       % (res.status, res.detail))
            allowed = "\n".join([facts_text, template_raw[mtype], terms if mtype == "C" else "",
                                 "\n".join(str(v) for v in (addon or {}).values()),
                                 "\n".join(str(v) for v in ctx.values())])
            flags = extra_flags + (drafting.check_draft(text, allowed, rules, max_words) if text else [])
            queue.append({
                "queue_id": "Q-%04d" % next_id,
                "created_on": today,
                "booking_id": b["booking_id"],
                "arm": "treatment",
                "message_type": mtype,
                "message_name": drafting.MESSAGE_INFO[mtype][0],
                "suggested_send_date": plan["send_date"].isoformat(),
                "trip_date": ctx["trip_date"],
                "subject": subject,
                "draft_text": text,
                "drafted_by": drafted_by,
                "checks": "; ".join(flags) if flags else "no flags (a person still reviews it)",
                "status": "PENDING",
                "approved_by": "",
                "approved_on": "",
                "reviewer_notes": "",
            })
            have.add((b["booking_id"], mtype))
            next_id += 1
            if text:
                made[mtype] = made.get(mtype, 0) + 1
            else:
                failed += 1
    drafting.write_queue(p["queue"], queue)
    say("Treatment bookings: %d. Holdout bookings: %d (they get no pilot messages)." % (len(treatment), holdout))
    say("Drafted: " + (", ".join("%s %s: %d" % (k, drafting.MESSAGE_INFO[k][0], made[k]) for k in sorted(made)) or "none"))
    if failed:
        say("No text came back for %d draft(s). They are in the queue marked NO DRAFT; run draft again to retry them."
            % failed)
    if provider is not None:
        say("Model calls this run: %d (%s)" % (calls, getattr(provider, "model", "")))
    for reason, n in sorted(skipped.items(), key=lambda kv: -kv[1]):
        say("  not drafted, %s: %d" % (reason, n))
    say("Wrote %s. Every row is PENDING, and every draft starts with '%s'." % (p["queue"], DRAFT_MARKER))
    say("Nothing was sent. A person reviews each row, sets status to APPROVED or REJECTED,")
    say("and sends approved messages from the booking platform.")
    return 0


# ------------------------------------------------------------------ report

def cmd_report(args, rules) -> int:
    p = paths(args)
    if not os.path.exists(p["assignments"]):
        say("Run score and assign first: the report compares the stored assignments.")
        return 2
    try:
        outcomes, log = load_outcomes(args.outcomes, p["logs"])
    except AdapterError as exc:
        say("Could not load outcomes: %s" % exc)
        return 2
    for line in log.lines:
        say("  adapter: %s" % line)
    all_bookings = None
    if args.bookings and os.path.exists(args.bookings):
        all_bookings, _ = load_bookings(args.bookings, None)
    assignments = assign_mod.read_assignments(p["assignments"])
    queue = drafting.read_queue(p["queue"]) if os.path.exists(p["queue"]) else None
    fictional = os.path.basename(args.outcomes).startswith("baylight-")
    md, rows, summary = report.build(assignments, outcomes, rules, queue, all_bookings, fictional)
    md_path, csv_path = report.write(md, rows, p["out"])
    for seg, s in summary.items():
        t, h = s["treatment"], s["holdout"]
        say("%s: treatment %s (n=%d), holdout %s (n=%d). Read: %s"
            % (seg, report.pct(t["rate"]), t["n"], report.pct(h["rate"]), h["n"], s["read"]))
    say("Wrote %s and %s" % (md_path, csv_path))
    return 0


# ------------------------------------------------------------------ power

def power_text(baseline, target, share, alpha, power, bookings=None, eligible_share=None, operators=1) -> str:
    out = []
    out.append("Sample size: two-proportion test, alpha %s (two-sided), power %s" % (alpha, power))
    out.append("Holdout rate %.1f%% (no messages)  vs  treatment rate %.1f%% (with messages)"
               % (100 * baseline, 100 * target))
    out.append("")
    out.append("%-26s %9s %10s %9s %9s" % ("Split (treatment/holdout)", "Holdout", "Treatment", "Total", "vs 50/50"))
    shares = [0.5, 0.3, 0.2]
    if share not in shares:
        shares.append(share)
    for r in stats.split_table(baseline, target, shares, alpha, power):
        mark = "  <- yours" if abs(r["holdout_share"] - share) < 1e-9 else ""
        out.append("%-26s %9s %10s %9s %8.2fx%s" % (
            "%d/%d" % (round(100 * (1 - r["holdout_share"])), round(100 * r["holdout_share"])),
            format(r["holdout"], ","), format(r["treatment"], ","), format(r["total"], ","), r["vs_5050"], mark))
    mine = stats.required_sample(baseline, target, share, alpha, power)
    out.append("")
    show = share if abs(share - 0.5) > 1e-9 else 0.2
    exact = stats.required_sample(baseline, target, show, alpha, power)["total"] / stats.required_sample(
        baseline, target, 0.5, alpha, power)["total"]
    label = "%d/%d" % (round(100 * (1 - show)), round(100 * show))
    article = "an" if label.startswith(("8", "11", "18")) else "a"
    out.append("Rule of thumb: %s %s split needs about 1 / (4 x %.2f x %.2f) = %.2fx the bookings of 50/50."
               % (article, label, 1 - show, show, 1 / (4 * show * (1 - show))))
    out.append("The exact figure in the table is %.2fx. Either way: for a pilot, 50/50 gets an answer soonest." % exact)
    if bookings and eligible_share:
        eligible = bookings * eligible_share
        out.append("")
        out.append("Your season: %s bookings x %d%% eligible = %s eligible bookings per operator"
                   % (format(bookings, ","), round(100 * eligible_share), format(round(eligible), ",")))
        pooled = eligible * max(1, operators)
        seasons = mine["total"] / pooled if pooled else float("inf")
        needed_ops = int(-(-mine["total"] // max(1, eligible)))
        if operators > 1:
            out.append("Pooled across %d operators running the same design: %s eligible bookings per season."
                       % (operators, format(round(pooled), ",")))
        out.append("At your split you would need about %.1f season(s) of data. Operators needed to finish in one season: about %d."
                   % (seasons, needed_ops))
        if seasons > 1:
            out.append("Verdict: DIRECTIONAL READ ONLY. Worth having; not evidence to scale on.")
            out.append("To get a firmer answer: use 50/50, run across seasons, or pool the same design through ATIA.")
        else:
            out.append("Verdict: one season can reach the sample size. Still read the intervals.")
    return "\n".join(out)


def cmd_power(args, rules) -> int:
    pw = rules["power"]
    baseline = args.baseline if args.baseline is not None else pw["baseline_rate"]
    target = args.target if args.target is not None else pw["target_rate"]
    share = args.holdout_share if args.holdout_share is not None else float(rules["holdout"]["share"])
    alpha = args.alpha if args.alpha is not None else pw.get("alpha", 0.05)
    power = args.power if args.power is not None else pw.get("power", 0.8)
    for name, v in (("baseline", baseline), ("target", target)):
        if v > 1:
            say("Give %s as a share, for example 0.15 for 15%%." % name)
            return 2
    try:
        say(power_text(baseline, target, share, alpha, power, args.bookings_per_season,
                       args.eligible_share if args.eligible_share is not None else rules["eligibility"]["top_share"],
                       args.operators))
    except ValueError as exc:
        say("Cannot compute: %s" % exc)
        return 2
    return 0


# ------------------------------------------------------------------ demo

def cmd_demo(args, rules) -> int:
    workdir = os.path.abspath(args.workdir or os.path.join(HERE, "demo_output"))
    for sub in ("state", "output"):
        for name in ("scores.csv", "assignments.csv", "approval_queue.csv", "report.md", "report.csv"):
            f = os.path.join(workdir, sub, name)
            if os.path.exists(f):
                os.remove(f)
    ns = argparse.Namespace(**vars(args))
    ns.workdir = workdir
    say("== DEMO on fictional data (Bay Light Day Cruises, Seward). Output folder: %s" % workdir)
    say("")
    say("== 1. score")
    ns.bookings = DEFAULT_BOOKINGS
    if cmd_score(ns, rules):
        return 2
    say("")
    say("== 2. assign")
    cmd_assign(ns, rules)
    say("")
    say("== 3. draft --dry-run (templates only, no API)")
    ns.dry_run, ns.redraft, ns.provider, ns.max_calls = True, False, None, 0
    ns.facts = os.path.join(HERE, "approved_facts.md")
    ns.addons = os.path.join(HERE, "approved_addons.csv")
    ns.templates = os.path.join(HERE, "templates")
    cmd_draft(ns, rules)
    say("")
    say("== 4. report (simulated end-of-season outcomes)")
    ns.outcomes = DEFAULT_OUTCOMES
    ns.bookings = DEFAULT_BOOKINGS
    cmd_report(ns, rules)
    say("")
    say("== 5. power (for a 1,500-booking season)")
    ns.baseline = ns.target = ns.holdout_share = ns.alpha = ns.power = None
    ns.bookings_per_season, ns.eligible_share, ns.operators = 1500, None, 1
    cmd_power(ns, rules)
    say("")
    say("Open %s in a spreadsheet to see the drafts, and %s for the report."
        % (os.path.join(workdir, "output", "approval_queue.csv"), os.path.join(workdir, "output", "report.md")))
    return 0


# ------------------------------------------------------------------ main

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pilot.py",
        description="Post-booking retention pilot (teaching code). Nothing here sends a message.",
    )
    ap.add_argument("--rules", default=os.path.join(HERE, "rules.json"), help="rules file (default: rules.json)")
    ap.add_argument("--workdir", default=None, help="folder for state/, output/ and logs/ (default: this folder)")
    sub = ap.add_subparsers(dest="command", required=True)

    s = sub.add_parser("score", help="score open bookings and mark the top share eligible")
    s.add_argument("--bookings", default=DEFAULT_BOOKINGS, help="booking export CSV (default: the fictional mock)")

    sub.add_parser("assign", help="assign eligible bookings to treatment or holdout, once")

    d = sub.add_parser("draft", help="draft messages for treatment bookings into the approval queue")
    d.add_argument("--dry-run", action="store_true", help="fill templates only, no API call, no key needed")
    d.add_argument("--provider", default=None, help="mock, anthropic, openai or gemini (default: PROVIDER in .env, else mock)")
    d.add_argument("--max-calls", type=int, default=25, help="cost cap: model calls per run (default 25)")
    d.add_argument("--redraft", action="store_true", help="replace PENDING drafts; reviewed rows are kept")
    d.add_argument("--facts", default=os.path.join(HERE, "approved_facts.md"))
    d.add_argument("--addons", default=os.path.join(HERE, "approved_addons.csv"))
    d.add_argument("--templates", default=os.path.join(HERE, "templates"))

    r = sub.add_parser("report", help="treatment versus holdout, with Wilson 95%% intervals")
    r.add_argument("--outcomes", default=DEFAULT_OUTCOMES, help="outcomes CSV: booking_id, outcome, outcome_date")
    r.add_argument("--bookings", default=DEFAULT_BOOKINGS, help="optional: all bookings, for the context line")

    pw = sub.add_parser("power", help="bookings needed for a clear answer")
    pw.add_argument("--baseline", type=float, default=None, help="holdout rate as a share, for example 0.15")
    pw.add_argument("--target", type=float, default=None, help="hoped-for treatment rate, for example 0.12")
    pw.add_argument("--holdout-share", type=float, default=None, help="for example 0.5 or 0.2")
    pw.add_argument("--alpha", type=float, default=None)
    pw.add_argument("--power", type=float, default=None)
    pw.add_argument("--bookings-per-season", type=int, default=None, help="for example 1500")
    pw.add_argument("--eligible-share", type=float, default=None, help="share of bookings eligible, for example 0.10")
    pw.add_argument("--operators", type=int, default=1, help="operators pooling the same design")

    sub.add_parser("demo", help="run every step on the fictional data (dry run, no keys)")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    load_env(os.path.join(HERE, ".env"))
    try:
        rules = load_rules(args.rules)
    except RulesError as exc:
        say(str(exc))
        return 2
    handler = {
        "score": cmd_score, "assign": cmd_assign, "draft": cmd_draft,
        "report": cmd_report, "power": cmd_power, "demo": cmd_demo,
    }[args.command]
    return handler(args, rules)


if __name__ == "__main__":
    sys.exit(main())
