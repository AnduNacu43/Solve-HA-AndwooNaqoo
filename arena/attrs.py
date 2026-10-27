"""What kind of value each (subject, attribute) carries, learned from practice.

The lexicon names attributes but gives no kind or unit; data/baked/attrs.json
holds both, voted from the practice forms by build/bake.py. Units are stored as
practice writes them (`inch`, counted nouns such as `star`); canonical_unit()
maps a spelling to the referee's symbol (`inch` -> `in`).
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Optional

from arena.model import AttrSpec, Value

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def baked_path(path: str) -> str:
    """`path` as given if it exists (or is absolute), else relative to the
    repository root, so the default data/baked/... paths work from any cwd."""
    if os.path.isabs(path) or os.path.exists(path):
        return path
    return os.path.join(ROOT, path)

# Physical units by dimension, with the factor to the dimension's base unit.
# Mirrors contracts/value-forms.md "Quantity"; A's grammar has the same table
# (deferred: keep one copy after merge).
UNIT_DIMENSIONS: dict[str, tuple[str, float]] = {
    "B": ("data", 1.0), "KB": ("data", 1e3), "MB": ("data", 1e6),
    "GB": ("data", 1e9), "TB": ("data", 1e12),
    "mm": ("length", 1e-3), "cm": ("length", 1e-2), "m": ("length", 1.0),
    "km": ("length", 1e3), "in": ("length", 0.0254),
    "g": ("mass", 1.0), "kg": ("mass", 1e3),
    "mAh": ("charge", 1.0),
    "Hz": ("frequency", 1.0), "kHz": ("frequency", 1e3),
    "MHz": ("frequency", 1e6), "GHz": ("frequency", 1e9),
    "mW": ("power", 1e-3), "W": ("power", 1.0), "kW": ("power", 1e3),
}

# Lower-case spellings of the units above. Symbols are case-sensitive and are
# looked up in UNIT_DIMENSIONS first, so `m` stays a metre and `mW` a milliwatt.
_UNIT_SPELLINGS = {
    "b": "B", "byte": "B", "bytes": "B",
    "kb": "KB", "kilobyte": "KB", "mb": "MB", "megabyte": "MB",
    "gb": "GB", "gig": "GB", "gigabyte": "GB", "tb": "TB", "terabyte": "TB",
    "millimetre": "mm", "millimeter": "mm", "centimetre": "cm", "centimeter": "cm",
    "metre": "m", "meter": "m", "kilometre": "km", "kilometer": "km",
    "inch": "in", "inches": "in", '"': "in", "″": "in",
    "gram": "g", "gramme": "g", "kilogram": "kg", "kilo": "kg",
    "mah": "mAh", "hertz": "Hz", "khz": "kHz", "mhz": "MHz", "ghz": "GHz",
    "kilohertz": "kHz", "megahertz": "MHz", "gigahertz": "GHz",
    "milliwatt": "mW", "watt": "W", "kilowatt": "kW",
}


class AttrMap(dict):
    """dict[(subject, attribute)] -> AttrSpec, plus a by-attribute fallback."""

    def __init__(self, pairs=(), by_attribute: Optional[dict[str, AttrSpec]] = None):
        super().__init__(pairs)
        self.by_attribute: dict[str, AttrSpec] = dict(by_attribute or {})


def canonical_unit(unit: Optional[str]) -> Optional[str]:
    """Referee symbol for a unit spelling (`inch` -> `in`, `gb` -> `GB`).

    Counted nouns come back lower-cased and otherwise unchanged.
    """
    if unit is None or unit in UNIT_DIMENSIONS:
        return unit
    low = unit.lower()
    return _UNIT_SPELLINGS.get(low, low)


def unit_dimension(unit: Optional[str]) -> Optional[tuple[str, float]]:
    """(dimension, factor to base unit) for a physical unit, None for a counted noun."""
    return UNIT_DIMENSIONS.get(canonical_unit(unit) or "")


def spec_to_json(spec: AttrSpec) -> dict:
    d: dict = {"kind": spec.kind, "n_seen": spec.n_seen}
    if spec.unit is not None:
        d["unit"] = spec.unit
    if spec.currency is not None:
        d["currency"] = spec.currency
    if spec.per is not None:
        d["per"] = spec.per
    return d


def spec_from_json(d: dict) -> AttrSpec:
    return AttrSpec(kind=d["kind"], unit=d.get("unit"), currency=d.get("currency"),
                    per=d.get("per"), n_seen=d.get("n_seen", 0))


def load_attrs(path: str = "data/baked/attrs.json") -> dict[tuple[str, str], AttrSpec]:
    """Load the baked specs as {(subject, attribute): AttrSpec}.

    The returned mapping is an AttrMap (a dict) whose .by_attribute holds the
    majority spec per bare attribute name, used by spec_for() as a fallback.
    """
    with open(baked_path(path), encoding="utf-8") as f:
        data = json.load(f)
    pairs = {}
    for key, d in data["pairs"].items():
        subject, attribute = key.rsplit("|", 1)
        pairs[(subject, attribute)] = spec_from_json(d)
    by_attr = {a: spec_from_json(d) for a, d in data.get("by_attribute", {}).items()}
    return AttrMap(pairs, by_attr)


def spec_for(attrs, subject: str, attribute: str) -> Optional[AttrSpec]:
    """Spec for (subject, attribute): the exact pair first, then the same
    attribute name on any subject (the most-seen one), else None."""
    spec = attrs.get((subject, attribute))
    if spec is not None:
        return spec
    by_attr = getattr(attrs, "by_attribute", None)
    if by_attr is not None:
        return by_attr.get(attribute)
    best = None
    for (_, a), s in attrs.items():
        if a == attribute and (best is None or s.n_seen > best.n_seen):
            best = s
    return best


def infer_spec(values: list[Value]) -> AttrSpec:
    """Majority kind, then majority unit/currency/period within that kind,
    for an attribute the baked file has never seen. Raises on an empty list."""
    if not values:
        raise ValueError("infer_spec needs at least one value")
    kind = _majority(v.kind for v in values)
    same = [v for v in values if v.kind == kind]
    unit = currency = per = None
    if kind in ("quantity", "duration"):
        unit = _majority(v.unit for v in same)
    if kind == "money":
        currency = _majority(v.currency for v in same)
        per = _majority(v.per for v in same)
    return AttrSpec(kind=kind, unit=unit, currency=currency, per=per, n_seen=len(values))


def _majority(items):
    counts = Counter(items)
    # most common; ties broken by the smallest repr so the vote is deterministic
    return min(counts, key=lambda x: (-counts[x], repr(x)))
