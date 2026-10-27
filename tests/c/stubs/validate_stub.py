"""Stub of A's arena.validate.validate: entry.schema.json shape plus a strict
reading of claim-forms.md. Stricter than needed on purpose (any digit, month,
time word or negation outside what the form needs is refused) so output that
passes here is likely to pass A's real validator and the referee."""
from __future__ import annotations

import re

from arena.model import DURATION_UNITS, Value

from grammar_stub import (MONTH_WORDS, NEGATION_WORDS, NUMBER_WORDS, TIME_WORDS,
                          attribute_words, compare_values, format_value)

ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
ATTR_RE = re.compile(r"^[a-z][a-z0-9_]*$")
UNIT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DATE_RE = re.compile(r"^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$")
VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,3}$")
FORM_KEYS = {
    "fact": {"subject", "attribute", "value"},
    "compare": {"left", "right", "op"},
    "change": {"subject", "attribute", "from", "to"},
    "at_event": {"subject", "attribute", "event", "value"},
    "relation": {"subject", "link", "target", "attribute", "value"},
}
VALUE_KEYS = {
    "quantity": ({"kind", "value", "unit"}, set()),
    "money": ({"kind", "value", "currency"}, {"per"}),
    "percent": ({"kind", "value"}, set()),
    "date": ({"kind", "value"}, set()),
    "version": ({"kind", "value"}, set()),
    "duration": ({"kind", "value", "unit"}, set()),
    "name": ({"kind", "value"}, set()),
    "boolean": ({"kind", "value"}, set()),
}
AMOUNT_PHRASES = {
    "gt": ["more", "higher", "greater", "larger", "bigger", "longer"],
    "lt": ["less", "fewer", "lower", "smaller", "shorter", "cheaper"],
}
DATE_PHRASES = {"gt": [r"after", r"later than"], "lt": [r"before", r"earlier than"],
                "eq": [r"on the same day as", r"the same day as"]}
EVENT_PHRASES = ["at the time of", "on the day of", "during", "at"]
ABBREVIATIONS = ("e.g.", "i.e.", "vs.", "approx.", "inc.", "ltd.", "co.", "corp.",
                 "dr.", "mr.", "mrs.", "ms.", "prof.", "st.")


_KNOWN: set[str] = set()


def _named(lexicon, name) -> bool:
    return bool(lexicon.resolve(name)) or str(name).lower() in _KNOWN


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def value_errors(v, where: str) -> list[str]:
    if not isinstance(v, dict) or v.get("kind") not in VALUE_KEYS:
        return [f"{where}: unknown value kind"]
    req, opt = VALUE_KEYS[v["kind"]]
    keys = set(v)
    errs = []
    if "op" in keys:
        errs.append(f"{where}: value carries op")
    if not req <= keys or keys - req - opt:
        errs.append(f"{where}: keys {sorted(keys)} do not fit {v['kind']}")
        return errs
    k, x = v["kind"], v["value"]
    if k in ("quantity", "money", "percent", "duration") and not _num(x):
        errs.append(f"{where}: value is not a number")
    elif k in ("money", "duration") and x < 0:
        errs.append(f"{where}: negative value")
    if k == "quantity" and (not UNIT_RE.match(str(v["unit"])) or len(v["unit"]) > 40
                            or v["unit"] in DURATION_UNITS):
        errs.append(f"{where}: bad unit")
    if k == "money" and (not re.match(r"^[A-Z]{3}$", str(v["currency"]))
                         or v.get("per") not in (None, "day", "week", "month", "year")):
        errs.append(f"{where}: bad currency or period")
    if k == "date" and not (isinstance(x, str) and DATE_RE.match(x)):
        errs.append(f"{where}: bad date")
    if k == "version" and not (isinstance(x, str) and VERSION_RE.match(x)):
        errs.append(f"{where}: bad version")
    if k == "duration" and v["unit"] not in DURATION_UNITS:
        errs.append(f"{where}: bad duration unit")
    if k == "name" and not (isinstance(x, str) and 1 <= len(x) <= 200 and x.strip()):
        errs.append(f"{where}: bad name")
    if k == "boolean" and not isinstance(x, bool):
        errs.append(f"{where}: boolean is not true/false")
    return errs


