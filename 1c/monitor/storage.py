"""Append-only files the monitor writes.

results.csv   one row per answer per watched name (columns below, never reordered)
answers.jsonl one line per answer: prompt, model, citations, usage, cost and, where
              allowed by STORE_FULL_TEXT_<PROVIDER>, the full answer text
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RESULT_COLUMNS = [
    "run_id", "date", "provider", "model", "tool_version", "user_location", "prompt_id", "name",
    "appears", "first_offset", "rank_among_watched", "mention_count", "cited", "cited_urls",
    "input_tokens", "output_tokens", "search_calls", "cost_usd_measured", "error",
]


class SchemaMismatch(RuntimeError):
    pass


def append_results(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        if header != RESULT_COLUMNS:
            raise SchemaMismatch(f"{path} has different columns. Move it aside and run again.")
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in RESULT_COLUMNS})


def read_results(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_answer(path: str | Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_answers(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
