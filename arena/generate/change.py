"""change claims: a pair held one value and later another (true); the reverse
when it never happened, or a from-value it never held (false)."""
from __future__ import annotations

from typing import Iterator

from arena.generate import deps
from arena.generate.common import claim, contains, evidence, round_robin, usable_pairs, weak
from arena.generate.perturb import perturbed_values
from arena.model import Claim, Interval


def _happened(intervals: list[Interval], a, b) -> bool:
    """Some interval holding a is followed, later, by one holding b."""
    for i, x in enumerate(intervals):
        if deps.same_value(x.value, a):
            if any(deps.same_value(y.value, b) for y in intervals[i + 1:]):
                return True
    return False


def _transitions(intervals: list[Interval]) -> list[tuple[Interval, Interval]]:
    """Consecutive transitions first, then the longer jumps, without repeats."""
    out: list[tuple[Interval, Interval]] = []
    for gap in range(1, len(intervals)):
        for i in range(len(intervals) - gap):
            a, b = intervals[i], intervals[i + gap]
            if deps.same_value(a.value, b.value) or weak(a) or weak(b):
                continue
            if any(deps.same_value(a.value, x.value) and deps.same_value(b.value, y.value)
                   for x, y in out):
                continue
            out.append((a, b))
    return out


def _pair(subject, attribute, intervals, timelines, lexicon, config) -> Iterator[Claim]:
    seen = [iv.value for iv in intervals]
    n = 0
    for a, b in _transitions(intervals):
        if n >= config["change_per_pair"]:
            return
        ev = evidence("change", b, intervals, from_support=a.support,
                      support=min(a.support, b.support), anchored=a.anchored and b.anchored)
        form = {"subject": subject, "attribute": attribute,
                "from": a.value.to_json(), "to": b.value.to_json()}
        yield claim("change", form, True, ev)
        if not _happened(intervals, b.value, a.value):
            swapped = {"subject": subject, "attribute": attribute,
                       "from": b.value.to_json(), "to": a.value.to_json()}
            yield claim("change", swapped, False, dict(ev, swapped=True))
        else:
            fakes = perturbed_values(subject, attribute, a.value, seen, timelines, lexicon)
            if fakes:
                form = {"subject": subject, "attribute": attribute,
                        "from": fakes[0].to_json(), "to": b.value.to_json()}
                yield claim("change", form, False, dict(ev, perturbed=True))
        n += 1


def _stable_pair(subject, attribute, intervals, timelines, lexicon) -> Iterator[Claim]:
    """A single-valued pair never changed: a change into its value from one it
    never held is false."""
    cur = deps.current(intervals)
    if cur is None or cur.value.kind == "boolean":
        return
    seen = [iv.value for iv in intervals]
    fakes = [f for f in perturbed_values(subject, attribute, cur.value, seen, timelines, lexicon)
             if not contains(seen, f)]
    if fakes:
        form = {"subject": subject, "attribute": attribute,
                "from": fakes[0].to_json(), "to": cur.value.to_json()}
        yield claim("change", form, False, evidence("change", cur, intervals, perturbed=True))


def generate_changes(timelines, lexicon, attrs, config: dict) -> Iterator[Claim]:
    """Pairs that changed first (most intervals first), then false changes on
    well-supported single-valued pairs."""
    # A's referee clone refuses yes/no changes ("not written by this system")
    pairs = [p for p in usable_pairs(timelines, lexicon, attrs)
             if p[2][0].value.kind != "boolean"]
    moving = sorted((p for p in pairs if deps.volatility(p[2]) >= 2),
                    key=lambda p: (-deps.volatility(p[2]), p[0], p[1]))
    yield from round_robin([_pair(s, a, ivs, timelines, lexicon, config) for s, a, ivs in moving])
    still = sorted((p for p in pairs if deps.volatility(p[2]) == 1),
                   key=lambda p: (-max(iv.support for iv in p[2]), p[0], p[1]))
    for s, a, ivs in still[:config["change_stable_max"]]:
        yield from _stable_pair(s, a, ivs, timelines, lexicon)
