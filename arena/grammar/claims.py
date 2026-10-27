"""Claim phrases of contracts/claim-forms.md: op, change and event phrases, attribute words.

`…` in a phrase stands for up to three words of the writer's own, so
`more … than` reads `more than`, `more languages than` and `more paying
customers than`.
"""
from __future__ import annotations

import re
from typing import Optional

from arena.grammar import sentences as S
from arena.grammar import values as V

OP_PHRASES: dict[str, list[str]] = {
    "gt": ["more … than", "higher … than", "greater … than", "larger … than", "bigger … than", "longer … than"],
    "lt": ["less … than", "fewer … than", "lower … than", "smaller … than", "shorter … than", "cheaper … than"],
    "eq": ["the same … as", "as much … as", "as many … as", "as long as", "as high as", "equal to"],
}
DATE_OP_PHRASES: dict[str, list[str]] = {
    "gt": ["after", "later than"],
    "lt": ["before", "earlier than"],
    "eq": ["on the same day as", "the same day as"],
}
EVENT_PHRASES: list[str] = ["at", "during", "on the day of", "at the time of"]

_ACRONYMS = frozenset(
    """soc ceo cto cfo coo cio eu uk ai api apis sdk sdks sso cli nps io ar hq ide ides url sla arr
    vat os ux ui gpu cpu p99 p95 p50 gb mb tb kb dpa sms""".split()
)
_GAP = r"(?:\s+[A-Za-z0-9'\u2019-]+){0,3}"


def _phrase_regex(phrase: str) -> re.Pattern:
    parts = [p.strip() for p in phrase.split("…")]
    body = (_GAP + r"\s+").join("(" + re.escape(p).replace(r"\ ", r"\s+") + ")" for p in parts)
    return re.compile(r"(?<![A-Za-z])" + body + r"(?![A-Za-z])", re.I)


def _first_word(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z])" + re.escape(phrase.split()[0]) + r"(?![A-Za-z])", re.I)


_OP_REGEXES = [("amount", op, p, _phrase_regex(p), _first_word(p)) for op, ps in OP_PHRASES.items() for p in ps] + [
    ("date", op, p, _phrase_regex(p), _first_word(p)) for op, ps in DATE_OP_PHRASES.items() for p in ps
]
_EVENT_BEFORE = re.compile(
    r"(?<![A-Za-z])(?P<p>at\s+the\s+time\s+of|on\s+the\s+day\s+of|during|at)\s+(?:the\s+)?$", re.I
)


def _units(attr: str) -> list[str]:
    out = []
    for tok in attr.split("_"):
        out.extend(re.findall(r"[a-z]+|[0-9]+", tok.lower()))
    return out


def attribute_words(attr: str) -> str:
    """The attribute read as words, for writing: soc2_certified -> "SOC 2 certified".

    Words are matched in any case with a space, a hyphen or nothing between
    them (and between letters and digits), see attribute_word_spans().
    """
    words = []
    for tok in attr.split("_"):
        if not tok:
            continue
        low = tok.lower()
        if low in _ACRONYMS:
            words.append(low.upper())
            continue
        runs = re.findall(r"[a-z]+|[0-9]+", low)
        if len(runs) > 1:
            words.append(" ".join(r.upper() if r in _ACRONYMS else r for r in runs))
        elif len(low) == 1 and low.isalpha():
            words.append(low.upper())
        else:
            words.append(low)
    return " ".join(words)


def attribute_word_regex(attr: str) -> re.Pattern:
    units = _units(attr)
    body = r"[\s-]*".join(re.escape(u) for u in units)
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.I)


def attribute_word_spans(sentence: str, attr: str) -> list[tuple[int, int]]:
    """Spans where the sentence holds the attribute in words, word for word."""
    if not _units(attr):
        return []
    return [m.span() for m in attribute_word_regex(attr).finditer(sentence)]


def op_phrase_matches(sentence: str) -> list[dict]:
    """Every op phrase occurrence: {"family", "op", "start", "end", "literals"}.

    literals are the spans of the phrase's own words, not the `…` gap. An
    occurrence whose own words all lie in a longer one is that same phrase
    (`the same … as` inside `on the same day as`); any other overlap is a
    second phrase (`cheaper but less popular than` holds two).
    """
    found = []
    for fam, op, _, rx, first in _OP_REGEXES:
        for w in first.finditer(sentence):
            m = rx.match(sentence, w.start())
            if m:
                lits = tuple(m.span(i) for i in range(1, (m.lastindex or 0) + 1))
                found.append({"family": fam, "op": op, "start": m.start(), "end": m.end(), "literals": lits})
    found.sort(key=lambda f: (-sum(b - a for a, b in f["literals"]), f["start"]))
    kept: list[dict] = []
    for f in found:
        if any(all(any(ka <= a and b <= kb for ka, kb in k["literals"]) for a, b in f["literals"]) for k in kept):
            continue
        kept.append(f)
    return sorted(kept, key=lambda f: f["start"])


