"""Measure A's extractor on the practice text (build time).

Runs only when A's arena.extract, arena.pages and arena.lexicon import, that
is after agent-a/grammar is merged. Then bake.py:
  - takes each practice row's cues from what A's extract() emits for it, so
    priors.json learns multipliers for exactly the cues A emits at run time
    (rows A extracts nothing from keep build/practice.py's regex cues);
  - stores the extractor's precision per value kind and per "subject named
    in the sentence or taken from context" in priors.json["extraction"];
    timeline.observation_weight multiplies unlabelled observations by it.
Before the merge nothing changes: no table, regex cues.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from arena.model import Observation
from arena.timeline import extraction_key, value_key

PRECISION_SMOOTHING = 10.0   # pseudo-observations pulling a kind toward the overall precision


def available() -> bool:
    try:
        from arena.extract import extract  # noqa: F401
        from arena.lexicon import Lexicon  # noqa: F401
        from arena.pages import load_universe  # noqa: F401
    except ImportError:
        return False
    return True


def extract_practice(csv_path: str, lexicon_path: str, attrs) -> list[Observation]:
    """A's observations of the practice text, unlabelled, as at run time."""
    from arena.extract import extract
    from arena.lexicon import Lexicon
    from arena.pages import load_universe

    return extract(load_universe(csv_path), Lexicon.load(lexicon_path), attrs)


def precision_table(extracted: list[Observation], gold: list[Observation]) -> dict[str, float]:
    """`<kind>:named|context` -> share of extracted facts found in the row's
    form (same subject, attribute and value after unit conversion), shrunk
    toward the overall share."""
    forms = defaultdict(set)
    for o in gold:
        forms[o.row_id].add((o.subject, o.attribute, value_key(o.value)))
    hit, n = Counter(), Counter()
    for o in extracted:
        k = extraction_key(o).split(":", 1)[1]
        n[k] += 1
        hit[k] += (o.subject, o.attribute, value_key(o.value)) in forms[o.row_id]
    overall = sum(hit.values()) / max(1, sum(n.values()))
    m = PRECISION_SMOOTHING
    return {k: round((hit[k] + m * overall) / (n[k] + m), 4) for k in sorted(n)}


def cues_by_row(extracted: list[Observation]) -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for o in extracted:
        out[o.row_id] |= set(o.cues)
    return {r: frozenset(c) for r, c in out.items()}
