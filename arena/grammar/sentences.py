"""Sentence, clause and word-list rules the referee reads by.

Sources: contracts/value-forms.md (sentence ends, clauses, negations) and the
"Refused" table of contracts/claim-forms.md (time words, dates without a year).
All functions work on character offsets into the string they are given.
"""
from __future__ import annotations

import re

NEGATION_WORDS: frozenset[str] = frozenset(
    {"not", "no", "never", "none", "nobody", "nothing", "neither", "nor", "without", "cannot"}
)  # plus any word ending in n't

TIME_WORDS: frozenset[str] = frozenset(
    {
        "ago", "yesterday", "tomorrow", "once", "formerly", "previously", "originally",
        "initially", "recently", "lately", "soon", "eventually", "then", "before", "after",
        "since", "until", "till", "earlier", "later", "used to",
        "last week", "last month", "last quarter", "last year",
        "next week", "next month", "next quarter", "next year",
        "in the past", "in the future", "at the time", "at that time",
    }
)

MONTH_WORDS: frozenset[str] = frozenset(
    {
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december",
    }
)  # "may" counts only when written with a capital M
SEASON_WORDS: frozenset[str] = frozenset({"spring", "summer", "autumn", "winter"})
WEEKDAY_WORDS: frozenset[str] = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)
YEARLESS_DATE_WORDS: frozenset[str] = MONTH_WORDS | SEASON_WORDS | WEEKDAY_WORDS

MONTH_NUMBERS: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_ABBREVIATIONS: frozenset[str] = frozenset(k for k in MONTH_NUMBERS if len(k) <= 4 and k not in MONTH_WORDS)

# Comparison words that hold a negation word but are not a negation (value-forms.md).
NEGATED_OP_PHRASES: tuple[str, ...] = (
    "no more than", "not more than", "no less than", "not less than", "no fewer than",
    "no later than", "no earlier than",
)

# Abbreviations whose point ends nothing (value-forms.md, "A claim names what it is about").
_ABBREVIATIONS = frozenset(
    {"e.g", "i.e", "vs", "approx", "inc", "ltd", "co", "corp", "dr", "mr", "mrs", "ms", "prof", "st"}
)
# Read leniently from universe pages only, never when policing our own entries.
_LENIENT_ABBREVIATIONS = frozenset({"ver", "est", "ca", "no", "nr", "fig", "approx"}) | MONTH_ABBREVIATIONS

_WORD_BEFORE_DOT = re.compile(r"(?<![A-Za-z.])([A-Za-z]+(?:\.[A-Za-z]+)*)$")
_BLANK_LINE = re.compile(r"\n[ \t\r\f\v]*\n")
_CLOSERS = "\"'”’)»"

_NEGATION_RE = re.compile(
    r"(?<![A-Za-z])(?:[A-Za-z]*n['’]t|not|no|never|none|nobody|nothing|neither|nor|without|cannot)(?![A-Za-z])",
    re.I,
)
_NEGATED_OP_RE = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(p.replace(" ", r"\s+") for p in NEGATED_OP_PHRASES) + r")(?![A-Za-z])",
    re.I,
)
_NUMBER_ABBR_RE = re.compile(r"(?<![A-Za-z])no\.\s*\d", re.I)


def _phrase_regex(phrases) -> re.Pattern:
    alts = sorted(phrases, key=len, reverse=True)
    return re.compile(
        r"(?<![A-Za-z])(?:" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in alts) + r")(?![A-Za-z])",
        re.I,
    )


_TIME_RE = _phrase_regex(TIME_WORDS)
_YEARLESS_RE = re.compile(
    r"(?<![A-Za-z])(?:" + "|".join(sorted(YEARLESS_DATE_WORDS, key=len, reverse=True)) + r")(?![A-Za-z])",
    re.I,
)
_MONTH_ABBR_RE = re.compile(r"(?<![A-Za-z])(?:Sept|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?![A-Za-z])\.?")


def dot_is_abbreviation(text: str, i: int, lenient: bool = False) -> bool:
    """True when the point at text[i] belongs to an abbreviation and ends nothing.

    The referee's list: e.g., i.e., vs., approx., Inc., Ltd., Co., Corp., Dr., Mr.,
    Mrs., Ms., Prof., St., a single initial such as J., and No. before a number.
    lenient=True also accepts ver., est., ca. and month abbreviations before a
    number, which universe pages use; never use it to police an entry.
    """
    m = _WORD_BEFORE_DOT.search(text, 0, i)
    if not m:
        return False
    word = m.group(1)
    low = word.lower()
    if low in _ABBREVIATIONS:
        return True
    if len(word) == 1 and word.isupper():
        return True
    after = text[i + 1 : i + 4]
    if low == "no" and re.match(r"\s*\d", after):
        return True
    if lenient and low in _LENIENT_ABBREVIATIONS and (low not in MONTH_ABBREVIATIONS or re.match(r"\s*\d", after)):
        return True
    return False


