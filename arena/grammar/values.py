"""Value grammar of contracts/value-forms.md: read values from text, write them back.

parse_values() reads every value a sentence states, with its flags; forms the
contract calls ambiguous (`99,9`, `1.500`, `12/03/2026`, `Q4 2026` ...) read as
nothing. format_value() writes a Value in a form parse_values reads back as
exactly that value. same_value() and compare_values() apply the referee's unit
conversions.

read() is the richer reading the validator uses: besides the value it keeps
where the number starts and every counted noun the value could be read with
(`1,200 paying customers` can state customers; up to two words may sit between
a number and its noun).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date as _date
from typing import Literal, Optional

from arena.grammar import sentences as S
from arena.model import ParsedValue, Value

# ------------------------------------------------------------------ tables

INVISIBLE = "​‌‍⁠﻿­᠎⁡⁢⁣⁤"
_SPACES = "           "

ISO_CURRENCIES = (
    "EUR", "USD", "GBP", "CHF", "RON", "PLN", "CZK", "HUF", "SEK", "NOK", "DKK", "JPY", "CNY",
    "INR", "CAD", "AUD",
)
_SYMBOL_CURRENCY = {"US$": "USD", "€": "EUR", "$": "USD", "£": "GBP"}
_WORD_CURRENCY = {"euro": "EUR", "euros": "EUR", "dollar": "USD", "dollars": "USD", "lei": "RON"}
_CURRENCY_SYMBOL_OUT = {"EUR": "€", "USD": "$", "GBP": "£"}

# Physical units: exact symbols (case carries meaning) and words (any case).
_PHYS_SYMBOLS = {
    "B": "B", "KB": "KB", "kB": "KB", "kb": "KB", "MB": "MB", "mb": "MB", "GB": "GB", "gb": "GB",
    "TB": "TB", "tb": "TB", "mm": "mm", "cm": "cm", "m": "m", "km": "km", "in": "in",
    "g": "g", "kg": "kg", "mAh": "mAh", "Hz": "Hz", "kHz": "kHz", "MHz": "MHz", "GHz": "GHz",
    "mW": "mW", "W": "W", "kW": "kW",
}
_PHYS_WORDS = {
    "byte": "B", "kilobyte": "KB", "megabyte": "MB", "gigabyte": "GB", "gig": "GB", "terabyte": "TB",
    "millimetre": "mm", "millimeter": "mm", "centimetre": "cm", "centimeter": "cm",
    "metre": "m", "meter": "m", "kilometre": "km", "kilometer": "km", "inch": "in",
    "gram": "g", "gramme": "g", "kilogram": "kg", "kilo": "kg",
    "hertz": "Hz", "kilohertz": "kHz", "megahertz": "MHz", "gigahertz": "GHz",
    "milliwatt": "mW", "watt": "W", "kilowatt": "kW",
}
_PHYS_DIM = {
    "B": ("data", 1.0), "KB": ("data", 1e3), "MB": ("data", 1e6), "GB": ("data", 1e9), "TB": ("data", 1e12),
    "mm": ("length", 1e-3), "cm": ("length", 1e-2), "m": ("length", 1.0), "km": ("length", 1e3),
    "in": ("length", 0.0254), "g": ("mass", 1.0), "kg": ("mass", 1e3), "mAh": ("charge", 1.0),
    "Hz": ("frequency", 1.0), "kHz": ("frequency", 1e3), "MHz": ("frequency", 1e6), "GHz": ("frequency", 1e9),
    "mW": ("power", 1e-3), "W": ("power", 1.0), "kW": ("power", 1e3),
}

# Duration units: written form -> (unit, multiplier). Single letters are lower case only.
_DUR_SYMBOLS = {"ms": ("ms", 1), "s": ("s", 1), "h": ("h", 1), "d": ("day", 1)}
_DUR_WORDS = {
    "millisecond": ("ms", 1), "second": ("s", 1), "sec": ("s", 1), "minute": ("min", 1), "min": ("min", 1),
    "hour": ("h", 1), "hr": ("h", 1), "day": ("day", 1), "week": ("week", 1), "wk": ("week", 1),
    "fortnight": ("week", 2), "month": ("month", 1), "mo": ("month", 1), "mth": ("month", 1),
    "year": ("year", 1), "yr": ("year", 1), "decade": ("year", 10),
}
_DUR_SECONDS = {"ms": 0.001, "s": 1.0, "min": 60.0, "h": 3600.0, "day": 86400.0, "week": 604800.0}
_DUR_MONTHS = {"month": 1.0, "year": 12.0}
_DUR_OUT = {"ms": ("ms", "ms"), "s": ("second", "seconds"), "min": ("minute", "minutes"),
            "h": ("hour", "hours"), "day": ("day", "days"), "week": ("week", "weeks"),
            "month": ("month", "months"), "year": ("year", "years")}
_DURATION_WORDS = frozenset(
    list(_DUR_WORDS) + [w + "s" for w in _DUR_WORDS] + ["ms", "hrs", "mins", "secs", "mths", "yrs", "wks"]
)

_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December"]

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen"]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_ONES_VAL = {w: i for i, w in enumerate(_ONES)}
_TENS_VAL = {w: 20 + 10 * i for i, w in enumerate(_TENS)}

IRREGULAR_PLURALS = {
    "people": "person", "children": "child", "men": "man", "women": "woman", "feet": "foot",
    "teeth": "tooth", "mice": "mouse", "geese": "goose", "criteria": "criterion",
}
_INVARIANT = frozenset({"series", "species", "data", "media", "news"})

# Words that are never the counted noun of a number.
FUNCTION_WORDS = frozenset(
    """a an the of our your their its his her my these those this that which who whom whose and or
    but nor in on at to for by with from per into onto over under than as is are was were be been
    being has have had do does did will would can could may might must shall should so too very more
    most less least all each every other another such out up down off about around just only also
    still now then there here it they we you he she them us him me i am pm not no plus times via
    across between among within without inside outside since until after before while when where
    what how why if yet already even again ever""".split()
)

# ------------------------------------------------------------------ regexes

def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


def _with_plurals(words) -> list[str]:
    out = []
    for w in words:
        out.append(w)
        if w in ("hertz", "kilohertz", "megahertz", "gigahertz"):
            continue
        out.append(w + "es" if w.endswith("ch") else w + "s")
    return out


_NUM_RUN = re.compile(r"(?<![A-Za-z0-9_.,])\d+(?:[.,]\d+)*")
_NUMWORD = re.compile(
    r"(?<![A-Za-z-])(?:(?P<h>a|one|two|three|four|five|six|seven|eight|nine)\s+hundred"
    r"|(?P<dz>a)\s+dozen"
    r"|(?P<t>" + _alt(_TENS) + r")(?:[-\s](?P<tu>" + _alt(_ONES[1:10]) + r"))?"
    r"|(?P<u>" + _alt(_ONES) + r"))(?![A-Za-z])",
    re.I,
)
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_DECIMAL_COMMA = re.compile(r"\d+,\d{1,2}")
_THREE_DECIMALS = re.compile(r"[\d,]*\.\d{3}")
_MULTI_DOT = re.compile(r"\d+(?:\.\d+){2,}")

_SCALE = re.compile(
    r"\s*(?P<w>(?i:thousand|million|billion))s?(?![A-Za-z])"
    r"|\s?(?P<bn>(?i:bn))(?![A-Za-z])"
    r"|(?P<M>M)(?![A-Za-z])"
    r"|(?P<k>k)(?![A-Za-z])"
)
_SCALE_VAL = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "bn": 1e9, "M": 1e6, "k": 1e3}

_PERCENT = re.compile(r"\s*(?:%|(?i:per\s*cent|percent)(?![A-Za-z]))")
_CUR_SUFFIX = re.compile(
    r"\s*(?:(?P<sym>US\$|€|\$|£)"
    r"|(?P<iso>" + _alt(ISO_CURRENCIES) + r")(?![A-Za-z])"
    r"|(?P<word>(?i:euros?|dollars?|lei))(?![A-Za-z]))"
)
_CUR_PREFIX = re.compile(
    r"(?:(?P<sym>US\$|€|\$|£)|(?<![A-Za-z])(?P<iso>" + _alt(ISO_CURRENCIES) + r"))\s*$"
)
_PERIOD = re.compile(
    r"(?:\s*(?:per\s+(?:user|seat|person|member)|/\s*(?:user|seat)))?"
    r"(?:\s*/\s*(?P<slash>month|mo|day|week|wk|year|yr)(?![A-Za-z])"
    r"|\s+(?:a|per)\s+(?P<per>month|day|week|year)(?![A-Za-z])"
    r"|\s+(?P<adv>monthly|daily|weekly|yearly|annually)(?![A-Za-z])"
    r"|\s+per\s+(?P<annum>annum)(?![A-Za-z]))",
    re.I,
)
_PERIOD_CANON = {"month": "month", "mo": "month", "monthly": "month", "day": "day", "daily": "day",
                 "week": "week", "wk": "week", "weekly": "week", "year": "year", "yr": "year",
                 "yearly": "year", "annually": "year", "annum": "year"}

_PHYS = re.compile(
    r"(?P<sep>-|\s*)(?:(?P<sym>" + _alt(_PHYS_SYMBOLS) + r")(?![A-Za-z0-9])"
    r"|(?P<word>(?i:" + _alt(_with_plurals(_PHYS_WORDS)) + r"))(?![A-Za-z]))"
)
_DUR = re.compile(
    r"(?P<sep>-|\s*)(?:(?P<sym>ms|s|h|d)(?![A-Za-z0-9])"
    r"|(?P<word>(?i:" + _alt(_with_plurals(_DUR_WORDS)) + r"))(?![A-Za-z]))"
)
_A_DURATION = re.compile(
    r"(?<![A-Za-z])(?:under|within|in|for|over|than|at\s+least|at\s+most|to|only|just|about|around)"
    r"\s+(?P<a>an?)\s+(?P<u>millisecond|second|sec|minute|min|hour|hr|day|week|fortnight|month|year|decade)(?![A-Za-z])",
    re.I,
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*[A-Za-z]|[A-Za-z]")
_GAP = re.compile(r"[ \t]+")

_MONTH_ALT = (
    r"(?P<mon>January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Sept|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?![A-Za-z])\.?"
)
_ORD = r"(?:st|nd|rd|th)?"
_DATE_PATTERNS = [
    re.compile(r"(?<![\d-])(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?![\d-])"),
    re.compile(r"(?<![\d-])(?P<y>\d{4})-(?P<m>\d{2})(?![\d-])"),
    re.compile(r"(?<![A-Za-z0-9])(?:the\s+)?(?P<d>\d{1,2})" + _ORD + r"\s*(?:of\s+)?" + _MONTH_ALT
               + r",?\s*(?P<y>\d{4})(?!\d)", re.I),
    re.compile(r"(?<![A-Za-z])" + _MONTH_ALT + r"\s*(?P<d>\d{1,2})" + _ORD + r",?\s+(?P<y>\d{4})(?!\d)", re.I),
    re.compile(r"(?<![A-Za-z])" + _MONTH_ALT + r",?\s+(?P<y>\d{4})(?!\d)", re.I),
]
# Forms that read as nothing and must not leave readable pieces behind.
_BLOCKERS = [
    re.compile(r"(?<![\dA-Za-z])\d{1,4}[./-]\d{1,2}[./-]\d{2,4}(?![\d])"),  # 12/03/2026, 12.03.2026
    re.compile(r"(?<![A-Za-z0-9])[QH][1-4]\s*(?:\d{4})?(?![A-Za-z0-9])"),  # Q4 2026, H1
    re.compile(r"(?<![A-Za-z])" + _MONTH_ALT + r"\s*\d{1,2}" + _ORD + r"(?![\d])", re.I),  # March 12
    re.compile(r"(?<![A-Za-z0-9])\d{1,2}" + _ORD + r"\s*(?:of\s+)?" + _MONTH_ALT, re.I),  # 12 March
    re.compile(r"(?<![A-Za-z0-9])\d+(?:st|nd|rd|th)(?![A-Za-z])", re.I),  # ordinals
    re.compile(r"(?<![\d])\d{1,2}:\d{2}(?![\d])"),  # 10:30
    re.compile(r"(?<![\d.,])\d+/\d+(?![\d])"),  # 24/7, 1/2
    re.compile(r"(?<![A-Za-z])half\s+an?\s+[A-Za-z]+", re.I),  # half an hour
]
_VERSION_V = re.compile(r"(?<![A-Za-z0-9])[vV](?P<n>\d+(?:\.\d+){0,3})(?!\.?\d)(?![A-Za-z])")
_VERSION_WORD = re.compile(r"(?<![A-Za-z])(?i:version|ver\.?)\s*(?P<n>\d+(?:\.\d+){0,3})(?!\.?\d)(?![A-Za-z])")
_CAP_NAME_BEFORE = re.compile(r"(?<![A-Za-z0-9])(?P<w>[A-Z][A-Za-z0-9/&+'-]*) $")
_NOT_NAMES = frozenset(
    """At In On By For To The A An Of With From Over Under Up About Around And Or Now Only Just Since
    Until After Before Is Was Are Were Has Have It Its Our We They This That These Those Than Then
    Each Every Some All Top Only Just Nearly Almost Roughly Approx Approximately Version Ver""".split()
)

# Comparison and approximation words around a value (value-forms.md, "Comparisons").
_OPS_BEFORE = [
    ("no more than", "le"), ("not more than", "le"), ("no less than", "ge"), ("not less than", "ge"),
    ("no fewer than", "ge"), ("in excess of", "gt"), ("upwards of", "gt"), ("more than", "gt"),
    ("greater than", "gt"), ("higher than", "gt"), ("less than", "lt"), ("fewer than", "lt"),
    ("lower than", "lt"), ("up to", "le"), ("at most", "le"), ("at least", "ge"),
    ("starting at", "eq"), ("exceeding", "gt"), ("maximum", "le"), ("minimum", "ge"),
    ("above", "gt"), ("below", "lt"), ("over", "gt"), ("under", "lt"), ("max.", "le"), ("max", "le"),
    ("only", "eq"), ("just", "eq"), ("from", "eq"),
]
_DATE_OPS_BEFORE = [("no later than", "le"), ("no earlier than", "ge"), ("prior to", "lt"),
                    ("before", "lt"), ("after", "gt"), ("by", "le"), ("from", "eq"), ("only", "eq")]
_APPROX_BEFORE = ["more or less", "approximately", "close to", "estimated", "roughly", "approx.",
                  "approx", "nearly", "almost", "around", "circa", "about", "some", "est.", "est",
                  "ca.", "ca"]


def _before_re(phrases) -> re.Pattern:
    return re.compile(
        r"(?<![A-Za-z])(?P<p>" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases) + r")\s*$",
        re.I,
    )


_OPS_BEFORE_RE = _before_re([p for p, _ in sorted(_OPS_BEFORE, key=lambda x: -len(x[0]))])
_OPS_BEFORE_MAP = {p: o for p, o in _OPS_BEFORE}
_DATE_OPS_BEFORE_RE = _before_re([p for p, _ in sorted(_DATE_OPS_BEFORE, key=lambda x: -len(x[0]))])
_DATE_OPS_BEFORE_MAP = {p: o for p, o in _DATE_OPS_BEFORE}
_WITHIN_RE = _before_re(["within"])
_APPROX_BEFORE_RE = re.compile(
    r"(?:(?<![A-Za-z])(?:" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in _APPROX_BEFORE)
    + r")\s*|[~≈±]\s*)$",
    re.I,
)
_OPS_AFTER = re.compile(
    r"\s+or\s+(?P<le>less|fewer|under|below|lower|shorter)(?![A-Za-z])"
    r"|\s+or\s+(?P<ge>more|higher|above|longer|over)(?![A-Za-z])",
    re.I,
)
_APPROX_AFTER = re.compile(r"\s+or\s+so(?![A-Za-z])|,?\s+give\s+or\s+take(?![A-Za-z])|-ish(?![A-Za-z])", re.I)
_RANGE_GAP = re.compile(r"^\s*(?P<j>[-–—]|to|or|and)\s*$", re.I)
_BARE_BEFORE = re.compile(
    r"(?P<n>(?<![A-Za-z0-9_.,])\d+(?:[.,]\d+)*|(?<![A-Za-z])(?:" + _alt(_TENS + _ONES) + r"))"
    r"\s*(?P<j>[-–—]|to|or|and)\s*(?:US\$|€|\$|£)?\s*$",
    re.I,
)

# ------------------------------------------------------------------ readings


@dataclass
class Reading:
    """One value read from a sentence, with what the validator needs to know.

    start/end span the whole written value (currency, unit, `v`), num_start is
    where its number starts, and nouns are the singular counted nouns it can be
    read with (empty for anything but a counted quantity).
    """

    value: Value
    start: int
    end: int
    num_start: int
    negated: bool = False
    approximate: bool = False
    range_end: bool = False
    nouns: tuple[str, ...] = ()

    @property
    def plain(self) -> bool:
        """Read as stated: no comparison word, approximation, range or negation."""
        return self.value.op is None and not (self.negated or self.approximate or self.range_end)


@dataclass
class _Cand:
    kind: str
    value: object
    start: int
    end: int
    num_start: int
    unit: Optional[str] = None
    currency: Optional[str] = None
    per: Optional[str] = None
    op: Optional[str] = None
    approx: bool = False
    range_end: bool = False
    nouns: tuple[str, ...] = ()


def _normalize(s: str) -> tuple[str, list[int]]:
    """Drop soft hyphens between letters, unify spaces and apostrophes; keep an offset map."""
    out: list[str] = []
    idx: list[int] = []
    n = len(s)
    for i, c in enumerate(s):
        if c == "­" and 0 < i < n - 1 and s[i - 1].isalpha() and s[i + 1].isalpha():
            continue
        if c in _SPACES:
            c = " "
        elif c == "’" or c == "‘":
            c = "'"
        out.append(c)
        idx.append(i)
    idx.append(n)
    return "".join(out), idx


def singular(word: str) -> str:
    """The singular of a counted noun, lower case (`companies` -> `company`)."""
    w = word.lower()
    if w in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[w]
    if w in _INVARIANT:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("sses", "shes", "ches", "xes", "zzes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 2:
        return w[:-1]
    return w


def plural(noun: str) -> str:
    """The plural singular() reads back as noun (`person` -> `people`)."""
    w = noun
    for p, s in IRREGULAR_PLURALS.items():
        if s == w.lower():
            return p
    if w.lower() in _INVARIANT:
        return w
    if w.endswith("y") and len(w) > 1 and w[-2].lower() not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    return w + "s"


def _is_plural(w: str) -> bool:
    lw = w.lower()
    if lw in IRREGULAR_PLURALS:
        return True
    return len(lw) > 3 and lw.endswith("s") and not lw.endswith(("ss", "us", "is", "'s"))


def canonical_unit(unit: Optional[str]) -> Optional[str]:
    """Physical unit symbol for any listed spelling (`inch` -> `in`), else None."""
    if not unit:
        return None
    if unit in _PHYS_SYMBOLS:
        return _PHYS_SYMBOLS[unit]
    lw = unit.lower()
    for w in (lw, singular(lw), lw[:-2] if lw.endswith("es") else lw):
        if w in _PHYS_WORDS:
            return _PHYS_WORDS[w]
    return None


def _read_digits(raw: str) -> tuple[Optional[float], bool, bool]:
    """(number, decimal_comma, three_decimals) for a digit run; number None if unreadable."""
    if _THOUSANDS.fullmatch(raw):
        return float(raw.replace(",", "")), False, bool(_THREE_DECIMALS.fullmatch(raw))
    if _DECIMAL_COMMA.fullmatch(raw):
        return float(raw.replace(",", ".")), True, False
    return None, False, False


def _numword_value(m: re.Match) -> float:
    if m.group("h"):
        h = m.group("h").lower()
        return 100.0 * (1 if h == "a" else _ONES_VAL[h])
    if m.group("dz"):
        return 12.0
    if m.group("t"):
        v = _TENS_VAL[m.group("t").lower()]
        if m.group("tu"):
            v += _ONES_VAL[m.group("tu").lower()]
        return float(v)
    return float(_ONES_VAL[m.group("u").lower()])


def _counted_noun(t: str, pos: int) -> Optional[tuple[str, int, tuple[str, ...]]]:
    """(noun, end, all candidate nouns) for the counted noun after a number at pos."""
    p = pos
    if p < len(t) and t[p] == "-":
        p += 1
    else:
        while p < len(t) and t[p] in " \t":
            p += 1
    found: list[tuple[str, int, int]] = []
    for _ in range(3):
        wm = _WORD.match(t, p)
        if not wm:
            break
        found.append((wm.group(0), wm.start(), wm.end()))
        gm = _GAP.match(t, wm.end())
        if not gm:
            break
        p = gm.end()
    usable = [
        (w, b) for (w, a, b) in found
        if len(w) >= 2 and w.lower() not in FUNCTION_WORDS and w.lower() not in _DURATION_WORDS
    ]
    if not usable:
        return None
    nouns = tuple(dict.fromkeys(singular(w) for w, _ in usable))
    for w, b in usable:
        if _is_plural(w):
            return singular(w), b, nouns
    for w, b in usable:
        lw = w.lower()
        if w[0].isupper() or lw.endswith("ly") or (lw.endswith("ed") and len(lw) > 4):
            continue
        return singular(w), b, nouns
    return None


class _Scanner:
    def __init__(self, text: str):
        self.t = text
        self.taken = [False] * (len(text) + 1)
        self.cands: list[_Cand] = []

    def free(self, a: int, b: int) -> bool:
        return not any(self.taken[a:b])

    def take(self, a: int, b: int) -> None:
        for i in range(a, b):
            self.taken[i] = True

    def add(self, c: _Cand) -> None:
        self.cands.append(c)
        self.take(c.start, c.end)

    # -- passes
    def dates(self) -> None:
        for pat in _DATE_PATTERNS:
            for m in pat.finditer(self.t):
                if not self.free(m.start(), m.end()):
                    continue
                gd = m.groupdict()
                mon = gd.get("mon")
                if mon and mon.lower() == "may" and not mon[0].isupper():
                    continue
                y = int(m.group("y"))
                month = int(gd["m"]) if gd.get("m") else (S.MONTH_NUMBERS[mon.lower()] if mon else None)
                day = int(gd["d"]) if gd.get("d") else None
                try:
                    if day is not None:
                        _date(y, month, day)
                        val = f"{y:04d}-{month:02d}-{day:02d}"
                    else:
                        if not 1 <= month <= 12:
                            raise ValueError
                        val = f"{y:04d}-{month:02d}"
                except (ValueError, TypeError):
                    self.take(m.start(), m.end())  # an impossible date reads as nothing
                    continue
                self.add(_Cand("date", val, m.start(), m.end(), m.start()))

    def blockers(self) -> None:
        for pat in _BLOCKERS:
            for m in pat.finditer(self.t):
                if self.free(m.start(), m.end()):
                    self.take(m.start(), m.end())

    def versions(self) -> None:
        for pat in (_VERSION_V, _VERSION_WORD):
            for m in pat.finditer(self.t):
                if self.free(m.start(), m.end()):
                    self.add(_Cand("version", m.group("n"), m.start(), m.end(), m.start("n")))

    def a_durations(self) -> None:
        for m in _A_DURATION.finditer(self.t):
            a, b = m.start("a"), m.end()
            if not self.free(a, b):
                continue
            unit, mult = _DUR_WORDS[m.group("u").lower()]
            self.add(_Cand("duration", float(mult), a, b, a, unit=unit))

    def numbers(self) -> None:
        tokens = []
        for m in _NUM_RUN.finditer(self.t):
            tokens.append((m.start(), m.end(), m.group(0), False))
        for m in _NUMWORD.finditer(self.t):
            tokens.append((m.start(), m.end(), m, True))
        tokens.sort(key=lambda x: x[0])
        for s, e, raw, is_word in tokens:
            if not self.free(s, e):
                continue
            c = self._read_number(s, e, raw, is_word)
            if c is not None:
                self.add(c)
            else:
                self.take(s, e)

    # -- one number and what surrounds it
    def _read_number(self, s: int, e: int, raw, is_word: bool) -> Optional[_Cand]:
        t = self.t
        if is_word:
            if raw.group(0).lower() == "one" and re.match(r"\s+of(?![A-Za-z])", t[e:]):
                return None
            x, dec_comma, three = _numword_value(raw), False, False
            digits = None
        else:
            digits = raw
            if _MULTI_DOT.fullmatch(raw):
                if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw) or raw.count(".") > 3:
                    return None  # dots between thousands
                return _Cand("version", raw, s, e, s)
            x, dec_comma, three = _read_digits(raw)
            if x is None:
                return None
        pos = e
        op = None
        approx = False
        if t.startswith("+", pos):
            op, pos = "ge", pos + 1
        if re.match(r"-ish(?![A-Za-z])", t[pos:], re.I):
            approx, pos = True, pos + 4
        scale = 1.0
        sm = _SCALE.match(t, pos)
        if sm:
            key = next(k for k, v in sm.groupdict().items() if v)
            scale = _SCALE_VAL["bn" if key == "bn" else (sm.group("w").lower() if key == "w" else key)]
            pos = sm.end()
        value = x * scale

        def cand(kind, end, **kw):
            c = _Cand(kind, kw.pop("val", value), kw.pop("start", s), end, s, **kw)
            c.op = c.op or op
            c.approx = c.approx or approx
            return c

        # money: currency before or after the amount
        pm = _CUR_PREFIX.search(t, 0, s) if not is_word else None
        cur = None
        start = s
        if pm and pm.end() == s:
            cur = _SYMBOL_CURRENCY.get(pm.group("sym")) if pm.group("sym") else pm.group("iso")
            start = pm.start()
        end = pos
        if cur is None:
            cm = _CUR_SUFFIX.match(t, pos)
            if cm:
                if cm.group("sym"):
                    cur = _SYMBOL_CURRENCY[cm.group("sym")]
                elif cm.group("iso"):
                    cur = cm.group("iso")
                else:
                    cur = _WORD_CURRENCY[cm.group("word").lower()]
                end = cm.end()
        if cur is not None:
            if three:
                return None
            per = None
            pr = _PERIOD.match(t, end)
            if pr:
                key = pr.group("slash") or pr.group("per") or pr.group("adv") or pr.group("annum")
                per = _PERIOD_CANON[key.lower()]
                end = pr.end()
            return cand("money", end, start=start, currency=cur, per=per)
        if dec_comma:
            return None  # a decimal comma reads only in a price
        pc = _PERCENT.match(t, pos)
        if pc:
            return cand("percent", pc.end())
        if three:
            return None  # 1.500 could be one and a half or fifteen hundred
        if scale == 1.0 and not is_word and t.startswith(('"', "″"), pos):
            return cand("quantity", pos + 1, unit="in")
        ph = _PHYS.match(t, pos)
        if ph:
            if ph.group("sym"):
                unit = _PHYS_SYMBOLS[ph.group("sym")]
                if ph.group("sym") == "in" and ph.group("sep") not in ("", "-") and not re.match(
                    r"\s*(?:[.,;:!?)]|$)", t[ph.end():]
                ):
                    ph = None
            else:
                unit = canonical_unit(ph.group("word"))
            if ph:
                return cand("quantity", ph.end(), unit=unit)
        du = _DUR.match(t, pos)
        if du:
            if du.group("sym"):
                unit, mult = _DUR_SYMBOLS[du.group("sym")]
            else:
                w = du.group("word").lower()
                w = w if w in _DUR_WORDS else w[:-1]
                unit, mult = _DUR_WORDS[w]
            return cand("duration", du.end(), unit=unit, val=value * mult)
        if scale == 1.0 and digits and re.fullmatch(r"\d{4}", digits) and 1900 <= int(digits) <= 2099 and op is None:
            return cand("date", e, val=digits)
        if scale == 1.0 and digits and re.fullmatch(r"\d+\.\d+", digits):
            nm = _CAP_NAME_BEFORE.search(t, 0, s)
            if nm and nm.group("w") not in _NOT_NAMES:
                return cand("version", e, val=digits)
        cn = _counted_noun(t, pos)
        if cn:
            noun, end, nouns = cn
            return cand("quantity", end, unit=noun, nouns=nouns)
        return None

    # -- flags
    def annotate(self) -> None:
        t = self.t
        cands = sorted(self.cands, key=lambda c: c.start)
        extra: list[_Cand] = []
        for i, c in enumerate(cands):
            left = t[: c.start]
            prev = cands[i - 1] if i else None
            if prev is not None and _RANGE_GAP.match(t[prev.end : c.start]):
                j = _RANGE_GAP.match(t[prev.end : c.start]).group("j").lower()
                if prev.kind == c.kind and _compatible(prev, c):
                    if j in ("-", "–", "—", "or"):
                        prev.range_end = c.range_end = True
                    elif j == "and" and re.search(r"(?<![A-Za-z])between\s*$", t[: prev.start], re.I):
                        prev.range_end = c.range_end = True
                    elif j == "to" and not re.search(r"(?<![A-Za-z])from\s*$", t[: prev.start], re.I):
                        prev.range_end = c.range_end = True
            else:
                bm = _BARE_BEFORE.search(left)
                if bm:
                    j = bm.group("j").lower()
                    if j != "and" or re.search(r"(?<![A-Za-z])between\s*$", left[: bm.start()], re.I):
                        c.range_end = True
                        if c.kind != "date":
                            n = bm.group("n")
                            nv = _read_digits(n)[0] if n[0].isdigit() else float(_ONES_VAL.get(
                                n.lower(), _TENS_VAL.get(n.lower(), 0)))
                            if nv is not None:
                                if c.kind == "duration":
                                    nv *= c.value / max(self._unit_count(c), 1e-12)
                                extra.append(_Cand(c.kind, nv, bm.start("n"), bm.end("n"), bm.start("n"),
                                                   unit=c.unit, currency=c.currency, per=c.per,
                                                   range_end=True, nouns=c.nouns))
            if c.op is None:
                c.op = self._op_before(c, left)
            if _APPROX_BEFORE_RE.search(left):
                c.approx = True
            after = t[c.end :]
            om = _OPS_AFTER.match(after)
            if om and c.op is None:
                c.op = "le" if om.group("le") else "ge"
            if _APPROX_AFTER.match(after):
                c.approx = True
        for c in self.cands:
            if c.op == "eq":
                c.op = None
        self.cands = sorted(cands + extra, key=lambda c: c.start)

    def _unit_count(self, c: _Cand) -> float:
        # the written count of a duration before fortnight/decade multipliers
        m = _NUM_RUN.match(self.t, c.num_start)
        if m:
            v = _read_digits(m.group(0))[0]
            if v:
                return v
        return c.value

    @staticmethod
    def _op_before(c: _Cand, left: str) -> Optional[str]:
        if c.kind == "date":
            m = _DATE_OPS_BEFORE_RE.search(left)
            return _DATE_OPS_BEFORE_MAP[re.sub(r"\s+", " ", m.group("p").lower())] if m else None
        if c.kind == "duration" and _WITHIN_RE.search(left):
            return "le"
        if c.kind in ("version",):
            m = _OPS_BEFORE_RE.search(left)
            return _OPS_BEFORE_MAP[re.sub(r"\s+", " ", m.group("p").lower())] if m else None
        m = _OPS_BEFORE_RE.search(left)
        return _OPS_BEFORE_MAP[re.sub(r"\s+", " ", m.group("p").lower())] if m else None


def _dur_group(unit: Optional[str]) -> Optional[str]:
    if unit in _DUR_SECONDS:
        return "seconds"
    if unit in _DUR_MONTHS:
        return "months"
    return None


def _compatible(a: _Cand, b: _Cand) -> bool:
    """Two readings of one kind that a range or a second value could join."""
    if a.kind != b.kind:
        return False
    if a.kind == "money":
        return a.currency == b.currency and a.per == b.per
    if a.kind == "quantity":
        ua, ub = canonical_unit(a.unit), canonical_unit(b.unit)
        if ua or ub:
            return bool(ua and ub and _PHYS_DIM[ua][0] == _PHYS_DIM[ub][0])
        return a.unit == b.unit
    if a.kind == "duration":
        return _dur_group(a.unit) == _dur_group(b.unit)
    return True


def read(sentence: str) -> list[Reading]:
    """Every value the sentence states, as Readings in text order (offsets into sentence)."""
    t, idx = _normalize(sentence)
    sc = _Scanner(t)
    sc.dates()
    sc.blockers()
    sc.versions()
    sc.a_durations()
    sc.numbers()
    sc.annotate()
    out = []
    for c in sc.cands:
        lo, hi = max(c.start - 1, 0), min(c.end + 1, len(t))
        if any(ch in INVISIBLE for ch in t[lo:hi]):
            continue
        v = Value(
            kind=c.kind,
            value=float(c.value) if c.kind in ("quantity", "money", "percent", "duration") else c.value,
            unit=c.unit if c.kind in ("quantity", "duration") else None,
            currency=c.currency if c.kind == "money" else None,
            per=c.per if c.kind == "money" else None,
            op=c.op,
        )
        out.append(
            Reading(
                value=v,
                start=idx[c.start],
                end=idx[c.end],
                num_start=idx[c.num_start],
                negated=S.negated_before(t, c.start),
                approximate=c.approx,
                range_end=c.range_end,
                nouns=c.nouns if c.nouns else ((c.unit,) if c.kind == "quantity" and canonical_unit(c.unit) is None else ()),
            )
        )
    return out


def parse_values(sentence: str) -> list[ParsedValue]:
    """Every readable value in the sentence, in text order, with its flags.

    Values the contract calls ambiguous (`99,9`, `1.500`, `12/03/2026`, `Q4 2026`,
    `10m` as millions, a value beside an invisible character ...) are omitted.
    Negated, approximate and range-end values are returned with their flag set;
    comparison words set Value.op (`over 10,000 customers` -> op "gt").
    Names and yes/no are not read here (see Lexicon.find_mentions).
    """
    return [
        ParsedValue(r.value, r.start, r.end, negated=r.negated, approximate=r.approximate, range_end=r.range_end)
        for r in read(sentence)
    ]


# ------------------------------------------------------------------ writing


def _fmt_number(x: float, three_decimals_ok: bool = False) -> str:
    if not math.isfinite(x):
        raise ValueError(f"not a finite number: {x}")
    if float(x).is_integer() and abs(x) < 1e15:
        return f"{int(x):,}"
    s = repr(float(x))
    if "e" in s:
        s = f"{x:.12f}".rstrip("0")
    ip, fp = s.split(".")
    if len(fp) == 3 and not three_decimals_ok:
        fp += "0"  # `1.125` would read as nothing; `1.1250` reads
    return f"{int(ip):,}.{fp}"


def format_value(v: Value) -> str:
    """The canonical written form the referee reads back as exactly v.

    money "€59 per month" / "€299.99"; quantity "128 GB" / "12 languages";
    percent "99.9%"; date "12 March 2026" / "March 2026" / "2026"; version "v2.3";
    duration "14 days"; name as-is. A boolean raises ValueError: yes/no is written
    through the attribute's words, not as a value.
    """
    k = v.kind
    if k == "boolean":
        raise ValueError("a yes or no has no written value; use attribute_words()")
    if k == "name":
        return str(v.value)
    if k == "version":
        return f"v{v.value}"
    if k == "date":
        parts = str(v.value).split("-")
        if len(parts) == 1:
            return parts[0]
        month = _MONTH_NAMES[int(parts[1]) - 1]
        if len(parts) == 2:
            return f"{month} {parts[0]}"
        return f"{int(parts[2])} {month} {parts[0]}"
    x = float(v.value)
    if k == "percent":
        return f"{_fmt_number(x, three_decimals_ok=True)}%"
    if k == "money":
        cur = v.currency or "EUR"
        num = _fmt_number(x)
        amount = f"{_CURRENCY_SYMBOL_OUT[cur]}{num}" if cur in _CURRENCY_SYMBOL_OUT else f"{cur} {num}"
        return f"{amount} per {v.per}" if v.per else amount
    num = _fmt_number(x)
    if k == "duration":
        one, many = _DUR_OUT[v.unit]
        return f"{num} {one if x == 1 else many}"
    if k == "quantity":
        sym = canonical_unit(v.unit)
        if sym == "in":
            return f"{num} {'inch' if x == 1 else 'inches'}"
        if sym:
            return f"{num} {sym}"
        return f"{num} {v.unit if x == 1 else plural(v.unit)}"
    raise ValueError(f"unknown kind {k!r}")


# ------------------------------------------------------------------ comparing


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _quantity_key(v: Value):
    sym = canonical_unit(v.unit)
    if sym:
        dim, f = _PHYS_DIM[sym]
        return ("phys", dim), float(v.value) * f
    return ("noun", singular(v.unit or "")), float(v.value)


def _duration_key(v: Value):
    if v.unit in _DUR_SECONDS:
        return "seconds", float(v.value) * _DUR_SECONDS[v.unit]
    if v.unit in _DUR_MONTHS:
        return "months", float(v.value) * _DUR_MONTHS[v.unit]
    return None, None


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _version_tuple(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in str(s).split("."))


def _amounts(a: Value, b: Value) -> Optional[tuple[float, float]]:
    """The two values on one scale, or None when they do not compare."""
    if a.kind != b.kind or a.kind in ("name", "boolean", "date", "version"):
        return None
    if a.kind == "money":
        if a.currency != b.currency or a.per != b.per:
            return None
        return float(a.value), float(b.value)
    if a.kind == "percent":
        return float(a.value), float(b.value)
    if a.kind == "quantity":
        ka, xa = _quantity_key(a)
        kb, xb = _quantity_key(b)
        return (xa, xb) if ka == kb else None
    if a.kind == "duration":
        ga, xa = _duration_key(a)
        gb, xb = _duration_key(b)
        return (xa, xb) if ga is not None and ga == gb else None
    return None


def same_value(a: Value, b: Value) -> bool:
    """True when a and b state the same value under the referee's rules.

    Units of one dimension convert (14 days = 2 weeks, 1 GB = 1,000 MB, 12 months
    = 1 year; 30 days is not 1 month); money needs the same currency and period;
    versions and dates compare as written (`2.3` != `2.3.0`, `2026-03-12` !=
    `2026-03`); counted nouns compare in the singular; names ignore case and
    spaces. Values with different comparison words (op) are not the same.
    """
    if a.kind != b.kind or (a.op or "eq") != (b.op or "eq"):
        return False
    k = a.kind
    if k == "boolean":
        return bool(a.value) == bool(b.value)
    if k == "name":
        return _norm_name(a.value) == _norm_name(b.value)
    if k in ("date", "version"):
        return str(a.value) == str(b.value)
    pair = _amounts(a, b)
    return pair is not None and _close(*pair)


def compare_values(a: Value, b: Value) -> Optional[Literal["gt", "lt", "eq"]]:
    """How a compares with b ("gt", "lt", "eq"), or None when they do not compare.

    None for names and yes/no, different kinds, money in another currency or
    period, units of another dimension, days against months, dates of different
    precision, and versions that differ only in trailing zeros (`2.3` / `2.3.0`).
    For dates "gt" means later.
    """
    if a.kind != b.kind:
        return None
    if a.kind == "date":
        sa, sb = str(a.value), str(b.value)
        if len(sa) != len(sb):
            return None
        return "eq" if sa == sb else ("gt" if sa > sb else "lt")
    if a.kind == "version":
        if str(a.value) == str(b.value):
            return "eq"
        ta, tb = _version_tuple(a.value), _version_tuple(b.value)
        n = max(len(ta), len(tb))
        pa, pb = ta + (0,) * (n - len(ta)), tb + (0,) * (n - len(tb))
        if pa == pb:
            return None
        return "gt" if pa > pb else "lt"
    pair = _amounts(a, b)
    if pair is None:
        return None
    x, y = pair
    if _close(x, y):
        return "eq"
    return "gt" if x > y else "lt"


def states_value(r: Reading, v: Value) -> bool:
    """True when reading r states claim value v exactly, as the referee reads it.

    The reading must be plain (no op, approximation, range or negation). A counted
    quantity is read with any of its candidate nouns (`1,200 paying customers`).
    """
    if not r.plain or r.value.kind != v.kind:
        return False
    if v.kind == "quantity" and canonical_unit(v.unit) is None:
        if canonical_unit(r.value.unit) is not None:
            return False
        return singular(v.unit or "") in r.nouns and _close(float(r.value.value), float(v.value))
    return same_value(r.value, Value(v.kind, v.value, v.unit, v.currency, v.per))
