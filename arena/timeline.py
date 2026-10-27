"""Per-pair timelines: which value each (subject, attribute) held when.

build() merges observations into intervals by a weighted change-point search
per pair:

1. Observations are grouped by value: unit conversions (14 days = 2 weeks,
   1 TB = 1,000 GB), name aliases and name prefixes (`Gavin` = `Gavin Bellson`)
   collapse into one candidate. A month or year date supports the finer dates
   it covers; an `op` observation (`over 100`) supports every candidate that
   satisfies it, at half weight.
2. Each value's support splits into episodes where another value is seen in
   between; a return to an established value is a candidate of its own only
   if it passes the revert guard (plan rule 4: over its first 14 days, twice
   the support the other values have in that window and the 30 days before,
   on at least two dates), so a one-day stale nest never is.
   Candidates are put in time order by the weighted median date of their
   episode. A dynamic programme then splits the pair's dates into segments,
   each holding one candidate, later segments only taking later candidates.
   A segment pays a change penalty (CHANGE_PENALTY, rising with the log of
   the pair's total weight; three times that for a revert), so a lone lie
   never becomes an interval inside a run, and in a dense pair a lie on the
   last day does not become the current value. In a dense pair a new value
   must also be seen on two days: a one-day nest of stale pages (2026-10-26)
   never replaces the current value.
3. Labelled practice rows are anchors: a true row pins its value at its date;
   a false single-fact row excludes its value at its date; a false multi-fact
   row and an unsure row count at half weight.

Intervals are contiguous: each ends where the next starts, the last holds on
AS_OF_DATE. The first starts at the pair's first observation.
"""
from __future__ import annotations

import bisect
import calendar
import json
import math
from collections import Counter, defaultdict
from datetime import date as _date, timedelta
from typing import Iterable, Optional

from arena.attrs import baked_path, canonical_unit, unit_dimension
from arena.model import AS_OF_DATE, Interval, Observation, Timelines, Value

ANCHOR_WEIGHT = 25.0       # score of a labelled row; outweighs any unlabelled crowd
CHANGE_PENALTY = 0.6       # cost of a new segment, in observation-weight units
PENALTY_PER_LOG_WEIGHT = 0.3   # ... rising as 0.3 ln(1 + pair weight) for dense pairs
REVERT_PENALTY_FACTOR = 3.0    # a return to an earlier value costs three changes
DENSE_PAIR_WEIGHT = 8.0    # pair weight from which a change must be seen on ...
CHANGE_MIN_DATES = 2       # ... at least this many days (unless a labelled row pins it)
BURST_BONUS = 0.25         # change made cheaper per unit of the new value's support on its first day
BURST_CAP = 3.0
MAX_CANDIDATES = 8         # per pair; weaker values only count as conflict
OP_FACTOR = 0.5            # over/under observations
SOFT_LABEL_FACTOR = 0.5    # unsure rows and multi-fact false rows
REVERT_WINDOW_DAYS = 14
REVERT_LOOKBACK_DAYS = 30
REVERT_RATIO = 2.0
REVERT_MIN_DATES = 2       # a one-day stale nest is never a revert
ESTABLISHED_MIN_DATES = 3  # dates a value needs before a return to it is a revert

_ORDER_OPS = ("lt", "le", "gt", "ge")

# Durations convert within seconds-based units and within month-based units;
# months and years never convert to days (value-forms.md).
_DURATION_BASE = {
    "ms": ("sec", 1e-3), "s": ("sec", 1.0), "min": ("sec", 60.0), "h": ("sec", 3600.0),
    "day": ("sec", 86400.0), "week": ("sec", 604800.0),
    "month": ("month", 1.0), "year": ("month", 12.0),
}


# ---------------------------------------------------------------- values


def _num(x) -> float:
    return float(f"{float(x):.12g}")


def name_tokens(name: str, aliases: Optional[dict[str, str]] = None) -> tuple[str, ...]:
    """Lower-cased word tuple of a name, resolved through `aliases` when given."""
    norm = " ".join(str(name).split()).casefold()
    if aliases:
        norm = " ".join(aliases.get(norm, norm).split()).casefold()
    return tuple(norm.replace("-", " ").split())