def sentence_spans(text: str, lenient: bool = False) -> list[tuple[int, int]]:
    """Spans of the sentences of text, trimmed of surrounding whitespace.

    A sentence ends at '.', '!' or '?' before a space (or the end of the text),
    or at a blank line; a single line break is a space; abbreviation points end
    nothing. lenient=True also ends a sentence at a closing quote after the
    point (`."`), for reading universe pages.
    """
    raw: list[tuple[int, int]] = []
    start = i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\n":
            m = _BLANK_LINE.match(text, i)
            if m:
                raw.append((start, i))
                start = i = m.end()
                continue
        elif c in ".!?":
            j = i + 1
            if lenient:
                while j < n and text[j] in _CLOSERS:
                    j += 1
            if j >= n or text[j].isspace():
                if c == "." and dot_is_abbreviation(text, i, lenient):
                    i += 1
                    continue
                raw.append((start, j))
                start = i = j
                continue
        i += 1
    raw.append((start, n))
    spans = []
    for a, b in raw:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if b > a:
            spans.append((a, b))
    return spans


def _is_clause_break(sentence: str, i: int) -> bool:
    c = sentence[i]
    if c in ";!?•·|":
        return True
    prev_digit = i > 0 and sentence[i - 1].isdigit()
    next_char = sentence[i + 1] if i + 1 < len(sentence) else ""
    if c in ",:":
        return not (prev_digit and next_char.isdigit())
    if c == ".":
        if next_char and not next_char.isspace() and next_char not in _CLOSERS:
            return False  # 99.9, v2.3, e.g, Hooly.com
        return not dot_is_abbreviation(sentence, i, lenient=True)
    return False


def clauses(sentence: str) -> list[tuple[int, int]]:
    """Spans of the clauses of a sentence.

    A clause ends at . , ; : ! ? • · | or a blank line, but not at a single line
    break, a decimal point, a thousands comma or an abbreviation point.
    """
    spans = []
    start = 0
    i = 0
    n = len(sentence)
    while i < n:
        if sentence[i] == "\n":
            m = _BLANK_LINE.match(sentence, i)
            if m:
                spans.append((start, i))
                start = i = m.end()
                continue
        elif _is_clause_break(sentence, i):
            spans.append((start, i))
            start = i + 1
        i += 1
    spans.append((start, n))
    return spans


def clause_of(sentence: str, pos: int) -> tuple[int, int]:
    """The clause span holding character pos."""
    for a, b in clauses(sentence):
        if a <= pos <= b:
            return a, b
    return 0, len(sentence)


def find_negations(sentence: str, include_op_phrases: bool = True) -> list[tuple[int, int]]:
    """Spans of every negation word (not, no, never, ..., any word ending in n't).

    include_op_phrases=False leaves out the negation words of comparison words
    such as `no more than`, and the `No.` of `No. 1`, which value-forms.md says
    are not negations.
    """
    spans = [m.span() for m in _NEGATION_RE.finditer(sentence)]
    skip = [m.span() for m in _NUMBER_ABBR_RE.finditer(sentence)]
    if not include_op_phrases:
        skip += [m.span() for m in _NEGATED_OP_RE.finditer(sentence)]
    return [s for s in spans if not any(a <= s[0] < b for a, b in skip)]


def negated_before(sentence: str, pos: int) -> bool:
    """True when a negation word stands earlier than pos in the same clause.

    Comparison words such as `no more than` are not negations here.
    """
    a, _ = clause_of(sentence, pos)
    return any(a <= s < pos for s, _ in find_negations(sentence, include_op_phrases=False))


def find_time_words(sentence: str) -> list[tuple[str, int, int]]:
    """Every time word of the refused table: (word as listed, start, end)."""
    return [(re.sub(r"\s+", " ", m.group(0).lower()), m.start(), m.end()) for m in _TIME_RE.finditer(sentence)]


def find_yearless_date_words(sentence: str) -> list[tuple[str, int, int]]:
    """Months, seasons and weekdays (and capitalised month abbreviations).

    `may` counts as the month only when written with a capital M.
    """
    out = []
    for m in _YEARLESS_RE.finditer(sentence):
        w = m.group(0)
        if w.lower() == "may" and not w[0].isupper():
            continue
        out.append((w.lower(), m.start(), m.end()))
    for m in _MONTH_ABBR_RE.finditer(sentence):
        out.append((m.group(0).rstrip(".").lower(), m.start(), m.end()))
    return sorted(out, key=lambda x: x[1])


def words(sentence: str) -> list[tuple[str, int, int]]:
    """Word tokens (letters and digits, with inner apostrophes) and their spans."""
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?", sentence)]
