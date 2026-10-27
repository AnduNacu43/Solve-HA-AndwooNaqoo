"""Stub of A's arena.grammar (values, sentences, claims) for C's tests and the
pre-merge image: format_value, same_value, compare_values, attribute_words and
the word lists of claim-forms.md. Good enough for the kinds practice holds."""
from __future__ import annotations

import re
from typing import Literal, Optional

from arena.model import Value

NEGATION_WORDS = frozenset(
    "not no never none nobody nothing neither nor without cannot".split()
)
TIME_WORDS = frozenset([
    "ago", "yesterday", "tomorrow", "once", "formerly", "previously", "originally",
    "initially", "recently", "lately", "soon", "eventually", "then", "before",
    "after", "since", "until", "till", "earlier", "later", "used to", "last week",
    "last month", "last quarter", "last year", "next week", "next month",
    "next quarter", "next year", "in the past", "in the future", "at the time",
    "at that time",
])
MONTH_WORDS = frozenset([
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "spring", "summer", "autumn",
    "winter", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
])
NUMBER_WORDS = frozenset(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty "
    "sixty seventy eighty ninety hundred dozen thousand million billion".split()
)

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

_UNIT_ALIASES = {
    "inch": "in", "inches": "in", '"': "in", "gb": "GB", "gigabyte": "GB",
    "mb": "MB", "megabyte": "MB", "tb": "TB", "terabyte": "TB", "kb": "KB",
    "byte": "B", "gram": "g", "kilogram": "kg", "kilo": "kg", "metre": "m",
    "meter": "m", "kilometre": "km", "kilometer": "km", "watt": "W",
    "hertz": "Hz", "gigahertz": "GHz", "megahertz": "MHz",
}
_DIMENSIONS = [
    {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12},
    {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "km": 1e3, "in": 0.0254},
    {"g": 1.0, "kg": 1e3},
    {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9},
    {"mW": 1e-3, "W": 1.0, "kW": 1e3},
    {"mAh": 1.0},
]
_DURATION_DIMS = [
    {"ms": 1e-3, "s": 1.0, "min": 60.0, "h": 3600.0, "day": 86400.0, "week": 604800.0},
    {"month": 1.0, "year": 12.0},
]
_DURATION_WORDS = {"ms": ("ms", "ms"), "s": ("second", "seconds"),
                   "min": ("minute", "minutes"), "h": ("hour", "hours"),
                   "day": ("day", "days"), "week": ("week", "weeks"),
                   "month": ("month", "months"), "year": ("year", "years")}
_CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
_ACRONYMS = {"soc2": "SOC 2", "eu": "EU", "sso": "SSO", "api": "API", "ar": "AR",
             "ai": "AI", "cli": "CLI", "ceo": "CEO", "cto": "CTO", "sla": "SLA",
             "sdk": "SDK", "sdks": "SDKs", "ide": "IDE", "ides": "IDEs", "a": "A"}


def canonical_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    return _UNIT_ALIASES.get(unit, _UNIT_ALIASES.get(unit.lower(), unit))


def _number(x: float, three_decimals_ok: bool = False) -> str:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"not a number: {x!r}")
    if float(x).is_integer():
        return f"{int(round(x)):,}"
    s = f"{x:,.6f}".rstrip("0").rstrip(".")
    if len(s.split(".")[1]) == 3 and not three_decimals_ok:
        raise ValueError(f"{s} reads as ambiguous")
    return s


def _plural(noun: str) -> str:
    if noun == "person":
        return "people"
    if re.search(r"[^aeiou]y$", noun):
        return noun[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", noun):
        return noun + "es"
    return noun + "s"


def format_value(v: Value) -> str:
    """Canonical written form the referee reads back as exactly v."""
    k = v.kind
    if k == "money":
        if v.value < 0:
            raise ValueError("negative money")
        amount = (f"{int(round(v.value)):,}" if float(v.value).is_integer()
                  else f"{v.value:,.2f}")
        sym = _CURRENCY_SYMBOLS.get(v.currency)
        text = f"{sym}{amount}" if sym else f"{v.currency} {amount}"
        return f"{text} per {v.per}" if v.per else text
    if k == "quantity":
        unit = canonical_unit(v.unit)
        n = _number(v.value)
        if unit == "in":
            return f"{n}-inch"
        if any(unit in d for d in _DIMENSIONS):
            return f"{n} {unit}"
        return f"{n} {unit if v.value == 1 else _plural(unit)}"
    if k == "percent":
        return f"{_number(v.value, three_decimals_ok=True)}%"
    if k == "date":
        parts = str(v.value).split("-")
        if len(parts) == 1:
            return parts[0]
        month = MONTHS[int(parts[1]) - 1]
        if len(parts) == 2:
            return f"{month} {parts[0]}"
        return f"{int(parts[2])} {month} {parts[0]}"
    if k == "version":
        return f"v{v.value}"
    if k == "duration":
        one, many = _DURATION_WORDS[v.unit]
        return f"{_number(v.value)} {one if v.value == 1 else many}"
    if k == "name":
        return str(v.value)
    raise ValueError(f"{k} has no written value; use attribute words")


def attribute_words(attr: str) -> str:
    """soc2_certified -> "SOC 2 certified"."""
    return " ".join(_ACRONYMS.get(w, w) for w in attr.split("_"))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _order(a: float, b: float) -> Literal["gt", "lt", "eq"]:
    if _close(a, b):
        return "eq"
    return "gt" if a > b else "lt"


def _in_dims(dims, ua, ub):
    for d in dims:
        if ua in d and ub in d:
            return d
    return None


def compare_values(a: Value, b: Value) -> Optional[Literal["gt", "lt", "eq"]]:
    """None when not comparable (names, booleans, other currency/period/precision)."""
    if a.kind != b.kind or a.kind in ("name", "boolean"):
        return None
    if a.kind == "money":
        if a.currency != b.currency or a.per != b.per:
            return None
        return _order(a.value, b.value)
    if a.kind == "percent":
        return _order(a.value, b.value)
    if a.kind == "quantity":
        ua, ub = canonical_unit(a.unit), canonical_unit(b.unit)
        d = _in_dims(_DIMENSIONS, ua, ub)
        if d:
            return _order(a.value * d[ua], b.value * d[ub])
        if ua.lower() == ub.lower() and not any(ua in x for x in _DIMENSIONS):
            return _order(a.value, b.value)
        return None
    if a.kind == "duration":
        d = _in_dims(_DURATION_DIMS, a.unit, b.unit)
        return _order(a.value * d[a.unit], b.value * d[b.unit]) if d else None
    if a.kind == "date":
        if len(str(a.value)) != len(str(b.value)):
            return None
        return "eq" if a.value == b.value else ("gt" if a.value > b.value else "lt")
    if a.kind == "version":
        pa = [int(x) for x in str(a.value).split(".")]
        pb = [int(x) for x in str(b.value).split(".")]
        n = max(len(pa), len(pb))
        pa, pb = pa + [0] * (n - len(pa)), pb + [0] * (n - len(pb))
        if pa == pb:
            return "eq" if a.value == b.value else None
        return "gt" if pa > pb else "lt"
    return None


def same_value(a: Value, b: Value) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == "name":
        return re.sub(r"\s+", "", str(a.value)).lower() == re.sub(r"\s+", "", str(b.value)).lower()
    if a.kind == "boolean":
        return a.value == b.value
    return compare_values(a, b) == "eq"
