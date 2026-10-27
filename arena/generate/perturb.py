"""False values for a fact: perturbed ones the universe never states for the
pair, and stale ones it stated before the current value replaced them."""
from __future__ import annotations

import math
from typing import Iterator, Optional

from arena.generate import deps
from arena.generate.common import contains, stable_hash
from arena.model import Interval, Value

ROUNDING = {"money": 2, "percent": 3}


def _decimals(x: float) -> int:
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return len(s.split(".")[1]) if "." in s else 0


def _nice_above(x: float) -> float:
    """The next round number above x: 12 -> 20, 59 -> 60, 4 -> 5."""
    if x <= 0:
        return 1.0
    m = 10 ** math.floor(math.log10(x))
    nice = math.ceil(x / m) * m
    return float(nice if nice != x else x + m)


def _numeric(v: Value) -> list[Value]:
    x = float(v.value)
    whole = x.is_integer()
    if v.kind == "percent":
        raw = [x - 1, x / 2, x + 1, round(x) + 5] if x >= 50 else [x * 2, x / 2, x + 1, x + 10]
        raw = [r for r in raw if 0 < r <= 100]
    else:
        raw = [_nice_above(x), x * 2, x / 2, x + 1]
    out = []
    for r in raw:
        if whole and v.kind != "percent":
            r = float(round(r))
        else:
            r = round(r, max(_decimals(x), 1) if v.kind != "money" else 2)
        if r < 0 or (v.kind != "percent" and r == 0) or r == x:
            continue
        if whole and v.kind in ("quantity", "duration") and not float(r).is_integer():
            continue
        out.append(Value(v.kind, int(r) if float(r).is_integer() else r,
                         v.unit, v.currency, v.per))
    return out


def _shift_month(y: int, m: int, by: int) -> tuple[int, int]:
    m0 = (m - 1) + by
    return y + m0 // 12, m0 % 12 + 1


def _date(v: Value) -> list[Value]:
    parts = str(v.value).split("-")
    y = int(parts[0])
    if len(parts) == 1:
        return [Value("date", str(y + 1)), Value("date", str(y - 1))]
    m = int(parts[1])
    out = []
    for by in (1, -1):
        yy, mm = _shift_month(y, m, by)
        if len(parts) == 2:
            out.append(Value("date", f"{yy:04d}-{mm:02d}"))
        else:
            d = min(int(parts[2]), 28)
            out.append(Value("date", f"{yy:04d}-{mm:02d}-{d:02d}"))
    return out


def _version(v: Value) -> list[Value]:
    parts = [int(p) for p in str(v.value).split(".")]
    out = []
    up = parts[:-1] + [parts[-1] + 1]
    out.append(Value("version", ".".join(map(str, up))))
    if parts[-1] > 0:
        out.append(Value("version", ".".join(map(str, parts[:-1] + [parts[-1] - 1]))))
    if len(parts) > 1:
        out.append(Value("version", ".".join(map(str, [parts[0] + 1] + [0] * (len(parts) - 1)))))
    return out


def name_pool(subject: str, attribute: str, value: Value, timelines, lexicon) -> list[str]:
    """Other names of the same type: values of the same attribute on other
    subjects, then lexicon subjects whose attributes resemble the true value's."""
    pool: list[str] = []
    for (s, a), intervals in timelines.items():
        if a == attribute and s != subject:
            for iv in intervals:
                if iv.value.kind == "name" and iv.value.value not in pool:
                    pool.append(iv.value.value)
    target = lexicon.resolve(value.value)
    if target:
        mine = set(lexicon.subjects.get(target, []))
        for other, attrs in sorted(lexicon.subjects.items()):
            if other in (target, subject) or other in lexicon.events:
                continue
            theirs = set(attrs)
            if mine and theirs and len(mine & theirs) / len(mine | theirs) >= 0.5:
                if other not in pool:
                    pool.append(other)
    return [n for n in pool if lexicon.resolve(n) != lexicon.resolve(subject)]


def perturbed_values(subject: str, attribute: str, value: Value, seen: list[Value],
                     timelines, lexicon) -> list[Value]:
    """Values of the same kind, unit, currency and period that the pair never held,
    in a stable order that varies by pair."""
    k = value.kind
    if k in ("quantity", "money", "percent", "duration"):
        cands = _numeric(value)
    elif k == "date":
        cands = _date(value)
    elif k == "version":
        cands = _version(value)
    elif k == "name":
        cands = [Value("name", n) for n in name_pool(subject, attribute, value, timelines, lexicon)]
    elif k == "boolean":
        cands = [Value("boolean", not value.value)]
    else:
        cands = []
    out = []
    for c in cands:
        if contains(seen, c) or contains(out, c):
            continue
        if k != "boolean":
            try:
                deps.format_value(c)
            except (ValueError, KeyError, IndexError, TypeError):
                continue
        out.append(c)
    if len(out) > 1 and k != "name":
        r = stable_hash(subject, attribute) % len(out)
        out = out[r:] + out[:r]
    return out


def stale_intervals(intervals: list[Interval], cur: Interval) -> list[Interval]:
    """Superseded intervals whose value differs from the current one, latest first."""
    out: list[Interval] = []
    for iv in reversed(intervals):
        if iv is cur or iv.start >= cur.start or deps.same_value(iv.value, cur.value):
            continue
        if not contains([o.value for o in out], iv.value):
            out.append(iv)
    return out


def false_values(subject: str, attribute: str, intervals: list[Interval],
                 cur: Interval, timelines, lexicon) -> Iterator[tuple[Value, bool, Optional[Interval]]]:
    """(value, perturbed, stale_interval) for false as-of claims: one perturbed,
    then the latest stale value, then the remaining perturbed ones."""
    seen = [iv.value for iv in intervals]
    perturbed = perturbed_values(subject, attribute, cur.value, seen, timelines, lexicon)
    stale = stale_intervals(intervals, cur)
    if perturbed:
        yield perturbed[0], True, None
    for iv in stale[:1]:
        yield iv.value, False, iv
    for v in perturbed[1:]:
        yield v, True, None
    for iv in stale[1:]:
        yield iv.value, False, iv