def value_key(v: Value, aliases: Optional[dict[str, str]] = None) -> tuple:
    """Hashable key under which equal values (after unit conversion) collide.

    `op` is ignored: the key is that of the stated number.
    """
    k = v.kind
    if k == "quantity":
        dim = unit_dimension(v.unit)
        if dim:
            return ("quantity", dim[0], _num(v.value * dim[1]))
        return ("quantity", canonical_unit(v.unit), _num(v.value))
    if k == "duration":
        base, factor = _DURATION_BASE.get(v.unit, (v.unit, 1.0))
        return ("duration", base, _num(v.value * factor))
    if k == "money":
        return ("money", v.currency, v.per, _num(v.value))
    if k == "percent":
        return ("percent", _num(v.value))
    if k in ("date", "version"):
        return (k, str(v.value))
    if k == "boolean":
        return ("boolean", bool(v.value))
    if k == "name":
        return ("name", name_tokens(v.value, aliases))
    return (k, repr(v.value))


def _order_key(key: tuple):
    """(scale, magnitude) for ordered comparisons, None when unordered."""
    kind = key[0]
    if kind in ("quantity", "duration"):
        return (key[1], key[2])
    if kind == "money":
        return ((key[1], key[2]), key[3])
    if kind == "percent":
        return ("%", key[1])
    if kind == "version":
        try:
            return ("v", tuple(int(p) for p in key[1].split(".")))
        except ValueError:
            return None
    return None


def _date_cmp(cand: str, stated: str) -> int:
    """Compare a candidate date with a stated one at the stated precision."""
    c = cand[: len(stated)]
    return (c > stated) - (c < stated)


def _satisfies(cand_key: tuple, op: str, stated_key: tuple) -> bool:
    if cand_key[0] != stated_key[0]:
        return False
    if cand_key[0] == "date":
        c = _date_cmp(cand_key[1], stated_key[1])
    else:
        a, b = _order_key(cand_key), _order_key(stated_key)
        if a is None or b is None or a[0] != b[0]:
            return False
        c = (a[1] > b[1]) - (a[1] < b[1])
    return {"lt": c < 0, "le": c <= 0, "gt": c > 0, "ge": c >= 0}[op]


def _key_consistent(stated_key: tuple, op: Optional[str], cand_key: tuple) -> bool:
    if op in _ORDER_OPS:
        return _satisfies(cand_key, op, stated_key)
    if stated_key == cand_key:
        return True
    if stated_key[0] == "date" == cand_key[0]:
        return cand_key[1].startswith(stated_key[1] + "-")
    if stated_key[0] == "name" == cand_key[0]:
        s, c = stated_key[1], cand_key[1]
        return 0 < len(s) < len(c) and c[: len(s)] == s
    return False


def consistent(stated: Value, held: Value, aliases: Optional[dict[str, str]] = None) -> bool:
    """True when an observation stating `stated` agrees with `held` being the value.

    Equal after unit conversion; a coarser date covering a finer one
    (`2026-06` agrees with `2026-06-09`); a name that is a word prefix of the
    held name (`Gavin` agrees with `Gavin Bellson`); an `op` value the held
    value satisfies (`over 100` agrees with 120).
    """
    if stated.kind != held.kind:
        return False
    return _key_consistent(value_key(stated, aliases), stated.op, value_key(held, aliases))


def same_value(a: Value, b: Value, aliases: Optional[dict[str, str]] = None) -> bool:
    """Exact equality after unit conversion (B's copy of A's rule; deferred)."""
    return a.kind == b.kind and value_key(a, aliases) == value_key(b, aliases)


# ---------------------------------------------------------------- serialisation


def value_to_json(v: Value) -> dict:
    d = v.to_json()
    if v.op and v.op != "eq":
        d["op"] = v.op
    return d


def observation_to_json(o: Observation) -> dict:
    d = {
        "subject": o.subject, "attribute": o.attribute, "value": value_to_json(o.value),
        "date": o.date, "page_id": o.page_id, "row_id": o.row_id, "sentence": o.sentence,
        "subject_in_sentence": o.subject_in_sentence, "cues": sorted(o.cues),
    }
    if o.label is not None:
        d["label"] = o.label
    return d


