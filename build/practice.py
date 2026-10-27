"""Practice rows -> labelled Observations (build time only).

Every fact in every `form` becomes one Observation. Pages are maximal runs of
consecutive ids sharing a date, numbered `seed-pg-0001`... so they never
collide with the run-time universe's page ids. Cues are simple regexes in the
spirit of A's extractor; they need not match A's exactly, because
reliability learns a multiplier per cue name from whatever fires.
"""
from __future__ import annotations

import csv
import json
import re
from typing import Optional

from arena.model import Observation, Value

SEED_PAGE_PREFIX = "seed-pg-"

_CUE_PATTERNS: dict[str, re.Pattern] = {
    "gavin": re.compile(r"\bGavin\b"),
    "first_person": re.compile(r"\b(I|I'm|I've|me|my)\b"),
    "boast": re.compile(
        r"more than any|can only dream|not even tired|before lunch|poetry|asked for it to be higher"
        r"|never misses|like nothing|best money|the best|in the world|record|and counting",
        re.I),
    "hearsay": re.compile(
        r"I have been told|I('ve| have) heard|\brecalls\b|between us|reportedly|rumou?r|apparently"
        r"|has said|they say|according to|told the room",
        re.I),
    "hedge": re.compile(r"\bthough\b|\balthough\b|\bbut the real\b|listed fewer|is lower|is higher", re.I),
    "announce_future": re.compile(
        r"\bcoming\b|\bwill\b|\bsoon\b|next (week|month|quarter|year)|\bplanned\b|\bplans to\b"
        r"|is getting|\bstarting\b|\bfrom \d{1,2} [A-Z][a-z]+",
        re.I),
    "press_release": re.compile(
        r"\btoday (announced|launched|unveiled|introduced|released)\b|^[A-Z][a-z]+, \d{1,2} [A-Z][a-z]+ \d{4}$"),
    "release_notes": re.compile(r"release notes|changelog|\bships today\b|\bis out\b", re.I),
}
_SPEAKER = re.compile(r"^([A-Z][A-Za-z]+):\s+(.*)$")
_TERMINAL = re.compile(r"[.!?][\"'”)]?$")


def cues_for(text: str) -> set[str]:
    """Cue names that fire on one sentence."""
    t = text.strip()
    cues = {name for name, pat in _CUE_PATTERNS.items() if pat.search(t)}
    m = _SPEAKER.match(t)
    if m and len(m.group(2).split()) >= 5:
        cues.add("speaker")
    if "first_person" in cues:
        cues.discard("first_person")
        cues.add("first_person" if "speaker" in cues else "testimonial")
    words = len(t.split())
    if words <= 4:
        cues.add("table_cell")
    elif not _TERMINAL.search(t):
        cues.add("headline")
    return cues


class NameFinder:
    """Whole-word, case-insensitive, longest-match lexicon mentions.

    Build-time stand-in for A's Lexicon.find_mentions: a name inside a longer
    name refers only to the longer one.
    """

    def __init__(self, lexicon: dict):
        self.canonical: dict[str, str] = {}
        for s in lexicon["subjects"]:
            for n in [s["name"], *s.get("aliases", [])]:
                self.canonical[" ".join(n.split()).casefold()] = s["name"]
        names = sorted(self.canonical, key=lambda n: (-len(n), n))
        body = "|".join(r"\s+".join(re.escape(w) for w in n.split()) for n in names)
        self._re = re.compile(rf"(?<![\w])(?:{body})(?![\w])", re.I)

    def subjects(self, text: str) -> set[str]:
        return {self.canonical[" ".join(m.group(0).split()).casefold()] for m in self._re.finditer(text)}


def load_lexicon(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_rows(path: str) -> list[dict]:
    """Practice rows in id order (p-1, p-2, ...)."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: int(r["id"].split("-")[-1]))
    return rows


def page_ids(rows: list[dict]) -> list[str]:
    """One page id per row: a new page starts whenever the date changes."""
    out, n, prev = [], 0, None
    for r in rows:
        if r["date"] != prev:
            n += 1
            prev = r["date"]
        out.append(f"{SEED_PAGE_PREFIX}{n:04d}")
    return out


def practice_observations(csv_path: str = "data/practice.csv",
                          lexicon_path: str = "data/lexicon.json",
                          hide_labels: bool = False,
                          lexicon: Optional[dict] = None) -> list[Observation]:
    """Every fact of every practice row as an Observation, in row order."""
    finder = NameFinder(lexicon or load_lexicon(lexicon_path))
    rows = read_rows(csv_path)
    out = []
    for r, page in zip(rows, page_ids(rows)):
        mentioned = finder.subjects(r["text"])
        cues = frozenset(cues_for(r["text"]))
        for fact in json.loads(r["form"]):
            out.append(Observation(
                subject=fact["subject"], attribute=fact["attribute"],
                value=Value.from_json(fact["value"]), date=r["date"],
                page_id=page, row_id=r["id"], sentence=r["text"],
                subject_in_sentence=fact["subject"] in mentioned, cues=cues,
                label=None if hide_labels else r["label"],
            ))
    return out
