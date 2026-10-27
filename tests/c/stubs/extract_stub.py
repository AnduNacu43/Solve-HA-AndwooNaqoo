"""Stub of A's arena.pages.load_universe and arena.extract.extract.

load_universe groups rows into pages (maximal runs of consecutive ids sharing
a date); extract finds nothing, so the run falls back to the seed timelines."""
from __future__ import annotations

import csv

from arena.model import Observation, Page, Row


def load_universe(path: str) -> list[Page]:
    pages: list[Page] = []
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not pages or pages[-1].date != row["date"]:
                pages.append(Page(f"u-{len(pages) + 1:05d}", row["date"], []))
            pages[-1].rows.append(Row(row["id"], row["text"]))
    return pages


def extract(pages: list[Page], lexicon, attrs: dict) -> list[Observation]:
    return []