def observation_from_json(d: dict) -> Observation:
    return Observation(
        subject=d["subject"], attribute=d["attribute"], value=Value.from_json(d["value"]),
        date=d["date"], page_id=d["page_id"], row_id=d["row_id"], sentence=d["sentence"],
        subject_in_sentence=d["subject_in_sentence"], cues=frozenset(d.get("cues", ())),
        label=d.get("label"),
    )


def load_seed(path: str = "data/baked/timelines_seed.json") -> list[Observation]:
    """The labelled practice observations baked by build/bake.py, in file order."""
    with open(baked_path(path), encoding="utf-8") as f:
        return [observation_from_json(d) for d in json.load(f)]


# ---------------------------------------------------------------- weights


def row_key(o: Observation) -> str:
    """Key of an observation's row in a weights dict (page ids never contain '#')."""
    return f"{o.page_id}#{o.row_id}"


def extraction_key(o: Observation) -> str:
    """Key of the extractor's precision for this kind of observation in a
    weights dict (`extract:<kind>:named|context`)."""
    return f"extract:{o.value.kind}:{'named' if o.subject_in_sentence else 'context'}"


def observation_weight(o: Observation, weights: dict[str, float], facts_in_row: int = 1) -> float:
    """Weight of one observation: its row's weight (else its page's, else 1.0),
    times the extractor's precision for an unlabelled observation of its kind
    (when known), halved for an `op` value, an unsure row, or a false row with
    several facts."""
    w = weights.get(row_key(o))
    if w is None:
        w = weights.get(o.page_id, 1.0)
    if o.label is None:
        w *= weights.get(extraction_key(o), 1.0)
    if o.value.op in _ORDER_OPS:
        w *= OP_FACTOR
    if o.label == "unsure" or (o.label == "false" and facts_in_row > 1):
        w *= SOFT_LABEL_FACTOR
    return w


# ---------------------------------------------------------------- build


def build(observations: list[Observation], weights: dict[str, float],
          aliases: Optional[dict[str, str]] = None) -> Timelines:
    """Merge observations into {(subject, attribute): [Interval, ...]}.

    weights: from reliability.page_weights (row keys, then page ids; missing
    means 1.0). aliases: optional lowercased name -> canonical map (the run-time
    Lexicon.aliases) so name values written as aliases collide.
    Pairs with no exact-valued observation (only `over N` and the like) get
    no timeline.
    """
    facts_in_row = Counter((o.page_id, o.row_id) for o in observations)
    by_pair: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for o in observations:
        by_pair[o.key()].append(o)
    out: Timelines = {}
    for key in sorted(by_pair):
        intervals = _build_pair(by_pair[key], weights, facts_in_row, aliases)
        if intervals:
            out[key] = intervals
    return out


class _Obs:
    __slots__ = ("o", "key", "op", "w", "role", "date")

    def __init__(self, o, key, w, role):
        self.o, self.key, self.w, self.role, self.date = o, key, w, role, o.date
        self.op = o.value.op if o.value.op in _ORDER_OPS else None


def _build_pair(obs_list, weights, facts_in_row, aliases) -> list[Interval]:
    obs = []
    for o in sorted(obs_list, key=lambda o: (o.date, o.page_id, o.row_id)):
        n_facts = facts_in_row[(o.page_id, o.row_id)]
        role = None
        if o.label == "true":
            role = "pin"
        elif o.label == "false" and n_facts == 1:
            role = "exclude"
        obs.append(_Obs(o, value_key(o.value, aliases), observation_weight(o, weights, n_facts), role))

    exact = [x for x in obs if x.op is None]
    if not exact:
        return []
    _merge_name_prefixes(exact)

    cands = _candidates(obs)
    if not cands:
        return []
    dates = sorted({x.date for x in obs})
    starts, values = _boundaries(obs, dates, _segment(obs, dates, cands, _change_costs(obs, cands)))
    return _intervals(obs, starts, values, obs_list[0])


def _merge_name_prefixes(exact: list[_Obs]) -> None:
    """Rewrite a name key that is a word prefix of a longer name key of the
    same pair to that longer key (the best-supported one)."""
    names = Counter()
    for x in exact:
        if x.key[0] == "name":
            names[x.key] += x.w
    if len(names) < 2:
        return
    target = {}
    for k in names:
        longer = [l for l in names if len(l[1]) > len(k[1]) and l[1][: len(k[1])] == k[1]]
        if longer:
            target[k] = min(longer, key=lambda l: (-names[l], -len(l[1]), repr(l)))
    for x in exact:
        k = x.key
        while k in target:
            k = target[k]
        x.key = k


