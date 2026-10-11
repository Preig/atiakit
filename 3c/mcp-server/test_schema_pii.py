"""The trip-record schema and the personal-data guard. Standard library only.

    python -m unittest -v          (or: python -m pytest)

If the optional jsonschema package is installed, the schema is also checked with it.
All data here is fictional; the "personal data" below is made up to prove it gets rejected.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_record as vr  # noqa: E402
from inventory import Config, Inventory  # noqa: E402

try:
    import jsonschema  # optional
except ImportError:  # pragma: no cover
    jsonschema = None

SCHEMA = vr.load_schema(HERE / "trip-record.schema.json")
EXAMPLE = json.loads((HERE / "trip-record.example.json").read_text(encoding="utf-8"))
BEFORE_EXPIRY = datetime(2026, 10, 10, 19, 0, tzinfo=timezone.utc)
AFTER_EXPIRY = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def with_change(fn) -> dict:
    rec = copy.deepcopy(EXAMPLE)
    fn(rec)
    return rec


# name -> (mutation, also caught by the JSON Schema on its own?)
PERSONAL = {
    "email field": (lambda r: r.__setitem__("email", "x"), True),
    "guest_name in party": (lambda r: r["party"].__setitem__("guest_name", "x"), True),
    "phone field in a hold": (lambda r: r["holds"][0].__setitem__("phone", "x"), True),
    "card_number at top": (lambda r: r.__setitem__("card_number", "x"), True),
    "email in notes": (lambda r: r.__setitem__("notes", "Send the kit to someone@example.com"), True),
    "phone in a question": (lambda r: r["open_questions"][0].__setitem__("question", "Call the guest at (907) 555-0142 about lunch"), True),
    "phone with dots in a reason": (lambda r: r["shortlisted"][0].__setitem__("reason", "Guest asked by text from 907.555.0199"), True),
    "card number in notes": (lambda r: r.__setitem__("notes", "Deposit on 4111 1111 1111 1111"), True),
    "SSN in an answer": (lambda r: r["open_questions"][3].__setitem__("answer", "ID 123-45-6789"), True),
    "street address in notes": (lambda r: r.__setitem__("notes", "Pick up at 412 Harbor View Drive"), False),
    "label in notes": (lambda r: r.__setitem__("notes", "Name: on file"), False),
    "title and surname in a reason": (lambda r: r["shortlisted"][1].__setitem__("reason", "Mrs. Example prefers dogs to boats"), False),
    "passport key in consent": (lambda r: r["consent"].__setitem__("passport", "x"), True),
}


class SchemaTests(unittest.TestCase):
    def test_example_is_valid(self) -> None:
        res = vr.validate(EXAMPLE, SCHEMA, now=BEFORE_EXPIRY)
        self.assertTrue(res.ok, res.to_dict())
        self.assertEqual(res.warnings, [])

    def test_example_after_expiry_is_still_valid_with_a_warning(self) -> None:
        res = vr.validate(EXAMPLE, SCHEMA, now=AFTER_EXPIRY)
        self.assertTrue(res.ok)
        self.assertTrue(any("has passed" in w.message for w in res.warnings))

    def test_schema_has_no_personal_fields_and_is_closed(self) -> None:
        def walk(node, path="#"):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False, path)
                for k, v in node.get("properties", {}).items():
                    self.assertFalse(vr._personal_key(k), f"{path}/properties/{k} looks personal")
                for k, v in node.items():
                    walk(v, f"{path}/{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}/{i}")
        walk(SCHEMA)
        for field in ("record_id", "version", "updated_at", "party", "dates", "budget_band", "preferences",
                      "shortlisted", "rejected", "holds", "open_questions", "consent"):
            self.assertIn(field, SCHEMA["required"])

    def test_personal_data_is_rejected(self) -> None:
        for name, (mutate, _) in PERSONAL.items():
            with self.subTest(name):
                res = vr.validate(with_change(mutate), SCHEMA, now=BEFORE_EXPIRY)
                self.assertFalse(res.ok, name)
                self.assertTrue(any(e.kind == "personal-data" for e in res.errors), [e.message for e in res.errors])

    def test_health_words_warn_but_do_not_block(self) -> None:
        rec = with_change(lambda r: r["open_questions"].append({"question": "Is the vessel wheelchair accessible?", "for": "owner", "status": "open"}))
        res = vr.validate(rec, SCHEMA, now=BEFORE_EXPIRY)
        self.assertTrue(res.ok)
        self.assertTrue(any("health" in w.message for w in res.warnings))

    def test_record_rules(self) -> None:
        cases = {
            "party count does not add up": lambda r: r["party"].__setitem__("count", 5),
            "depart before arrive": lambda r: r["dates"].__setitem__("depart", "2027-07-13"),
            "agent may confirm": lambda r: r["consent"].__setitem__("agent_may_confirm", True),
            "missing consent": lambda r: r.pop("consent"),
            "no source facts": lambda r: r["shortlisted"][0].__setitem__("source_fact_ids", []),
            "bad hold status": lambda r: r["holds"][0].__setitem__("status", "booked"),
            "impossible date": lambda r: r["dates"].__setitem__("arrive", "2027-02-30"),
            "holds without consent": lambda r: r["consent"].__setitem__("agent_may_place_holds", False),
            "expires before placed": lambda r: r["holds"][1].__setitem__("expires_at", "2026-10-10T18:00:00Z"),
            "unknown age band": lambda r: r["party"]["age_bands"][1].__setitem__("band", "6-9"),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                self.assertFalse(vr.validate(with_change(mutate), SCHEMA, now=BEFORE_EXPIRY).ok, name)

    def test_cli_exit_codes(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            good, bad, broken = tmp / "good.json", tmp / "bad.json", tmp / "broken.json"
            good.write_text(json.dumps(EXAMPLE), encoding="utf-8")
            bad.write_text(json.dumps(with_change(PERSONAL["email in notes"][0])), encoding="utf-8")
            broken.write_text("{ not json", encoding="utf-8")
            schema = str(HERE / "trip-record.schema.json")
            self.assertEqual(vr.main([str(good), "--schema", schema, "--json"]), 0)
            self.assertEqual(vr.main([str(bad), "--schema", schema, "--json"]), 1)
            self.assertEqual(vr.main([str(broken), "--schema", schema]), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipIf(jsonschema is None, "jsonschema not installed (optional cross-check)")
    def test_cross_check_with_jsonschema(self) -> None:
        jsonschema.Draft202012Validator.check_schema(SCHEMA)
        v = jsonschema.Draft202012Validator(SCHEMA)
        self.assertEqual(list(v.iter_errors(EXAMPLE)), [])
        for name, (mutate, schema_alone) in PERSONAL.items():
            if schema_alone:
                with self.subTest(name):
                    self.assertTrue(list(v.iter_errors(with_change(mutate))), f"jsonschema accepted: {name}")


class ServerRejectsPersonalData(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="trip-mcp-pii-"))
        self.inv = Inventory(Config(db_path=str(self.tmp / "t.sqlite3"), log_path=str(self.tmp / "calls.jsonl")))

    def tearDown(self) -> None:
        self.inv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_put_trip_record_saves_nothing_with_personal_data(self) -> None:
        bad = with_change(PERSONAL["phone in a question"][0])
        out = self.inv.put_trip_record("agent:a", bad)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "INVALID_RECORD")
        self.assertTrue(any(e["kind"] == "personal-data" for e in out["errors"]))
        self.assertEqual(self.inv.get_trip_record("agent:a", EXAMPLE["record_id"])["error"], "RECORD_NOT_FOUND")
        log = (self.tmp / "calls.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("555-0142", log)          # the log never copies the record itself

    def test_version_conflict(self) -> None:
        self.assertTrue(self.inv.put_trip_record("agent:a", EXAMPLE)["ok"])
        again = self.inv.put_trip_record("agent:a", EXAMPLE)
        self.assertEqual(again["error"], "VERSION_CONFLICT")
        nxt = dict(copy.deepcopy(EXAMPLE), version=EXAMPLE["version"] + 1)
        self.assertTrue(self.inv.put_trip_record("agent:a", nxt)["ok"])

    def test_confirmation_note_is_scanned(self) -> None:
        h = self.inv.place_hold("agent:a", "BL-CRUISE-4H", "2027-07-15", "09:00", 2)
        out = self.inv.request_confirmation("agent:a", h["hold_id"], note="Guest cell 907-555-0123")
        self.assertEqual(out["error"], "PERSONAL_DATA")
        self.assertEqual(self.inv.get_hold("agent:a", h["hold_id"])["status"], "active")


if __name__ == "__main__":
    unittest.main(verbosity=2)
