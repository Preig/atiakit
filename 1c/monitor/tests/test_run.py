"""End to end in mock mode (no keys, no network), the weekly diff, costs and the budget stop."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._util import HERE, clean_env, no_network, quiet
import monitor
import providers
from costs import answer_cost, budget_from_env, estimate_next_call
from providers.common import Answer
from report import build_diff
from storage import RESULT_COLUMNS

PRICES = dict(ANTHROPIC_PRICE_INPUT_PER_MTOK="4", ANTHROPIC_PRICE_OUTPUT_PER_MTOK="20",
              ANTHROPIC_PRICE_PER_1K_SEARCHES="10")


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


class MockRunEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, **env):
        with clean_env(**{**PRICES, **env}), no_network(), quiet() as buf:
            code = monitor.main(list(args))
        return code, buf.getvalue()

    def test_full_mock_run(self):
        code, out = self.run_cli("run", "--mock", "--out", self.out)
        self.assertEqual(code, 0, out)
        rows = read_csv(Path(self.out) / "results.csv")
        with open(Path(self.out) / "results.csv", newline="", encoding="utf-8") as f:
            self.assertEqual(next(csv.reader(f)), RESULT_COLUMNS)
        prompts = monitor.load_prompts(HERE / "prompts.csv")
        names = monitor.load_names(HERE / "names.csv")
        self.assertEqual(len(rows), len(prompts) * 3 * len(names))
        answers = read_jsonl(Path(self.out) / "answers.jsonl")
        self.assertEqual(len(answers), len(prompts) * 3)
        self.assertTrue(all(a["mode"] == "mock" and a["run_id"].endswith("-mock") for a in answers))

        bay = [r for r in rows if r["provider"] == "anthropic" and r["prompt_id"] == "P02"
               and r["name"] == "Bay Light Day Cruises"][0]
        self.assertEqual((bay["appears"], bay["cited"], bay["rank_among_watched"]), ("1", "1", "2"))
        self.assertIn("baylight.example", bay["cited_urls"])
        # OpenAI named it but cited a listing site, not its own domain
        oa = [r for r in rows if r["provider"] == "openai" and r["prompt_id"] == "P02"
              and r["name"] == "Bay Light Day Cruises"][0]
        self.assertEqual((oa["appears"], oa["cited"]), ("1", "0"))
        # Gemini redirect citations are matched on their domain-like titles
        gm = [r for r in rows if r["provider"] == "gemini" and r["prompt_id"] == "P02"
              and r["name"] == "Bay Light Day Cruises"][0]
        self.assertEqual(gm["cited"], "1")

        # Usage and cost once per answer, on the first name row only
        first = [r for r in rows if r["provider"] == "anthropic" and r["prompt_id"] == "P02"]
        self.assertTrue(first[0]["cost_usd_measured"])
        self.assertTrue(all(r["cost_usd_measured"] == "" for r in first[1:]))
        expected = (18200 * 4 + 1420 * 20) / 1e6 + 2 * 10 / 1000
        self.assertAlmostEqual(float(first[0]["cost_usd_measured"]), expected, places=6)
        # OpenAI prices are not set in this test, so its cost is blank rather than guessed
        self.assertEqual(oa["cost_usd_measured"], "")

        # Full text stored for Claude and OpenAI by default, not for Gemini
        by_p = {a["provider"]: a for a in answers if a["prompt_id"] == "P02"}
        self.assertTrue(by_p["anthropic"]["text"])
        self.assertIsNone(by_p["gemini"]["text"])
        self.assertFalse(by_p["gemini"]["text_stored"])
        self.assertTrue(by_p["gemini"]["citations"])
        self.assertIn("Nothing was spent", out)

    def test_dry_run_uses_two_prompts(self):
        code, _ = self.run_cli("run", "--mock", "--dry-run", "--out", self.out)
        self.assertEqual(code, 0)
        answers = read_jsonl(Path(self.out) / "answers.jsonl")
        self.assertEqual(sorted({a["prompt_id"] for a in answers}), ["P01", "P02"])
        self.assertEqual(len(answers), 6)

    def test_store_full_text_flag(self):
        self.run_cli("run", "--mock", "--limit", "2", "--out", self.out, STORE_FULL_TEXT_ANTHROPIC="0")
        answers = read_jsonl(Path(self.out) / "answers.jsonl")
        self.assertTrue(all(a["text"] is None for a in answers if a["provider"] == "anthropic"))

    def test_two_weeks_then_diff(self):
        self.run_cli("run", "--mock", "--out", self.out)
        self.run_cli("run", "--mock", "--fixtures", str(HERE / "fixtures" / "week2"), "--out", self.out)
        code, out = self.run_cli("diff", "--out", self.out)
        self.assertEqual(code, 0)
        md = (Path(self.out) / "weekly_diff.md").read_text(encoding="utf-8")
        self.assertIn("DRAFT - PENDING OWNER REVIEW", md)
        self.assertIn("One week is noise", md)
        self.assertIn("proxy panel", md)
        gained = md.split("## Gained mentions")[1].split("## Lost mentions")[0]
        lost = md.split("## Lost mentions")[1].split("## Sources cited")[0]
        self.assertIn("Bay Light Day Cruises: openai, prompt P03", gained)
        self.assertIn("Bay Light Day Cruises: openai, prompt P16", gained)
        self.assertIn("Bay Light Day Cruises: anthropic, prompt P03", lost)
        self.assertIn("Bay Light Day Cruises: gemini, prompt P02", lost)
        new_sources = md.split("## Sources cited for the first time")[1].split("##")[0]
        self.assertIn("visitfairbanks.example", new_sources)
        self.assertIn("travelblog.example", new_sources)
        self.assertNotIn("baylight.example", new_sources)
        self.assertIn("## Quarterly trend", md)
        self.assertIn("(2 runs)", md)

    def test_runs_in_the_same_second_get_distinct_ids(self):
        fixed = monitor.utc_now()
        with mock.patch.object(monitor, "utc_now", lambda: fixed):
            self.run_cli("run", "--mock", "--limit", "1", "--out", self.out)
            self.run_cli("run", "--mock", "--limit", "1", "--out", self.out)
        ids = {a["run_id"] for a in read_jsonl(Path(self.out) / "answers.jsonl")}
        self.assertEqual(len(ids), 2)

    def test_diff_with_one_run(self):
        self.run_cli("run", "--mock", "--limit", "3", "--out", self.out)
        self.run_cli("diff", "--out", self.out)
        md = (Path(self.out) / "weekly_diff.md").read_text(encoding="utf-8")
        self.assertIn("Previous run: none yet", md)
        self.assertIn("First run", md)

    def test_cost_report(self):
        self.run_cli("run", "--mock", "--limit", "2", "--out", self.out)
        code, _ = self.run_cli("cost", "--out", self.out)
        self.assertEqual(code, 0)
        md = (Path(self.out) / "cost_report.md").read_text(encoding="utf-8")
        self.assertIn("(not spent)", md)
        self.assertIn("n/a (price not set)", md)
        self.assertIn("OPENAI_PRICE_INPUT_PER_MTOK", md)

    def test_check_mock_parses_all_fixtures(self):
        code, out = self.run_cli("check", "--mock")
        self.assertEqual(code, 0, out)


class FakeLive:
    """Stands in for a provider module in live mode. Counts calls; never touches the network."""
    NAME = "anthropic"
    KEY_ENV = "ANTHROPIC_API_KEY"

    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def config(self):
        return {}

    def ask(self, prompt, cfg):
        self.calls += 1
        a = Answer(provider="anthropic", model="fake", tool_version="t", user_location="US",
                   text="Bay Light Day Cruises is an option.", input_tokens=10000, output_tokens=1000,
                   search_calls=2)
        a.add_citation("https://baylight.example/")
        return a


class BudgetAndCosts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_live_run_with_fake_provider_records_measured_cost(self):
        fake = FakeLive()
        with clean_env(**PRICES, ANTHROPIC_API_KEY="x"), no_network(), quiet(), \
                mock.patch.dict(providers.REGISTRY, {"anthropic": fake}):
            code = monitor.main(["run", "--providers", "anthropic", "--limit", "3", "--out", str(self.out)])
        self.assertEqual(code, 0)
        self.assertEqual(fake.calls, 3)
        answers = read_jsonl(self.out / "answers.jsonl")
        self.assertEqual({a["mode"] for a in answers}, {"live"})
        self.assertAlmostEqual(answers[0]["cost_usd_measured"], 0.04 + 0.02 + 0.02, places=6)

    def test_budget_stop_before_overspending(self):
        month = monitor.utc_now().strftime("%Y-%m-%d")
        prior = {"run_id": "old", "date": month, "mode": "live", "provider": "anthropic",
                 "prompt_id": "P01", "cost_usd_measured": 24.95, "search_calls": 0}
        (self.out / "answers.jsonl").write_text(json.dumps(prior) + "\n", encoding="utf-8")
        fake = FakeLive()
        with clean_env(**PRICES, ANTHROPIC_API_KEY="x", MONTHLY_BUDGET="25", EST_COST_PER_ANSWER="0.10"), \
                no_network(), quiet() as buf, mock.patch.dict(providers.REGISTRY, {"anthropic": fake}):
            code = monitor.main(["run", "--providers", "anthropic", "--out", str(self.out)])
        self.assertEqual(code, 3)
        self.assertEqual(fake.calls, 0)
        self.assertIn("BUDGET STOP", buf.getvalue())

    def test_budget_counts_spend_within_the_run(self):
        fake = FakeLive()   # each answer costs $0.08 at the test prices
        with clean_env(**PRICES, ANTHROPIC_API_KEY="x", MONTHLY_BUDGET="0.20", EST_COST_PER_ANSWER="0.01"), \
                no_network(), quiet(), mock.patch.dict(providers.REGISTRY, {"anthropic": fake}):
            code = monitor.main(["run", "--providers", "anthropic", "--out", str(self.out)])
        self.assertEqual(code, 3)
        self.assertEqual(fake.calls, 2)    # 0.08 + 0.08 = 0.16; a third would pass 0.20

    def test_unpriced_provider_is_skipped_while_budget_is_on(self):
        fake = FakeLive()
        with clean_env(ANTHROPIC_API_KEY="x"), no_network(), quiet() as buf, \
                mock.patch.dict(providers.REGISTRY, {"anthropic": fake}):
            code = monitor.main(["run", "--providers", "anthropic", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertEqual(fake.calls, 0)
        self.assertIn("prices not set", buf.getvalue())

    def test_missing_key_is_skipped(self):
        with clean_env(**PRICES), no_network(), quiet() as buf:
            code = monitor.main(["run", "--providers", "anthropic", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertIn("no API key", buf.getvalue())

    def test_gemini_free_allowance_and_missing_prices(self):
        with clean_env(GEMINI_PRICE_INPUT_PER_MTOK="0", GEMINI_PRICE_OUTPUT_PER_MTOK="0",
                       GEMINI_PRICE_PER_1K_SEARCHES="14"):
            cost, billable = answer_cost("gemini", 0, 0, 10, free_searches_left=4)
            self.assertEqual(billable, 6)
            self.assertAlmostEqual(cost, 6 * 14 / 1000)
            self.assertEqual(answer_cost("gemini", 0, 0, 3, free_searches_left=4), (0.0, 0))
        with clean_env():
            self.assertEqual(answer_cost("openai", 100, 100, 1), (None, 1))

    def test_budget_setting(self):
        with clean_env():
            self.assertEqual(budget_from_env(), 25.0)
        with clean_env(MONTHLY_BUDGET="none"):
            self.assertIsNone(budget_from_env())

    def test_estimate_uses_measured_average(self):
        answers = [{"provider": "anthropic", "mode": "live", "cost_usd_measured": c} for c in (0.1, 0.3)]
        self.assertAlmostEqual(estimate_next_call(answers, "anthropic", 9.9), 0.2)
        self.assertEqual(estimate_next_call(answers, "openai", 9.9), 9.9)


class DiffRules(unittest.TestCase):
    def test_dry_runs_and_errors_are_excluded(self):
        answers = [
            {"run_id": "r1", "date": "2026-07-01", "mode": "live", "provider": "p", "prompt_id": "A", "citations": []},
            {"run_id": "r2", "date": "2026-07-08", "mode": "dry", "provider": "p", "prompt_id": "A", "citations": []},
            {"run_id": "r3", "date": "2026-10-08", "mode": "live", "provider": "p", "prompt_id": "A", "citations": []},
            {"run_id": "r3", "date": "2026-10-08", "mode": "live", "provider": "p", "prompt_id": "B",
             "citations": [], "error": "rate_limited_after_retries"},
        ]
        results = [
            {"run_id": "r1", "provider": "p", "prompt_id": "A", "name": "N", "appears": "0", "cited": "0"},
            {"run_id": "r2", "provider": "p", "prompt_id": "A", "name": "N", "appears": "1", "cited": "0"},
            {"run_id": "r3", "provider": "p", "prompt_id": "A", "name": "N", "appears": "1", "cited": "1"},
            {"run_id": "r3", "provider": "p", "prompt_id": "B", "name": "N", "appears": "", "cited": ""},
        ]
        md = build_diff(results, answers)
        self.assertIn("`r3`", md)
        self.assertIn("Previous run: `r1`", md)          # the dry run r2 is skipped
        self.assertIn("| N | 1 of 1 (100%) | 0 of 1 (0%) |", md)   # errored answer not in the denominator
        self.assertIn("N: p, prompt A", md.split("## Gained")[1].split("## Lost")[0])
        self.assertIn("2026-Q3", md)
        self.assertIn("2026-Q4", md)
        self.assertIn("## Errors this run", md)


if __name__ == "__main__":
    unittest.main()
