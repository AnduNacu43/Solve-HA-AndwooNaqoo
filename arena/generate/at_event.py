"""at_event claims: a pair's value on an event's date (true), and a value it
held at another time or never held (false)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

from arena.generate import deps
from arena.generate.common import claim, evidence, merge_evidence, round_robin, usable_pairs
from arena.generate.perturb import perturbed_values
from arena.model import AS_OF_DATE, Claim

NEAR_DAYS = 45


def _event_dates(timelines, lexicon) -> list[tuple[str, str, dict]]:
    """(event, YYYY-MM-DD, evidence of the date) for past events with a day-precise date."""
    out = []
    for event in sorted(lexicon.events):
        attr = lexicon.event_date_attr(event)
        intervals = timelines.get((event, attr)) if attr else None
        if not intervals:
            continue
        cur = deps.current(intervals)
        if cur is None or cur.value.kind != "date" or len(str(cur.value.value)) != 10:
            continue
        if cur.value.value > AS_OF_DATE:
            continue
        out.append((event, cur.value.value, evidence("at_event", cur, intervals)))
    return out


def _near(intervals, day: str) -> bool:
    """A value of the pair changed within NEAR_DAYS of the event."""
    d = date.fromisoformat(day)
    lo, hi = (d - timedelta(days=NEAR_DAYS)).isoformat(), (d + timedelta(days=NEAR_DAYS)).isoformat()
    return any(lo <= iv.start <= hi for iv in intervals[1:])


def _event(event, day, date_ev, pairs, timelines, lexicon, config) -> Iterator[Claim]:
    cands = []
    for subject, attribute, intervals in pairs:
        if subject == event:
            continue
        iv = deps.value_at(intervals, day)
        if iv is None or iv.value.kind == "date":
            continue
        cands.append((not _near(intervals, day), -iv.support, subject, attribute, intervals, iv))
    cands.sort(key=lambda c: c[:4])
    for _, _, subject, attribute, intervals, iv in cands[:config["at_event_per_event"]]:
        ev = merge_evidence("at_event", evidence("at_event", iv, intervals), date_ev,
                            kind=iv.value.kind)
        base = {"subject": subject, "attribute": attribute, "event": event}
        yield claim("at_event", dict(base, value=iv.value.to_json()), True, ev)
        others = [o for o in intervals if not deps.same_value(o.value, iv.value)]
        if others:
            other = min(others, key=lambda o: abs(date.fromisoformat(o.start)
                                                   - date.fromisoformat(day)))
            yield claim("at_event", dict(base, value=other.value.to_json()), False,
                        dict(ev, stale=True, other_support=other.support))
        else:
            fakes = perturbed_values(subject, attribute, iv.value,
                                     [o.value for o in intervals], timelines, lexicon)
            if fakes:
                yield claim("at_event", dict(base, value=fakes[0].to_json()), False,
                            dict(ev, perturbed=True))


def generate_at_events(timelines, lexicon, attrs, config: dict) -> Iterator[Claim]:
    """Per event, pairs that changed near its date first, then by support;
    round-robin across events."""
    pairs = usable_pairs(timelines, lexicon, attrs)
    streams = [_event(e, d, ev, pairs, timelines, lexicon, config)
               for e, d, ev in _event_dates(timelines, lexicon)]
    yield from round_robin(streams)
