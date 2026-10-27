"""compare claims: two subjects' current values of the same attribute, in the
order compare_values gives (true) and the opposite order (false)."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterator

from arena.generate import deps
from arena.generate.common import (claim, evidence, merge_evidence, round_robin,
                                   stable_hash, usable_pairs)
from arena.model import Claim

OPPOSITE = {"gt": "lt", "lt": "gt", "eq": "gt"}


def _rel_diff(a, b) -> float:
    try:
        x, y = float(a.value), float(b.value)
    except (TypeError, ValueError):
        return 0.0
    return abs(x - y) / max(abs(x), abs(y), 1e-9)


def _group(attribute: str, members: list, config: dict) -> Iterator[Claim]:
    pairs = []
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            (si, ivi, alli), (sj, ivj, allj) = members[i], members[j]
            op = deps.compare_values(ivi.value, ivj.value)
            if op is None:
                continue
            ei, ej = evidence("compare", ivi, alli), evidence("compare", ivj, allj)
            strength = (ei["anchored"] and ej["anchored"], min(ei["support"], ej["support"]))
            pairs.append((strength, si, sj, op, ei, ej, _rel_diff(ivi.value, ivj.value)))
    pairs.sort(key=lambda p: (not p[0][0], -p[0][1], p[1], p[2]))
    for _, si, sj, op, ei, ej, rel in pairs[:config["compare_per_attr"]]:
        if stable_hash(si, sj, attribute) % 2:
            si, sj, ei, ej = sj, si, ej, ei
            op = {"gt": "lt", "lt": "gt", "eq": "eq"}[op]
        ev = merge_evidence("compare", ei, ej, rel_diff=rel)
        left = {"subject": si, "attribute": attribute}
        right = {"subject": sj, "attribute": attribute}
        yield claim("compare", {"left": left, "right": right, "op": op}, True, ev)
        yield claim("compare", {"left": left, "right": right, "op": OPPOSITE[op]}, False,
                    dict(ev))


def generate_compares(timelines, lexicon, attrs, config: dict) -> Iterator[Claim]:
    """Same attribute across different subjects, comparable kinds only;
    round-robin across attributes so one attribute cannot crowd out the rest."""
    groups: dict[str, list] = defaultdict(list)
    for subject, attribute, intervals in usable_pairs(timelines, lexicon, attrs):
        cur = deps.current(intervals)
        if cur is None or cur.value.kind in ("name", "boolean"):
            continue
        groups[attribute].append((subject, cur, intervals))
    streams = [_group(a, m, config) for a, m in sorted(groups.items(), key=lambda g: -len(g[1]))
               if len(m) >= 2]
    yield from round_robin(streams)
