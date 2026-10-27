"""Claim generation: five lazy streams interleaved by a static priority.

generate() yields claims best first and never blocks: each stream does at most
one sort of the pairs up front, then yields one claim at a time. A stream that
raises is closed and counted in stats; the others carry on."""
from __future__ import annotations

import json
from itertools import islice
from typing import Iterator, Optional

from arena.model import Claim, ClaimStream

GEN_CONFIG = {
    "fact_false_per_pair": 2,
    "compare_per_attr": 30,
    "change_per_pair": 3,
    "change_stable_max": 300,
    "at_event_per_event": 60,
    "caps": {"fact": 2500, "compare": 1000, "change": 900, "at_event": 900, "relation": 500},
    "weights": {"fact": 3, "compare": 1, "change": 1, "at_event": 1, "relation": 1},
    "total": 5000,
}

ORDER = ("fact", "compare", "change", "at_event", "relation")


def _streams(timelines, lexicon, attrs, config):
    from arena.generate.at_event import generate_at_events
    from arena.generate.change import generate_changes
    from arena.generate.compare import generate_compares
    from arena.generate.fact import generate_facts
    from arena.generate.relation import generate_relations
    makers = {"fact": generate_facts, "compare": generate_compares, "change": generate_changes,
              "at_event": generate_at_events, "relation": generate_relations}
    return {t: makers[t](timelines, lexicon, attrs, config) for t in ORDER}


def _guarded(name: str, stream: Iterator[Claim], cap: int, stats: dict) -> Iterator[Claim]:
    try:
        yield from islice(stream, cap)
    except Exception as e:  # one broken generator must not stop the run
        stats.setdefault("generator_errors", {})[name] = f"{type(e).__name__}: {e}"


def generate(timelines, lexicon, attrs, config: Optional[dict] = None,
             stats: Optional[dict] = None) -> ClaimStream:
    """Claims in descending expected score: per round, weights[type] claims from
    each stream in ORDER (fact, compare, change, at_event, relation), so a cut at
    any point holds a mix of types. Duplicate forms are dropped."""
    config = config or GEN_CONFIG
    stats = stats if stats is not None else {}
    raw = _streams(timelines, lexicon, attrs, config)
    queue = [(t, _guarded(t, raw[t], config["caps"][t], stats), config["weights"][t])
             for t in ORDER]
    seen: set[str] = set()
    total = 0
    while queue and total < config["total"]:
        nxt = []
        for t, stream, w in queue:
            taken, alive = 0, True
            while taken < w:
                c = next(stream, None)
                if c is None:
                    alive = False
                    break
                key = json.dumps([c.type, c.form], sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                taken += 1
                total += 1
                yield c
                if total >= config["total"]:
                    return
            if alive:
                nxt.append((t, stream, w))
        queue = nxt
