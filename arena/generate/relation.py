"""relation claims: a fact of the entity a subject's name-valued attribute
names, while it named it (true); a value from outside that period, or one the
target never held (false)."""
from __future__ import annotations

from typing import Iterator

from arena.generate import deps
from arena.generate.common import claim, contains, evidence, merge_evidence, usable_pairs, weak
from arena.generate.perturb import perturbed_values
from arena.model import Claim, Interval

OPEN_END = "9999-12-31"


def _overlaps(a: Interval, b: Interval) -> bool:
    return a.start < (b.end or OPEN_END) and b.start < (a.end or OPEN_END)


def generate_relations(timelines, lexicon, attrs, config: dict) -> Iterator[Claim]:
    """Every name-valued link whose value resolves to a lexicon subject, crossed
    with each of the target's attributes."""
    pairs = usable_pairs(timelines, lexicon, attrs)
    by_subject: dict[str, list] = {}
    for subject, attribute, intervals in pairs:
        by_subject.setdefault(subject, []).append((attribute, intervals))
    for subject, link, link_ivs in pairs:
        for link_iv in link_ivs:
            if link_iv.value.kind != "name" or weak(link_iv):
                continue
            target = lexicon.resolve(link_iv.value.value)
            if not target or target == subject:
                continue
            link_ev = evidence("relation", link_iv, link_ivs)
            for attribute, ivs in by_subject.get(target, []):
                inside = [iv for iv in ivs if _overlaps(iv, link_iv)]
                if not inside:
                    continue
                true_iv = max(inside, key=lambda iv: iv.support)
                ev = merge_evidence("relation", link_ev, evidence("relation", true_iv, ivs),
                                    kind=true_iv.value.kind)
                base = {"subject": subject, "link": link, "target": target,
                        "attribute": attribute}
                yield claim("relation", dict(base, value=true_iv.value.to_json()), True, ev)
                held = [iv.value for iv in inside]
                outside = [iv for iv in ivs if not contains(held, iv.value)]
                if outside:
                    yield claim("relation", dict(base, value=outside[-1].value.to_json()),
                                False, dict(ev, stale=True))
                    continue
                fakes = perturbed_values(target, attribute, true_iv.value,
                                         [iv.value for iv in ivs], timelines, lexicon)
                if fakes:
                    yield claim("relation", dict(base, value=fakes[0].to_json()), False,
                                dict(ev, perturbed=True))
