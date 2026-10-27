"""fact claims: the current value of a pair (true) and values it does not hold
on the as-of date (false: perturbed or stale)."""
from __future__ import annotations

from typing import Iterator

from arena.generate import deps
from arena.generate.common import claim, evidence, usable_pairs, weak
from arena.generate.perturb import false_values
from arena.model import Claim


def generate_facts(timelines, lexicon, attrs, config: dict) -> Iterator[Claim]:
    """Anchored single-valued pairs first, then by support; each pair's true
    claim is followed by up to config['fact_false_per_pair'] false twins."""
    ranked = []
    for subject, attribute, intervals in usable_pairs(timelines, lexicon, attrs):
        cur = deps.current(intervals)
        if cur is None:
            continue
        vol = deps.volatility(intervals)
        ranked.append((not (cur.anchored and vol == 1), -cur.support, subject, attribute,
                       intervals, cur))
    ranked.sort(key=lambda t: t[:4])
    for _, _, subject, attribute, intervals, cur in ranked:
        form = {"subject": subject, "attribute": attribute, "value": cur.value.to_json()}
        # a lone unlabelled sighting that displaced a pinned value is too thin to
        # call true, and the value it displaced may still hold: made-up falses only
        thin = weak(cur) and any(iv.anchored for iv in intervals if iv is not cur)
        if not thin:
            yield claim("fact", form, True, evidence("fact", cur, intervals))
        n = 0
        for value, perturbed, stale_iv in false_values(subject, attribute, intervals, cur,
                                                       timelines, lexicon):
            if n >= config["fact_false_per_pair"]:
                break
            if thin and not perturbed:
                continue
            form = {"subject": subject, "attribute": attribute, "value": value.to_json()}
            ev = evidence("fact", cur, intervals, perturbed=perturbed,
                          stale=stale_iv is not None)
            if stale_iv is not None:
                ev["stale_support"] = stale_iv.support
                ev["stale_end"] = stale_iv.end
            yield claim("fact", form, False, ev)
            n += 1
