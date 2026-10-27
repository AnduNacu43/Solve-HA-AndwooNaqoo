"""How much to believe each page and row.

Pass 1 (no timelines): a row's weight is the product of the multipliers its
cues earn in data/baked/priors.json, P(true | cue) / P(true) learned on the
practice rows and clipped to [0.3, 1.0]. Besides the observation's own cues,
three cues are derived here: `context_subject` (the subject is not named in
the sentence), `month:YYYY-MM` and `date:YYYY-MM-DD` (2026-10-26 pages are
mostly stale repeats).

Pass 2 (with timelines): each row's weight is multiplied by its page's
agreement with the timelines, the share of the page's observations that hold
on the page date, smoothed with a Beta(2, 2) prior. One EM round of truth
discovery; callers run at most two.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Optional

from arena.attrs import baked_path
from arena.model import Observation, Timelines
from arena.timeline import consistent, row_key, value_at

BETA_PRIOR = (2.0, 2.0)


def load_priors(path: str = "data/baked/priors.json") -> dict:
    """The cue multipliers baked by build/bake.py."""
    with open(baked_path(path), encoding="utf-8") as f:
        return json.load(f)


def derived_cues(o: Observation) -> set[str]:
    """The observation's cues plus the ones reliability derives itself."""
    cues = set(o.cues)
    if not o.subject_in_sentence:
        cues.add("context_subject")
    cues.add("month:" + o.date[:7])
    cues.add("date:" + o.date)
    return cues


def cue_weight(cues, priors: dict) -> float:
    """Product of the cue multipliers, clipped to priors['clip']."""
    mult = priors.get("multipliers", {})
    w = 1.0
    for c in cues:
        w *= mult.get(c, 1.0)
    lo, hi = priors.get("clip", (0.3, 1.0))
    return min(hi, max(lo, w))


def page_weights(observations: list[Observation], priors: dict,
                 timelines: Optional[Timelines] = None) -> dict[str, float]:
    """Weights in (0, 1] keyed by row (timeline.row_key) and by page id.

    The first call (timelines=None) uses the cue priors only; the second also
    multiplies by the page's smoothed agreement with `timelines`. A page's own
    entry is the mean of its rows' weights.
    """
    row_cues: dict[str, set[str]] = defaultdict(set)
    page_of: dict[str, str] = {}
    for o in observations:
        k = row_key(o)
        row_cues[k] |= derived_cues(o)
        page_of[k] = o.page_id
    rows = {k: cue_weight(c, priors) for k, c in row_cues.items()}

    if timelines is not None:
        agree = page_agreement(observations, timelines)
        for k in rows:
            rows[k] *= agree.get(page_of[k], 1.0)

    pages: dict[str, list[float]] = defaultdict(list)
    for k, w in rows.items():
        pages[page_of[k]].append(w)
    out = dict(rows)
    for p, ws in pages.items():
        out[p] = sum(ws) / len(ws)
    return out


def page_agreement(observations: list[Observation], timelines: Timelines) -> dict[str, float]:
    """Per page: (agreeing + a) / (checked + a + b) with the Beta(a, b) prior.

    Observations of pairs with no interval on the page date are not checked;
    a page with nothing checked gets the prior mean."""
    a, b = BETA_PRIOR
    hits: dict[str, float] = defaultdict(float)
    n: dict[str, float] = defaultdict(float)
    for o in observations:
        iv = value_at(timelines.get(o.key(), []), o.date)
        if iv is None:
            continue
        n[o.page_id] += 1
        if consistent(o.value, iv.value):
            hits[o.page_id] += 1
    out = {}
    for p in n:
        out[p] = (hits[p] + a) / (n[p] + a + b)
    # pages with nothing to check keep the prior mean, a / (a + b)
    prior_mean = a / (a + b)
    for o in observations:
        out.setdefault(o.page_id, prior_mean)
    return out
