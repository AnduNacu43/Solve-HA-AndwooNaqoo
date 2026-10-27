"""Stand-in for A's arena.extract.extract (plans/00-shared.md §3).

extract(pages, lexicon, attrs) -> list[Observation]. Instead of parsing text
it reads the practice forms, which is what A's extractor approximates; the
labels are hidden by default, as they would be for universe rows.
"""
from __future__ import annotations

from pathlib import Path

from build.practice import practice_observations

ROOT = Path(__file__).resolve().parents[3]


def extract(pages=None, lexicon=None, attrs=None, hide_labels: bool = True):
    return practice_observations(str(ROOT / "data" / "practice.csv"),
                                 str(ROOT / "data" / "lexicon.json"), hide_labels=hide_labels)