def _flex(words: str) -> str:
    """Attribute words with space, hyphen or nothing between words and letter/digit runs."""
    parts = re.findall(r"[A-Za-z]+|[0-9]+", words)
    return r"(?<![A-Za-z0-9])" + r"[\s-]?".join(map(re.escape, parts)) + r"(?![A-Za-z0-9])"


def _sentence_count(text: str) -> int:
    n, i = 1, 0
    for m in re.finditer(r"[.!?](?=\s)", text):
        before = text[:m.end()].lower()
        if before.endswith(ABBREVIATIONS) or re.search(r"(^|\s)[A-Za-z]\.$", before):
            continue
        if re.search(r"(^|\s)no\.$", before) and re.match(r"\s*\d", text[m.end():]):
            continue
        n += 1
        i = m.end()
    return n


def _blank(text: str, pattern: str) -> tuple[str, int]:
    """Replace every case-insensitive match of pattern by a neutral token."""
    return re.subn(pattern, " § ", text, flags=re.IGNORECASE)


def _name_pattern(name: str) -> str:
    return r"(?<![\w])" + r"\s*".join(map(re.escape, name.split())) + r"(?![\w])"


def _leftover_errors(rest: str, allow_negation: bool, allow_time: tuple = ()) -> list[str]:
    errs = []
    if re.search(r"\d", rest):
        errs.append("a number of its own")
    words = re.findall(r"[A-Za-z']+", rest)
    lower = [w.lower() for w in words]
    if any(w in NUMBER_WORDS for w in lower):
        errs.append("a number word")
    if any((w.lower() in MONTH_WORDS and w.lower() != "may") or w == "May" for w in words):
        errs.append("a month, season or weekday")
    joined = " " + " ".join(lower) + " "
    for tw in TIME_WORDS:
        if f" {tw} " in joined and tw not in allow_time:
            errs.append(f"time word '{tw}'")
    if not allow_negation and (any(w in NEGATION_WORDS for w in lower)
                               or any(w.endswith("n't") for w in lower)):
        errs.append("a negation")
    return errs


def _negated(text: str) -> bool:
    lower = re.findall(r"[a-z']+", text.lower())
    return any(w in NEGATION_WORDS or w.endswith("n't") for w in lower)


def _mentions(lexicon, text: str, subject: str) -> bool:
    canon = lexicon.resolve(subject)
    return any(m.subject == canon for m in lexicon.find_mentions(text))


def validate(claim, lexicon, attrs=None, known_names=None) -> list[str]:
    """[] when the claim looks acceptable; otherwise human-readable reasons.
    A name value must be a lexicon name or one of known_names (A's signature)."""
    global _KNOWN
    _KNOWN = {n.lower() for n in (known_names or ())}
    errs: list[str] = []
    if claim.type not in FORM_KEYS:
        return [f"unknown type {claim.type!r}"]
    if claim.label not in ("true", "false"):
        errs.append("label is not true/false")
    if claim.confidence is not None and not (0.5 <= claim.confidence <= 1.0):
        errs.append("confidence outside [0.5, 1]")
    if claim.id is not None and not ID_RE.match(claim.id):
        errs.append("bad id")
    text = claim.text or ""
    if not (1 <= len(text) <= 300) or not text.strip():
        return errs + ["text empty or longer than 300"]
    if not text.endswith("."):
        errs.append("text does not end with '.'")
    if _sentence_count(text) != 1:
        errs.append("text is not one sentence")
    f = claim.form
    if not isinstance(f, dict) or set(f) != FORM_KEYS[claim.type]:
        return errs + [f"form keys do not fit {claim.type}"]
    check = getattr(_Checks, claim.type)
    return errs + check(claim, f, text, lexicon)