def op_phrases(sentence: str) -> list[tuple[str, str, int, int]]:
    """Every op phrase as (family, op, start, end); family is "amount" or "date"."""
    return [(f["family"], f["op"], f["start"], f["end"]) for f in op_phrase_matches(sentence)]


def find_op_phrase(sentence: str) -> list[tuple[str, int, int]]:
    """Every compare op phrase (amount or date) in the sentence as (op, start, end)."""
    return [(op, a, b) for _, op, a, b in op_phrases(sentence)]


def find_change_phrases(sentence: str) -> list[dict]:
    """Every change phrase candidate, best first.

    Each is {"style": "from_to" | "up_from" | "down_from", "direction": "up" |
    "down" | None, "from": (start, end|None), "to": (start|None, end|None),
    "start", "end"}. For `from A to B` the from-side is exact and the to-side
    open-ended; for `B, up from A` the to-side ends at the comma and the
    from-side is open-ended. Candidates whose from-side reads as one whole value
    come first.
    """
    out = []
    for m in re.finditer(r"(?<![A-Za-z])(?:(?P<dir>up|down)\s+)?from\s+", sentence, re.I):
        for t in re.finditer(r"\s+to\s+", sentence[m.end():], re.I):
            a0, a1 = m.end(), m.end() + t.start()
            b0 = m.end() + t.end()
            if a1 <= a0:
                continue
            d = m.group("dir")
            out.append({"style": "from_to", "direction": d.lower() if d else None,
                        "from": (a0, a1), "to": (b0, None), "start": m.start(), "end": b0})
    for m in re.finditer(r",\s*(?P<dir>up|down)\s+from\s+", sentence, re.I):
        d = m.group("dir").lower()
        out.append({"style": f"{d}_from", "direction": d, "from": (m.end(), None), "to": (None, m.start()),
                    "start": m.start(), "end": m.end()})

    def clean(c):
        if c["style"] != "from_to":
            return 0
        a0, a1 = c["from"]
        rs = V.read(sentence[a0:a1])
        return 0 if len(rs) == 1 and rs[0].start == 0 and rs[0].end == a1 - a0 else 1

    out.sort(key=lambda c: (clean(c), c["start"]))
    return out


def find_change_phrase(sentence: str) -> Optional[dict]:
    """The best change phrase of the sentence (see find_change_phrases), or None."""
    c = find_change_phrases(sentence)
    return c[0] if c else None


def find_event_phrases(sentence: str, lexicon) -> list[tuple[str, int, int]]:
    """Every (event, start, end): an event phrase right before a lexicon event name."""
    out = []
    for mn in lexicon.find_mentions(sentence):
        if mn.subject not in lexicon.events:
            continue
        m = _EVENT_BEFORE.search(sentence, 0, mn.start)
        if m:
            out.append((mn.subject, m.start(), mn.end))
    return out


def find_event_phrase(sentence: str, lexicon) -> Optional[tuple[str, int, int]]:
    """(event, start, end) for the first event phrase (at, during, on the day of,
    at the time of) right before an event name, `the` optional between; else None.
    """
    found = find_event_phrases(sentence, lexicon)
    return found[0] if found else None


def _inside(span: tuple[int, int], allowed: list[tuple[int, int]]) -> bool:
    return any(a <= span[0] and span[1] <= b for a, b in allowed)


def time_words_outside(sentence: str, allowed_spans: list[tuple[int, int]]) -> list[tuple[str, int, int]]:
    return [w for w in S.find_time_words(sentence) if not _inside((w[1], w[2]), allowed_spans)]


def has_time_word(sentence: str, allowed_spans: list[tuple[int, int]]) -> bool:
    """True when a refused time word (ago, since, used to, last year ...) stands
    outside the allowed spans (the needed names, the value, the event phrase).
    """
    return bool(time_words_outside(sentence, allowed_spans))


_YEARISH = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_QUARTER = re.compile(r"(?<![A-Za-z0-9])[QH][1-4](?![A-Za-z0-9])")


def own_dates_outside(sentence: str, allowed_spans: list[tuple[int, int]]) -> list[tuple[str, int, int]]:
    out = []
    for r in V.read(sentence):
        if r.value.kind == "date" and not _inside((r.start, r.end), allowed_spans):
            out.append((sentence[r.start:r.end], r.start, r.end))
    for w, a, b in S.find_yearless_date_words(sentence):
        if not _inside((a, b), allowed_spans):
            out.append((w, a, b))
    for rx in (_YEARISH, _QUARTER):
        for m in rx.finditer(sentence):
            if not _inside(m.span(), allowed_spans) and not any(o[1] <= m.start() < o[2] for o in out):
                out.append((m.group(0), m.start(), m.end()))
    return out


def has_own_date(sentence: str, allowed_spans: list[tuple[int, int]]) -> bool:
    """True when a date, a month, season or weekday, a quarter or a year-like
    number stands outside the allowed spans.
    """
    return bool(own_dates_outside(sentence, allowed_spans))
