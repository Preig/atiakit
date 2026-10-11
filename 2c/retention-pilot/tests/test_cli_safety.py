"""End-to-end run on the mock data, plus safety checks on the bundle itself."""
import contextlib
import csv
import io
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pilot  # noqa: E402
from retention import DRAFT_MARKER  # noqa: E402

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "PROVIDER", "MOCK_"))}


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = pilot.main(list(argv))
    return code, buf.getvalue()


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
class EndToEnd(unittest.TestCase):
    def test_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run("--workdir", tmp, "demo")
            self.assertEqual(code, 0, out)
            self.assertIn("Nothing was sent", out)
            assignments = read_csv(os.path.join(tmp, "state", "assignments.csv"))
            queue = read_csv(os.path.join(tmp, "output", "approval_queue.csv"))
            holdout = {r["booking_id"] for r in assignments if r["arm"] == "holdout"}
            self.assertTrue(holdout)
            self.assertTrue(queue)
            for q in queue:
                self.assertEqual(q["status"], "PENDING")
                self.assertTrue(q["draft_text"].startswith(DRAFT_MARKER))
                self.assertNotIn(q["booking_id"], holdout)
                self.assertEqual(q["approved_by"], "")
            self.assertTrue(os.path.exists(os.path.join(tmp, "output", "report.md")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "output", "report.csv")))

    def test_steps_rerun_keep_arms_and_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run("--workdir", tmp, "score")[0], 0)
            self.assertEqual(run("--workdir", tmp, "assign")[0], 0)
            first = read_csv(os.path.join(tmp, "state", "assignments.csv"))
            self.assertEqual(run("--workdir", tmp, "assign")[0], 0)
            self.assertEqual(first, read_csv(os.path.join(tmp, "state", "assignments.csv")))
            self.assertEqual(run("--workdir", tmp, "draft", "--dry-run")[0], 0)
            q1 = read_csv(os.path.join(tmp, "output", "approval_queue.csv"))
            code, out = run("--workdir", tmp, "draft", "--dry-run")
            q2 = read_csv(os.path.join(tmp, "output", "approval_queue.csv"))
            self.assertEqual(len(q1), len(q2))
            self.assertIn("already in the queue", out)

    def test_model_path_with_mock_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("--workdir", tmp, "score")
            run("--workdir", tmp, "assign")
            code, out = run("--workdir", tmp, "draft", "--provider", "mock", "--max-calls", "5")
            self.assertEqual(code, 0, out)
            queue = read_csv(os.path.join(tmp, "output", "approval_queue.csv"))
            self.assertEqual(len(queue), 5)
            self.assertTrue(all(q["drafted_by"] == "mock:mock-model" for q in queue))
            self.assertIn("over --max-calls", out)

    def test_refusal_leaves_a_pending_row_without_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("--workdir", tmp, "score")
            run("--workdir", tmp, "assign")
            with mock.patch.dict(os.environ, {"MOCK_BEHAVIOR": "refuse"}):
                run("--workdir", tmp, "draft", "--provider", "mock", "--max-calls", "2")
            queue = read_csv(os.path.join(tmp, "output", "approval_queue.csv"))
            self.assertEqual(len(queue), 2)
            for q in queue:
                self.assertEqual(q["status"], "PENDING")
                self.assertEqual(q["draft_text"], "")
                self.assertIn("NO DRAFT", q["checks"])

    def test_failed_drafts_are_retried_on_the_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("--workdir", tmp, "score")
            run("--workdir", tmp, "assign")
            qpath = os.path.join(tmp, "output", "approval_queue.csv")
            with mock.patch.dict(os.environ, {"MOCK_BEHAVIOR": "error"}):
                code, out = run("--workdir", tmp, "draft", "--provider", "mock", "--max-calls", "2")
            self.assertIn("No text came back for 2 draft(s)", out)
            failed = read_csv(qpath)
            self.assertEqual([q["draft_text"] for q in failed], ["", ""])
            code, out = run("--workdir", tmp, "draft", "--provider", "mock", "--max-calls", "2")
            self.assertEqual(code, 0, out)
            self.assertIn("Retrying 2 earlier draft(s)", out)
            queue = read_csv(qpath)
            self.assertEqual(len(queue), 2)
            self.assertEqual({(q["booking_id"], q["message_type"]) for q in queue},
                             {(q["booking_id"], q["message_type"]) for q in failed})
            for q in queue:
                self.assertEqual(q["status"], "PENDING")
                self.assertTrue(q["draft_text"].startswith(DRAFT_MARKER))

    def test_reviewed_rows_are_never_redrafted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("--workdir", tmp, "score")
            run("--workdir", tmp, "assign")
            run("--workdir", tmp, "draft", "--dry-run")
            qpath = os.path.join(tmp, "output", "approval_queue.csv")
            queue = read_csv(qpath)
            queue[0]["status"], queue[0]["draft_text"] = "REJECTED", ""
            with open(qpath, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(queue[0].keys()))
                w.writeheader()
                w.writerows(queue)
            code, out = run("--workdir", tmp, "draft", "--dry-run", "--redraft")
            again = read_csv(qpath)
            self.assertEqual(code, 0, out)
            self.assertEqual(len(again), len(queue))
            rejected = [q for q in again if q["status"] == "REJECTED"]
            self.assertEqual([(q["queue_id"], q["draft_text"]) for q in rejected], [(queue[0]["queue_id"], "")])

    def test_power_command(self):
        code, out = run("power", "--holdout-share", "0.2", "--bookings-per-season", "1500")
        self.assertEqual(code, 0)
        self.assertIn("<- yours", out)
        self.assertIn("1.56x", out)


def bundle_files(exts):
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", "demo_output", "state", "output", "logs")]
        for f in files:
            if f.endswith(exts) or f == ".env.example":
                yield os.path.join(base, f)


class BundleSafety(unittest.TestCase):
    def test_no_sending_code(self):
        forbidden = re.compile(r"smtplib|email\.mime|twilio|sendgrid|mailgun|requests\.post|urlopen|http\.client|"
                               r"import socket|def send|\.send\(")
        for path in bundle_files((".py",)):
            if os.sep + "tests" + os.sep in path:
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIsNone(forbidden.search(text), "%s contains sending code" % path)

    def test_no_em_or_en_dashes(self):
        for path in bundle_files((".py", ".md", ".csv", ".json", ".txt")):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn(chr(0x2014), text, path)
            self.assertNotIn(chr(0x2013), text, path)

    def test_mock_data_has_no_personal_columns(self):
        with open(os.path.join(ROOT, "data", "baylight-bookings-mock.csv"), encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
        self.assertEqual(len(read_csv(os.path.join(ROOT, "data", "baylight-bookings-mock.csv"))), 300)
        for col in header:
            self.assertNotRegex(col, "name|email|phone|card|address|payment")


if __name__ == "__main__":
    unittest.main()