def _score(x: _Obs, cand: tuple) -> float:
    """What observation x says about `cand` holding on its date.

    A labelled true row pins its value; a labelled true `over 100` names no
    value, so it only rules out the values it excludes and supports the rest
    at its plain weight. A false single-fact row rules out what it states."""
    if not _key_consistent(x.key, x.op, cand):
        return -ANCHOR_WEIGHT if x.role == "pin" and x.op else 0.0
    if x.role == "pin":
        return x.w if x.op else ANCHOR_WEIGHT
    if x.role == "exclude":
        return -ANCHOR_WEIGHT
    return x.w


def _candidates(obs: list[_Obs]) -> list[tuple[tuple, bool]]:
    """[(value key, is_revert)] in time order, one entry per episode of a value.

    A value's supporting dates split into episodes wherever another value is
    seen on at least REVERT_MIN_DATES dates in between. An episode that
    follows an established one (ESTABLISHED_MIN_DATES dates) is a revert and
    stays a candidate of its own only if it passes _revert_ok (plan rule 4);
    otherwise it is stale and only counts as conflict. An episode after a
    passing mention absorbs that mention. The strongest MAX_CANDIDATES
    episodes are ordered by weighted median date.
    """
    keys = sorted({x.key for x in obs if x.op is None}, key=repr)
    sup: dict[tuple, dict[str, float]] = {k: defaultdict(float) for k in keys}
    for x in obs:
        for k in keys:
            s = _score(x, k)
            if s > 0:
                sup[k][x.date] += s
    sorted_dates = {k: sorted(sup[k]) for k in keys}

    episodes = []
    for k in keys:
        kd = sorted_dates[k]
        if not kd:
            continue
        raw = [[kd[0]]]
        for a, b in zip(kd, kd[1:]):
            if _rival_dates(sorted_dates, k, a, b) >= REVERT_MIN_DATES:
                raw.append([])
            raw[-1].append(b)
        kept: list[list[str]] = []
        for ep in raw:
            if not kept:
                kept.append(ep)
            elif len(kept[-1]) < ESTABLISHED_MIN_DATES:
                kept[-1] = kept[-1] + ep
            elif _revert_ok(obs, k, ep):
                kept.append(ep)
            elif sum(sup[k][d] for d in ep) > sum(sup[k][d] for d in kept[-1]):
                kept[-1] = ep
        for n, ep in enumerate(kept):
            episodes.append((sum(sup[k][d] for d in ep), _weighted_median(ep, sup[k]), k, n > 0, len(ep)))

    episodes.sort(key=lambda e: (-e[0], e[1], repr(e[2])))
    episodes = sorted(episodes[:MAX_CANDIDATES], key=lambda e: (e[1], repr(e[2])))
    pinned = {x.key for x in obs if x.role == "pin" and x.op is None}
    return [_Cand(k, revert, n_dates, any(_key_consistent(p, None, k) for p in pinned))
            for _, _, k, revert, n_dates in episodes]


class _Cand:
    __slots__ = ("key", "revert", "n_dates", "pinned")

    def __init__(self, key, revert, n_dates, pinned):
        self.key, self.revert, self.n_dates, self.pinned = key, revert, n_dates, pinned


def _change_costs(obs: list[_Obs], cands: list[_Cand]) -> list[float]:
    """Cost of starting a segment of each candidate after another one.

    CHANGE_PENALTY, growing with the log of the pair's total weight
    (BIC-like), so in a dense pair a new value needs more than one sighting;
    REVERT_PENALTY_FACTOR times that to return to an earlier value. In a
    dense pair (DENSE_PAIR_WEIGHT) a new value seen on fewer than
    CHANGE_MIN_DATES days, and pinned by no labelled row, cannot start a
    segment: a one-day nest of stale pages must not become the current value.
    A sparse pair with labelled rows is deliberately not guarded: a change
    after the last labelled row is only ever seen in unlabelled text.
    """
    total = sum(x.w for x in obs)
    base = max(CHANGE_PENALTY, PENALTY_PER_LOG_WEIGHT * math.log1p(total))
    dense = total >= DENSE_PAIR_WEIGHT
    out = []
    for c in cands:
        if dense and c.n_dates < CHANGE_MIN_DATES and not c.pinned:
            out.append(float("inf"))
        else:
            out.append(base * (REVERT_PENALTY_FACTOR if c.revert else 1.0))
    return out


