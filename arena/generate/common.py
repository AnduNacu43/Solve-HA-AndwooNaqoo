"""Helpers every generator shares: which timeline pairs are usable, evidence
built from intervals, stable ordering, round-robin."""
from __future__ import annotations

import hashlib
from collections import deque
from typing import Iterable, Iterator, Optional

from arena.generate import deps
from arena.model import Claim, Interval, Value


def stable_hash(*parts) -> int:
    raw = "\x1f".join(str(p) for p in parts)
    return int(hashlib.md5(raw.encode("utf-8")).hexdigest()[:8], 16)


def exact(v: Value) -> bool:
    """A value an entry may state: no op other than eq (dataset 'over 100' is not 100)."""
    return v.op in (None, "eq")


def weak(iv: Interval) -> bool:
    """One unlabelled sighting: too little to state a true claim on. One
    misread sentence would otherwise fan out into many wrong claims."""
    return not iv.anchored and iv.n_obs < 2


def usable_pairs(timelines, lexicon, attrs) -> list[tuple[str, str, list[Interval]]]:
    """(subject, attribute, intervals) whose subject and attribute exist in the
    run-time lexicon and whose values have the kind the attribute carries."""
    out = []
    for (subject, attribute), intervals in timelines.items():
        canon = lexicon.resolve(subject)
        if not canon or not intervals or not lexicon.has_attribute(canon, attribute):
            continue
        spec = deps.spec_for(attrs, canon, attribute)
        kept = [iv for iv in intervals if exact(iv.value)
                and (spec is None or spec.kind == iv.value.kind)]
        if kept:
            out.append((canon, attribute, kept))
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def evidence(ctype: str, iv: Interval, intervals: list[Interval], **extra) -> dict:
    ev = {
        "type": ctype,
        "kind": iv.value.kind,
        "support": iv.support,
        "conflict": iv.conflict,
        "n_obs": iv.n_obs,
        "volatility": deps.volatility(intervals),
        "anchored": iv.anchored,
        "perturbed": False,
        "stale": False,
    }
    ev.update(extra)
    return ev


def merge_evidence(ctype: str, a: dict, b: dict, **extra) -> dict:
    """Evidence of a claim resting on two facts: the weaker side bounds it."""
    ev = {
        "type": ctype,
        "kind": a["kind"],
        "support": min(a["support"], b["support"]),
        "conflict": max(a["conflict"], b["conflict"]),
        "n_obs": min(a["n_obs"], b["n_obs"]),
        "volatility": max(a["volatility"], b["volatility"]),
        "anchored": a["anchored"] and b["anchored"],
        "perturbed": False,
        "stale": False,
    }
    ev.update(extra)
    return ev


def contains(seen: Iterable[Value], v: Value) -> bool:
    return any(s.kind == v.kind and deps.same_value(s, v) for s in seen)


def claim(ctype: str, form: dict, label: bool, ev: dict) -> Claim:
    return Claim(type=ctype, form=form, label="true" if label else "false", evidence=ev)


def round_robin(streams: list[Iterator], weights: Optional[list[int]] = None) -> Iterator:
    """Take weights[i] items from each stream in turn until all are empty."""
    weights = weights or [1] * len(streams)
    queue = deque(zip(streams, weights))
    while queue:
        stream, w = queue.popleft()
        alive = True
        for _ in range(w):
            try:
                yield next(stream)
            except StopIteration:
                alive = False
                break
        if alive:
            queue.append((stream, w))
