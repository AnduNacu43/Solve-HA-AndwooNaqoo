"""Stub of B's arena.attrs / reliability / timeline / calibrate (00-shared.md §3).

Seed observations come from data/baked/timelines_seed.json when B's file is
present, otherwise straight from data/practice.csv. Timelines keep labelled-
true (and unlabelled) observations, one winner per date, and merge runs of the
same value; `current` is the interval holding on AS_OF_DATE."""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import arena
from arena.model import AS_OF_DATE, AttrSpec, Interval, Observation, Timelines, Value

from grammar_stub import same_value  # loaded from the same stubs folder

ROOT = Path(arena.__file__).resolve().parent.parent
PRACTICE = ROOT / "data" / "practice.csv"


def _practice_rows():
    with open(PRACTICE, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def _observations_from_practice() -> list[Observation]:
    out, page_no, last_date = [], 0, None
    for row in _practice_rows():
        if row["date"] != last_date:
            page_no, last_date = page_no + 1, row["date"]
        for fact in json.loads(row["form"]):
            out.append(Observation(
                subject=fact["subject"], attribute=fact["attribute"],
                value=Value.from_json(fact["value"]), date=row["date"],
                page_id=f"pg-{page_no:04d}", row_id=row["id"], sentence=row["text"],
                subject_in_sentence=fact["subject"].lower() in row["text"].lower(),
                label=row["label"],
            ))
    return out


def _observation_from_json(d: dict) -> Observation:
    d = dict(d)
    d["value"] = Value.from_json(d["value"])
    d["cues"] = frozenset(d.get("cues") or ())
    return Observation(**d)


def load_seed(path: str = "data/baked/timelines_seed.json") -> list[Observation]:
    """Labelled practice observations: B's baked file, else practice.csv."""
    p = Path(path) if os.path.isabs(path) else ROOT / path
    if p.exists():
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        items = raw["observations"] if isinstance(raw, dict) else raw
        return [_observation_from_json(d) for d in items]
    return _observations_from_practice()


def load_attrs(path: str = "data/baked/attrs.json") -> dict[tuple[str, str], AttrSpec]:
    """(subject, attribute) -> AttrSpec by majority vote over practice forms."""
    votes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for o in _observations_from_practice():
        v = o.value
        votes[o.key()][(v.kind, v.unit, v.currency, v.per)] += 1
    out = {}
    for key, c in votes.items():
        (kind, unit, currency, per), _ = c.most_common(1)[0]
        out[key] = AttrSpec(kind, unit, currency, per, sum(c.values()))
    return out


def spec_for(attrs, subject: str, attribute: str) -> Optional[AttrSpec]:
    """Exact (subject, attribute) first, then the same attribute on any subject."""
    if (subject, attribute) in attrs:
        return attrs[(subject, attribute)]
    for (_, a), spec in attrs.items():
        if a == attribute:
            return spec
    return None


def infer_spec(values: list[Value]) -> AttrSpec:
    c = Counter((v.kind, v.unit, v.currency, v.per) for v in values)
    (kind, unit, currency, per), n = c.most_common(1)[0]
    return AttrSpec(kind, unit, currency, per, n)


def load_priors(path: str = "data/baked/priors.json") -> dict:
    return {}


def page_weights(observations, priors, timelines=None) -> dict[str, float]:
    return {o.page_id: 1.0 for o in observations}


def build(observations: list[Observation], weights: dict[str, float],
          aliases: Optional[dict] = None) -> Timelines:
    """Per pair: one winning value per date, runs of equal values merged.
    aliases is accepted for B's signature and not used."""
    by_pair: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for o in observations:
        if o.label in ("false", "unsure") or o.value.op not in (None, "eq"):
            continue
        by_pair[o.key()].append(o)
    timelines: Timelines = {}
    for key, obs in by_pair.items():
        by_date: dict[str, list[Observation]] = defaultdict(list)
        for o in obs:
            by_date[o.date].append(o)
        intervals: list[Interval] = []
        for date in sorted(by_date):
            groups: list[list[Observation]] = []
            for o in by_date[date]:
                for g in groups:
                    if same_value(g[0].value, o.value):
                        g.append(o)
                        break
                else:
                    groups.append([o])
            groups.sort(key=lambda g: -sum(weights.get(o.page_id, 1.0) for o in g))
            win, rest = groups[0], groups[1:]
            w = sum(weights.get(o.page_id, 1.0) for o in win)
            c = sum(weights.get(o.page_id, 1.0) for g in rest for o in g)
            anchored = any(o.label == "true" for o in win)
            if intervals and same_value(intervals[-1].value, win[0].value):
                iv = intervals[-1]
                iv.support += w
                iv.conflict += c
                iv.n_obs += len(win)
                iv.anchored = iv.anchored or anchored
            else:
                intervals.append(Interval(key[0], key[1], win[0].value, date, None,
                                          w, c, len(win), anchored))
        intervals = _drop_blips(intervals)
        for a, b in zip(intervals, intervals[1:]):
            a.end = b.start
        timelines[key] = intervals
    return timelines


def _drop_blips(intervals: list[Interval]) -> list[Interval]:
    """A single-observation value sandwiched between two runs of one value is noise."""
    changed = True
    while changed:
        changed = False
        for i in range(1, len(intervals) - 1):
            a, b, c = intervals[i - 1], intervals[i], intervals[i + 1]
            if b.n_obs == 1 and same_value(a.value, c.value):
                a.support += c.support
                a.conflict += c.conflict + b.support
                a.n_obs += c.n_obs
                a.anchored = a.anchored or c.anchored
                intervals = intervals[:i] + intervals[i + 2:]
                changed = True
                break
    return intervals


def value_at(intervals: list[Interval], date: str) -> Optional[Interval]:
    for iv in intervals:
        if iv.start <= date and (iv.end is None or date < iv.end):
            return iv
    return None


def current(intervals: list[Interval]) -> Optional[Interval]:
    return value_at(intervals, AS_OF_DATE)


def volatility(intervals: list[Interval]) -> int:
    distinct: list[Value] = []
    for iv in intervals:
        if not any(same_value(iv.value, v) for v in distinct):
            distinct.append(iv.value)
    return len(distinct)


def load_calibration(path: str = "data/baked/calibration.json") -> dict:
    return {}


def confidence(claim, calibration: dict) -> float:
    """0.8 for true, 0.9 for perturbed false, 0.6 otherwise."""
    if claim.label == "true":
        return 0.8
    if claim.evidence.get("perturbed"):
        return 0.9
    return 0.6