def _rival_dates(sorted_dates: dict[tuple, list[str]], k: tuple, a: str, b: str) -> int:
    """Most dates strictly between a and b on which one other value is seen."""
    best = 0
    for j, ds in sorted_dates.items():
        if j != k:
            best = max(best, bisect.bisect_left(ds, b) - bisect.bisect_right(ds, a))
    return best


def _revert_ok(obs: list[_Obs], k: tuple, ep: list[str]) -> bool:
    """The returning value, over its first REVERT_WINDOW_DAYS, has REVERT_RATIO
    times the support of every other value over the same window plus the
    REVERT_LOOKBACK_DAYS before it (a value still being said is not replaced
    by a few stale repeats), on at least REVERT_MIN_DATES dates."""
    lo, hi = ep[0], _shift(ep[0], REVERT_WINDOW_DAYS)
    back = _shift(ep[0], -REVERT_LOOKBACK_DAYS)
    mine, other, mine_dates = 0.0, 0.0, set()
    for x in obs:
        if not (back <= x.date < hi) or x.role == "exclude":
            continue
        s = _score(x, k)
        if s > 0:
            if x.date >= lo:
                mine += s
                mine_dates.add(x.date)
        else:
            other += ANCHOR_WEIGHT if x.role == "pin" else x.w
    return len(mine_dates) >= REVERT_MIN_DATES and mine >= REVERT_RATIO * other


def _weighted_median(dates: list[str], weight: dict[str, float]) -> str:
    half = sum(weight[d] for d in dates) / 2
    acc = 0.0
    for d in dates:
        acc += weight[d]
        if acc >= half:
            return d
    return dates[-1]


def _segment(obs, dates, cands: list[_Cand], cost: list[float]) -> list[tuple[int, int, tuple]]:
    """Best monotone segmentation: [(first date index, end index, value key)].

    cands are in time order. f[j][k]: best score of dates[:j] whose last
    segment holds cands[k]. A segment [i, j) holding k scores P[j][k] - P[i][k];
    every segment after the first pays cost[k] and must hold a later candidate.
    """
    keys = [c.key for c in cands]
    m, K = len(dates), len(cands)
    didx = {d: i for i, d in enumerate(dates)}
    S = [[0.0] * K for _ in range(m)]
    for x in obs:
        row = S[didx[x.date]]
        for k, c in enumerate(keys):
            row[k] += _score(x, c)
    P = [[0.0] * K]
    for r in S:
        P.append([a + b for a, b in zip(P[-1], r)])

    # a change is cheaper on a date where the new value is said many times
    # (launch day, price-change day): BURST_BONUS per unit of support beyond
    # the first observation, capped, so a lone mention gains nothing
    burst = [[BURST_BONUS * max(0.0, min(BURST_CAP, sum(x.w for x in on if _score(x, c) > 0)) - 1.0)
              for c in keys] for on in _by_date(obs, dates)]

    NEG = float("-inf")
    f = [[NEG] * K for _ in range(m + 1)]
    back: list[list[tuple[int, int]]] = [[(0, -1)] * K for _ in range(m + 1)]
    best = [0.0] * K           # max over admissible starts i of (g[i][k] - penalty - P[i][k])
    arg = [(0, -1)] * K        # start i = 0 with no previous segment scores 0
    for j in range(1, m + 1):
        i = j - 1
        if i >= 1:
            run, run_k = NEG, -1   # max over k' < k of f[i][k']
            for k in range(K):
                if run > NEG:
                    c = run - cost[k] + burst[i][k] - P[i][k]
                    if c > best[k] + 1e-12:
                        best[k], arg[k] = c, (i, run_k)
                if f[i][k] > run:
                    run, run_k = f[i][k], k
        for k in range(K):
            f[j][k] = P[j][k] + best[k]
            back[j][k] = arg[k]

    k = max(range(K), key=lambda k: (f[m][k], -k))
    segs = []
    j = m
    while True:
        i, kp = back[j][k]
        segs.append((i, j, k))
        if kp < 0:
            break
        j, k = i, kp
    segs.reverse()
    return [(i, j, keys[k]) for i, j, k in segs]


