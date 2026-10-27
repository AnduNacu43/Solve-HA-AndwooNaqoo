"""Confidence of a claim's label: a lookup table plus caps, no model.

data/baked/calibration.json holds, for fact pseudo-claims replayed on the
practice set (each fold judged with the other folds' labels as anchors), how
often a label of each bucket was right. Buckets nest from coarse to fine:

    label | anchored | kind | volatility (1, 2, 3, 4+) | support bucket

and a bucket's rate is shrunk toward its parent's (m-estimate), so thin
buckets fall back gracefully. The rate is made non-decreasing in support.

claim.evidence keys read here (C fills them from the intervals used):
    support, conflict, n_obs, volatility, kind, anchored   -- one interval, or
                                  several merged flat (weakest side bounds)
    sides: [{same keys}, ...]  -- optional: one dict per interval
                                  (compare, change, at_event, relation)
    perturbed   -- the value was made up by perturb.py
    value_seen  -- that made-up value does appear in the universe for the pair
    spec_inferred -- the attribute's kind was inferred at run time
C builds every claim from its own intervals: a true claim states what they
hold; a false one states a superseded value, another interval's value or a
swapped order, and is false whenever they are right. So every claim uses
the interval-correctness rate (the label=true rows of the table), the
product q over `sides` when given; for a compare, a wrong side still leaves
the op right about half the time, so p = q + (1 - q) / 2. For a false claim
q is a lower bound (a wrong interval can still leave the claim false). The
label=false rows measure something C does not emit (an observed value the
timeline contradicts) and are kept for the report only. Other keys C sets
(stale, swapped, rel_diff, stale_support, other_support) are not read.

Caps and floors (plans/agent-b-timelines.md B4), applied after the table:
    perturbed, never-seen, non-boolean false claim -> 0.95
    fact/compare, every interval single-valued, anchored, >= 3 obs -> >= 0.9
    any interval with volatility >= 4 -> <= 0.7
    boolean not anchored -> <= 0.8
    true claim with conflict > support / 3 -> <= 0.65
    1.0 only with support >= 10, conflict 0, anchored; else <= 0.99
    spec inferred at run time -> <= 0.6
The volatility, boolean and conflict caps judge our timeline value, so they
do not apply to a perturbed never-seen value, which is false either way.
"""
from __future__ import annotations

import json
from typing import Optional

from arena.attrs import baked_path
from arena.model import Claim

DEFAULT_RULES = {
    "perturbed_novel": 0.95,
    "stable_anchored_floor": 0.9,
    "stable_min_obs": 3,
    "volatile_at": 4,
    "volatile_cap": 0.7,
    "boolean_cap": 0.8,
    "conflict_ratio": 1 / 3,
    "conflict_cap": 0.65,
    "certain_support": 10.0,
    "below_certain_cap": 0.99,
    "inferred_cap": 0.6,
}


def load_calibration(path: str = "data/baked/calibration.json") -> dict:
    """The table and rules baked by build/bake.py."""
    with open(baked_path(path), encoding="utf-8") as f:
        return json.load(f)


def support_bucket(support: float, edges) -> int:
    return sum(support >= e for e in edges)


def volatility_bucket(vol: int) -> int:
    return max(1, min(4, int(vol)))


def bucket_path(label: str, anchored: bool, kind: str, vol: int, sup_bucket: int) -> list[str]:
    """Table keys from the coarsest bucket to the finest."""
    parts = [f"label={label}", f"anchored={int(bool(anchored))}", f"kind={kind}",
             f"vol={volatility_bucket(vol)}", f"sup={sup_bucket}"]
    return ["|".join(parts[: n + 1]) for n in range(len(parts))]


def table_rate(calibration: dict, label: str, anchored: bool, kind: str, vol: int,
               support: float) -> float:
    """Shrunk empirical rate for one interval, non-decreasing in support and
    never lower for an anchored interval than for the same one unanchored
    (a labelled row only adds information; thin buckets can invert by noise)."""
    edges = calibration["support_edges"]
    top = support_bucket(support, edges)
    flags = (False, True) if anchored else (False,)
    return max(_rate(calibration, bucket_path(label, a, kind, vol, b))
               for b in range(top + 1) for a in flags)


def _rate(calibration: dict, path: list[str]) -> float:
    hits, n = calibration["global"]
    p = (hits + 1) / (n + 2)
    m = calibration["m"]
    table = calibration["table"]
    for key in path:
        if key in table:
            h, k = table[key]
            p = (h + m * p) / (k + m)
    return p


def _sides(ev: dict) -> list[dict]:
    sides = ev.get("sides")
    if sides:
        return [{**{k: ev[k] for k in ("kind",) if k in ev}, **s} for s in sides]
    return [ev]


def confidence(claim: Claim, calibration: dict) -> float:
    """Probability that claim.label is right, in [0.5, 1.0]."""
    rules = {**DEFAULT_RULES, **calibration.get("rules", {})}
    ev = claim.evidence or {}
    sides = _sides(ev)
    kind = ev.get("kind") or sides[0].get("kind", "quantity")

    novel = (claim.label == "false" and ev.get("perturbed") and not ev.get("value_seen")
             and kind != "boolean")
    if novel:
        p = rules["perturbed_novel"]
    else:
        # every claim C makes is right when the intervals it was built from are
        # right: interval correctness, the label=true rate of the table
        q = 1.0
        for s in sides:
            q *= table_rate(calibration, "true", bool(s.get("anchored")), s.get("kind", kind),
                            int(s.get("volatility", 1)), float(s.get("support", 0.0)))
        p = q + (1 - q) / 2 if claim.type == "compare" else q

        stable = all(int(s.get("volatility", 1)) == 1 and s.get("anchored")
                     and int(s.get("n_obs", 0)) >= rules["stable_min_obs"] for s in sides)
        if claim.type in ("fact", "compare") and stable:
            p = max(p, rules["stable_anchored_floor"])
        if any(int(s.get("volatility", 1)) >= rules["volatile_at"] for s in sides):
            p = min(p, rules["volatile_cap"])
        if kind == "boolean" and not all(s.get("anchored") for s in sides):
            p = min(p, rules["boolean_cap"])
        if claim.label == "true" and any(
                float(s.get("conflict", 0.0)) > float(s.get("support", 0.0)) * rules["conflict_ratio"]
                for s in sides):
            p = min(p, rules["conflict_cap"])

    certain = all(float(s.get("support", 0.0)) >= rules["certain_support"]
                  and float(s.get("conflict", 0.0)) == 0 and s.get("anchored") for s in sides)
    if not certain:
        p = min(p, rules["below_certain_cap"])
    if ev.get("spec_inferred"):
        p = min(p, rules["inferred_cap"])
    return round(min(1.0, max(0.5, p)), 3)


def describe(calibration: dict, kinds: Optional[list[str]] = None) -> str:
    """The table at label x anchored x kind level, for the README and demo."""
    table = calibration["table"]
    lines = [f"{'label':6} {'anchored':8} {'kind':9} {'right':>6} {'n':>5}"]
    for key in sorted(k for k in table if k.count("|") == 2):
        parts = dict(p.split("=") for p in key.split("|"))
        if kinds and parts["kind"] not in kinds:
            continue
        h, n = table[key]
        lines.append(f"{parts['label']:6} {parts['anchored']:8} {parts['kind']:9} {h / n:6.3f} {n:5d}")
    rules = {**DEFAULT_RULES, **calibration.get("rules", {})}
    lines.append("rules: " + ", ".join(f"{k}={round(v, 3)}" for k, v in sorted(rules.items())))
    return "\n".join(lines)