class _Checks:
    @staticmethod
    def _fact_like(f, text, lexicon, value_key="value", extra_names=(), allow_time=()):
        errs = []
        s = f["subject"]
        if not lexicon.has_attribute(s, f["attribute"]):
            errs.append(f"{s} has no attribute {f['attribute']}")
        if not _mentions(lexicon, text, s):
            errs.append(f"subject {s} not named")
        v = f[value_key]
        errs += value_errors(v, value_key)
        if errs:
            return errs, None
        rest = text
        for name in (s, *extra_names):
            rest, _ = _blank(rest, _name_pattern(name))
        value = Value.from_json(v)
        if value.kind == "boolean":
            rest, n = _blank(rest, _flex(attribute_words(f["attribute"])))
            if n == 0:
                errs.append("attribute words missing")
            if _negated(text) != (value.value is False):
                errs.append("polarity does not match the value")
            errs += _leftover_errors(rest, allow_negation=True, allow_time=allow_time)
            return errs, rest
        if value.kind == "name" and not _named(lexicon, value.value):
            errs.append(f"name {value.value!r} is not in the lexicon")
        written = format_value(value)
        rest, n = _blank(rest, r"(?<![\w€$£])" + re.escape(written) + r"(?![\w%])")
        if n != 1:
            errs.append(f"value '{written}' written {n} times")
        errs += _leftover_errors(rest, allow_negation=False, allow_time=allow_time)
        return errs, rest

    @staticmethod
    def fact(claim, f, text, lexicon):
        return _Checks._fact_like(f, text, lexicon)[0]

    @staticmethod
    def at_event(claim, f, text, lexicon):
        errs = []
        event = lexicon.resolve(f["event"])
        if event not in lexicon.events or not lexicon.event_date_attr(event):
            errs.append(f"{f['event']} is not an event with a date")
            return errs
        phrase = r"(?:%s)\s+(?:the\s+)?%s" % ("|".join(map(re.escape, EVENT_PHRASES)),
                                              _name_pattern(event))
        if not re.search(r"(?<![\w])" + phrase, text, re.IGNORECASE):
            errs.append("no event phrase right before the event name")
        text_wo_event, _ = _blank(text, r"(?<![\w])" + phrase)
        more, _ = _Checks._fact_like(f, text_wo_event, lexicon)
        return errs + more

    @staticmethod
    def relation(claim, f, text, lexicon):
        errs = []
        s, link, target = f["subject"], f["link"], f["target"]
        if not lexicon.has_attribute(s, link):
            errs.append(f"{s} has no link {link}")
        if not lexicon.has_attribute(target, f["attribute"]):
            errs.append(f"{target} has no attribute {f['attribute']}")
        if errs:
            return errs
        rest, n = _blank(text, _flex(attribute_words(link)))
        if n == 0:
            errs.append("relation words missing")
        if not _mentions(lexicon, text, s):
            errs.append(f"subject {s} not named")
        rest, _ = _blank(rest, _name_pattern(s))
        g = {"subject": target, "attribute": f["attribute"], "value": f["value"]}
        more, _ = _Checks._fact_like(g, rest, lexicon)
        return errs + [e for e in more if not e.startswith("subject")]

    @staticmethod
    def compare(claim, f, text, lexicon):
        errs = []
        if f["op"] not in ("gt", "lt", "eq"):
            errs.append("op is not gt/lt/eq")
        for side in ("left", "right"):
            ref = f[side]
            if not isinstance(ref, dict) or set(ref) != {"subject", "attribute"}:
                return errs + [f"{side} is not a subject/attribute ref"]
            if not lexicon.has_attribute(ref["subject"], ref["attribute"]):
                errs.append(f"{ref['subject']} has no attribute {ref['attribute']}")
        if f["left"] == f["right"]:
            errs.append("a fact compared with itself")
        if errs:
            return errs
        lm = re.search(_name_pattern(f["left"]["subject"]), text, re.IGNORECASE)
        if not lm:
            return ["left subject not named"]
        rm = None
        for m in re.finditer(_name_pattern(f["right"]["subject"]), text, re.IGNORECASE):
            if m.start() >= lm.end():
                rm = m
                break
        if not rm:
            return ["right subject not named after the left one"]
        middle = text[lm.end():rm.start()]
        prefix = text[:lm.start()] + " § "
        rest = prefix + middle + " § " + text[rm.end():]
        date_pats = {op: [r"(?<![\w])" + p + r"(?![\w])" for p in ps]
                     for op, ps in DATE_PHRASES.items()}
        gap = r"(?:\s+[A-Za-z][\w-]*){0,3}\s+"
        amount_pats = {op: [r"(?<![\w])" + w + gap + r"than(?![\w])" for w in ws]
                       for op, ws in AMOUNT_PHRASES.items()}
        amount_pats["eq"] = [r"(?<![\w])the same" + gap + r"as(?![\w])",
                             r"(?<![\w])as (?:much|many)" + gap + r"as(?![\w])",
                             r"(?<![\w])as (?:long|high) as(?![\w])",
                             r"(?<![\w])equal to(?![\w])"]

        def find(pats):
            hits = [(op, m) for op, ps in pats.items() for p in ps
                    for m in re.finditer(p, rest, re.IGNORECASE)]
            # "on the same day as" holds "the same day as": keep the outer match
            return [(op, m) for op, m in hits
                    if not any(n is not m and n.start() <= m.start() and m.end() <= n.end()
                               and (n.end() - n.start()) > (m.end() - m.start())
                               for _, n in hits)]
        kind = claim.evidence.get("kind")
        if kind == "date":
            found = find(date_pats)
        elif kind is not None:
            found = find(amount_pats)
        else:  # kind unknown (a row read back from CSV): either family, not both
            found_d, found_a = find(date_pats), find(amount_pats)
            found = found_d if len(found_d) == 1 and not found_a else found_a
        if len(found) != 1:
            return [f"{len(found)} op phrases"]
        op, m = found[0]
        if op != f["op"]:
            errs.append(f"phrase states {op}, form says {f['op']}")
        if not (len(prefix) <= m.start() and m.end() <= len(prefix) + len(middle)):
            errs.append("op phrase is not between the two subjects")
        rest_wo_phrase = rest[:m.start()] + " § " + rest[m.end():]
        errs += _leftover_errors(rest_wo_phrase, allow_negation=False)
        return errs

    @staticmethod
    def change(claim, f, text, lexicon):
        errs = []
        s = f["subject"]
        if not lexicon.has_attribute(s, f["attribute"]):
            errs.append(f"{s} has no attribute {f['attribute']}")
        if not _mentions(lexicon, text, s):
            errs.append(f"subject {s} not named")
        errs += value_errors(f["from"], "from") + value_errors(f["to"], "to")
        if errs:
            return errs
        a, b = Value.from_json(f["from"]), Value.from_json(f["to"])
        if a.kind != b.kind:
            return ["from and to differ in kind"]
        if a.kind == "name":
            for v in (a, b):
                if not _named(lexicon, v.value):
                    errs.append(f"name {v.value!r} is not in the lexicon")
            if errs:
                return errs
        rest, _ = _blank(text, _name_pattern(s))
        if a.kind == "boolean":
            m = re.search(r"(?<![\w])from (.+) to (.+)\.$", rest, re.IGNORECASE)
            if not m:
                return ["no 'from … to' change phrase"]
            words = _flex(attribute_words(f["attribute"]))
            for side, val in ((m.group(1), a), (m.group(2), b)):
                if not re.search(words, side, re.IGNORECASE):
                    errs.append("attribute words missing on one side")
                if _negated(side) != (val.value is False):
                    errs.append("side polarity does not match its value")
            if re.search(r"(?<![\w])(up|down)\s+from", rest, re.IGNORECASE):
                errs.append("direction word on a yes/no change")
            return errs
        fa, fb = re.escape(format_value(a)), re.escape(format_value(b))
        forms = [
            (rf"(?<![\w])(?:(up|down)\s+)?from {fa} to {fb}(?![\w%])", "fromto"),
            (rf"(?<![\w€$£]){fb}, (up|down) from {fa}(?![\w%])", "upfrom"),
        ]
        hit = None
        for pat, kind in forms:
            m = re.search(pat, rest, re.IGNORECASE)
            if m:
                hit = m
                break
        if not hit:
            return ["no change phrase holding both values"]
        direction = hit.group(1).lower() if hit.group(1) else None
        order = compare_values(b, a)
        if direction and a.kind == "name":
            errs.append("direction word on a name change")
        if direction == "up" and order != "gt":
            errs.append("'up' but to is not larger")
        if direction == "down" and order != "lt":
            errs.append("'down' but to is not smaller")
        leftover = rest[:hit.start()] + " § " + rest[hit.end():]
        return errs + _leftover_errors(leftover, allow_negation=False)