def _by_date(obs: list[_Obs], dates: list[str]) -> list[list[_Obs]]:
    idx = {d: i for i, d in enumerate(dates)}
    out: list[list[_Obs]] = [[] for _ in dates]
    for x in obs:
        out[idx[x.date]].append(x)
    return out


def _boundaries(obs, dates, segments) -> tuple[list[str], list[tuple]]:
    """Start date and value of each segment. A later segment starts at its
    first supporting observation; the first starts at the pair's first date."""
    starts, values = [], []
    for n, (i, j, cand) in enumerate(segments):
        start = dates[i]
        if n > 0:
            hi = dates[j] if j < len(dates) else None
            sup = [x.date for x in obs if x.date >= dates[i] and (hi is None or x.date < hi)
                   and _score(x, cand) > 0]
            start = min(sup, default=dates[i])
        starts.append(start)
        values.append(cand)
    return starts, values


def _shift(d: str, days: int) -> str:
    return (_date.fromisoformat(d) + timedelta(days=days)).isoformat()


def _intervals(obs, starts, values, sample: Observation) -> list[Interval]:
    out = []
    for n, (start, cand) in enumerate(zip(starts, values)):
        end = starts[n + 1] if n + 1 < len(starts) else None
        inside = [x for x in obs if x.date >= start and (end is None or x.date < end)]
        agree = [x for x in inside if _key_consistent(x.key, x.op, cand)]
        out.append(Interval(
            subject=sample.subject, attribute=sample.attribute,
            value=_representative(obs, cand),
            start=start, end=end,
            support=round(sum(x.w for x in agree), 6),
            conflict=round(sum(x.w for x in inside if not _key_consistent(x.key, x.op, cand)), 6),
            n_obs=len(agree),
            anchored=any(x.o.label == "true" and x.op is None for x in agree),
        ))
    return out


def _representative(obs: list[_Obs], cand: tuple) -> Value:
    """The written form of a candidate: its most-stated exact form; for a
    merged name, the longest one. Units become referee symbols."""
    forms = Counter()
    for x in obs:
        if x.op is None and x.key == cand:
            v = x.o.value
            forms[(v.kind, v.value, v.unit, v.currency, v.per)] += x.w
    if cand[0] == "name":
        best = max(forms, key=lambda f: (len(str(f[1]).split()), forms[f], str(f[1])))
    else:
        best = max(forms, key=lambda f: (forms[f], repr(f)))
    kind, value, unit, currency, per = best
    if kind == "quantity":
        unit = canonical_unit(unit)
    return Value(kind=kind, value=value, unit=unit, currency=currency, per=per)


# ---------------------------------------------------------------- queries


def _day_range(d: str) -> tuple[str, str]:
    if len(d) == 10:
        return d, d
    if len(d) == 7:
        y, m = int(d[:4]), int(d[5:7])
        return f"{d}-01", f"{d}-{calendar.monthrange(y, m)[1]:02d}"
    return f"{d}-01-01", f"{d}-12-31"


def value_at(intervals: list[Interval], date: str) -> Optional[Interval]:
    """The interval holding on `date` (YYYY-MM-DD), None before the first one.

    A month or year date (`2026-06`) answers only when one interval holds for
    the whole period.
    """
    if not intervals:
        return None
    lo, hi = _day_range(date)
    if lo != hi:
        a, b = value_at(intervals, lo), value_at(intervals, hi)
        return a if a is not None and a is b else None
    starts = [iv.start for iv in intervals]
    n = bisect.bisect_right(starts, lo) - 1
    if n < 0:
        return None
    iv = intervals[n]
    if iv.end is not None and lo >= iv.end:
        return None
    return iv


def current(intervals: list[Interval]) -> Optional[Interval]:
    """The interval holding on AS_OF_DATE."""
    return value_at(intervals, AS_OF_DATE)


def volatility(intervals: list[Interval]) -> int:
    """Number of intervals (distinct values the pair went through)."""
    return len(intervals)


def iter_intervals(timelines: Timelines) -> Iterable[Interval]:
    for key in sorted(timelines):
        yield from timelines[key]
