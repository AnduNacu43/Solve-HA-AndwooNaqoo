"""The referee clone: would the referee accept this entry?

Two layers. shape_errors() is entry.schema.json and claimed_value.schema.json
written by hand (no jsonschema at run time) plus the lexicon checks of the
contract. grammar_errors() re-reads the entry's text against its form with the
grammars of claim-forms.md and value-forms.md. When in doubt it rejects: an
entry we never emit costs nothing, an invalid one costs a point.

CLI: python -m arena.validate out/output.csv [more.csv|entry.json ...]
     [--lexicon data/lexicon.json] [--explain]
prints the number of rows and every invalid row with its reasons; exit code 1
if any row is invalid.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Optional

from arena.grammar import claims as C
from arena.grammar import sentences as S
from arena.grammar import values as V
from arena.lexicon import Lexicon, _name_pattern, name_key
from arena.model import DURATION_UNITS, Claim, Value
from arena.pages import split_sentences

TYPES = ("fact", "compare", "change", "at_event", "relation")
KINDS = ("quantity", "money", "percent", "date", "version", "duration", "name", "boolean")
PERIODS = ("day", "week", "month", "year")
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_ATTR_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_UNIT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_DATE_RE = re.compile(r"^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$")
_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,3}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

_FORM_KEYS = {
    "fact": ("subject", "attribute", "value"),
    "compare": ("left", "right", "op"),
    "change": ("subject", "attribute", "from", "to"),
    "at_event": ("subject", "attribute", "event", "value"),
    "relation": ("subject", "link", "target", "attribute", "value"),
}
_VALUE_KEYS = {  # kind -> (required, allowed)
    "quantity": ({"kind", "value", "unit"}, {"kind", "value", "unit", "op"}),
    "money": ({"kind", "value", "currency"}, {"kind", "value", "currency", "per", "op"}),
    "percent": ({"kind", "value"}, {"kind", "value", "op"}),
    "date": ({"kind", "value"}, {"kind", "value", "op"}),
    "version": ({"kind", "value"}, {"kind", "value", "op"}),
    "duration": ({"kind", "value", "unit"}, {"kind", "value", "unit", "op"}),
    "name": ({"kind", "value"}, {"kind", "value"}),
    "boolean": ({"kind", "value"}, {"kind", "value"}),
}
_NUMBER_WORDS = re.compile(
    r"(?<![A-Za-z])(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    r"eighty|ninety|hundred|thousand|million|billion|dozen|half|once|twice|double|triple)(?![A-Za-z])",
    re.I,
)
_CAP_WORD = re.compile(r"(?<![A-Za-z0-9'’])[A-Z][a-z][A-Za-z'’-]*")


# ------------------------------------------------------------------ shape


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_name(x) -> bool:
    return isinstance(x, str) and 1 <= len(x) <= 120 and bool(re.search(r"\S", x))


def value_errors(v, where: str, allow_op: bool = False) -> list[str]:
    """claimed_value.schema.json by hand; entries (allow_op=False) may not carry op."""
    if not isinstance(v, dict):
        return [f"{where}: a value must be an object"]
    kind = v.get("kind")
    if kind not in KINDS:
        return [f"{where}: kind must be one of {', '.join(KINDS)}"]
    req, allowed = _VALUE_KEYS[kind]
    errs = []
    if "op" in v and not allow_op:
        errs.append(f"{where}: an entry's value carries no op (a comparison is a compare)")
    missing = req - set(v)
    extra = set(v) - allowed
    if missing:
        errs.append(f"{where}: {kind} value lacks {', '.join(sorted(missing))}")
    if extra:
        errs.append(f"{where}: {kind} value has unknown field(s) {', '.join(sorted(extra))}")
    if "op" in v and v["op"] not in ("eq", "lt", "le", "gt", "ge"):
        errs.append(f"{where}: unknown op {v['op']!r}")
    x = v.get("value")
    if kind in ("quantity", "money", "percent", "duration"):
        if not _is_number(x):
            errs.append(f"{where}: value must be a number")
        elif kind in ("money", "duration") and x < 0:
            errs.append(f"{where}: value must not be negative")
    if kind == "quantity" and "unit" in v:
        u = v["unit"]
        if not isinstance(u, str) or not _UNIT_RE.match(u) or len(u) > 40:
            errs.append(f"{where}: unit must match ^[A-Za-z][A-Za-z0-9_]*$ (at most 40)")
        elif u in DURATION_UNITS:
            errs.append(f"{where}: {u!r} is a duration unit; durations are their own kind")
    if kind == "duration" and "unit" in v and v["unit"] not in DURATION_UNITS:
        errs.append(f"{where}: duration unit must be one of {', '.join(DURATION_UNITS)}")
    if kind == "money":
        if "currency" in v and (not isinstance(v["currency"], str) or not _CURRENCY_RE.match(v["currency"])):
            errs.append(f"{where}: currency must be an ISO code such as EUR")
        if "per" in v and v["per"] not in PERIODS:
            errs.append(f"{where}: per must be one of {', '.join(PERIODS)}")
    if kind == "date" and (not isinstance(x, str) or not _DATE_RE.match(x)):
        errs.append(f"{where}: date value must be YYYY, YYYY-MM or YYYY-MM-DD")
    if kind == "version" and (not isinstance(x, str) or not _VERSION_RE.match(x)):
        errs.append(f"{where}: version value must match ^[0-9]+(\\.[0-9]+){{0,3}}$ (no v)")
    if kind == "name" and (not isinstance(x, str) or not 1 <= len(x) <= 200 or not re.search(r"\S", x)):
        errs.append(f"{where}: name value must be a non-blank string of at most 200")
    if kind == "boolean" and not isinstance(x, bool):
        errs.append(f"{where}: boolean value must be true or false")
    return errs


def _ref_errors(ref, where: str, lexicon: Optional[Lexicon]) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{where}: must be an object with subject and attribute"]
    errs = []
    if set(ref) != {"subject", "attribute"}:
        errs.append(f"{where}: must hold exactly subject and attribute")
    errs += _fact_errors(ref.get("subject"), ref.get("attribute"), where, lexicon)
    return errs


def _fact_errors(subject, attribute, where: str, lexicon: Optional[Lexicon]) -> list[str]:
    errs = []
    if not _is_name(subject):
        errs.append(f"{where}.subject: must be a name of 1 to 120 characters")
    if not isinstance(attribute, str) or not _ATTR_RE.match(attribute):
        errs.append(f"{where}.attribute: must match ^[a-z][a-z0-9_]*$")
    if errs or lexicon is None:
        return errs
    if lexicon.resolve(subject) is None:
        errs.append(f"{where}.subject: {subject!r} is not a lexicon name")
    elif not lexicon.has_attribute(subject, attribute):
        errs.append(f"{where}.attribute: {lexicon.resolve(subject)!r} has no attribute {attribute!r}")
    return errs


def shape_errors(entry: dict, lexicon: Optional[Lexicon] = None) -> list[str]:
    """entry.schema.json by hand, plus: names are lexicon names, attributes exist
    for their subject, an at_event's event is a lexicon event with a date fact.
    """
    if not isinstance(entry, dict):
        return ["an entry must be an object"]
    errs = []
    required = ("id", "type", "text", "form", "tag", "confidence")
    for k in required:
        if k not in entry:
            errs.append(f"missing {k}")
    for k in entry:
        if k not in required:
            errs.append(f"unknown field {k!r}")
    i = entry.get("id")
    if "id" in entry and (not isinstance(i, str) or not 1 <= len(i) <= 64 or not _ID_RE.match(i)):
        errs.append("id must be 1 to 64 letters, digits, '.', '_' or '-'")
    t = entry.get("type")
    if "type" in entry and t not in TYPES:
        errs.append(f"type must be one of {', '.join(TYPES)}")
    text = entry.get("text")
    if "text" in entry and (not isinstance(text, str) or not 1 <= len(text) <= 300 or not re.search(r"\S", text)):
        errs.append("text must be 1 to 300 characters with a non-space")
    if "tag" in entry and entry["tag"] not in ("true", "false"):
        errs.append("label must be true or false")
    c = entry.get("confidence")
    if "confidence" in entry and (not _is_number(c) or not 0.5 <= c <= 1):
        errs.append("confidence must be a number from 0.5 to 1")
    form = entry.get("form")
    if "form" in entry and not isinstance(form, dict):
        errs.append("form must be an object")
    elif isinstance(form, dict) and t in TYPES:
        keys = _FORM_KEYS[t]
        for k in keys:
            if k not in form:
                errs.append(f"form: a {t} needs {k}")
        for k in form:
            if k not in keys:
                errs.append(f"form: a {t} has no field {k!r}")
        if t == "compare":
            if "left" in form:
                errs += _ref_errors(form["left"], "form.left", lexicon)
            if "right" in form:
                errs += _ref_errors(form["right"], "form.right", lexicon)
            if "op" in form and form["op"] not in ("gt", "lt", "eq"):
                errs.append("form.op must be gt, lt or eq")
        else:
            link_key = "link" if t == "relation" else "attribute"
            if "subject" in form and link_key in form:
                errs += _fact_errors(form["subject"], form[link_key], "form", lexicon)
            for vk in ("value", "from", "to"):
                if vk in form:
                    errs += value_errors(form[vk], f"form.{vk}")
            if t == "change" and isinstance(form.get("from"), dict) and isinstance(form.get("to"), dict):
                if form["from"].get("kind") != form["to"].get("kind"):
                    errs.append("form: from and to must be of one kind")
            if t == "at_event" and "event" in form:
                ev = form["event"]
                if not _is_name(ev):
                    errs.append("form.event: must be a name of 1 to 120 characters")
                elif lexicon is not None:
                    if not lexicon.is_event(ev):
                        errs.append(f"form.event: {ev!r} is not a lexicon event")
                    elif lexicon.event_date_attr(ev) is None:
                        errs.append(f"form.event: {ev!r} has no date fact to judge it on")
            if t == "relation" and "target" in form and "attribute" in form:
                errs += _fact_errors(form["target"], form["attribute"], "form.target", lexicon)
    return errs


# ------------------------------------------------------------------ grammar


def _inside(pos: int, spans) -> bool:
    return any(a <= pos < b for a, b in spans)


def _span_inside(span, spans) -> bool:
    return any(a <= span[0] and span[1] <= b for a, b in spans)


class _Sentence:
    def __init__(self, text: str, lexicon: Lexicon):
        self.text = text
        self.mentions = lexicon.find_mentions(text)
        self.readings = V.read(text)
        self.negations = S.find_negations(text)

    def spans_of(self, canon: str) -> list[tuple[int, int]]:
        return [(m.start, m.end) for m in self.mentions if m.subject == canon]


def _same_kind(r: V.Reading, v: Value) -> bool:
    """Would reading r be "another value of the claim's kind" next to v?"""
    o = r.value
    if o.kind != v.kind:
        return False
    if v.kind == "money":
        return o.currency == v.currency and o.per == v.per
    if v.kind == "quantity":
        uv = V.canonical_unit(v.unit)
        if uv:
            uo = V.canonical_unit(o.unit)
            return bool(uo) and V._PHYS_DIM[uo][0] == V._PHYS_DIM[uv][0]
        noun = V.singular(v.unit or "")
        return noun in r.nouns or V.singular(o.unit or "") == noun
    return True


def _name_spans(sent: _Sentence, name: str, lexicon: Lexicon) -> list[tuple[int, int]]:
    """Where the sentence names `name` (any spelling the lexicon gives it, or the
    name itself as whole words, any case, spaces optional), never inside the
    longer name of another entity.
    """
    canon = lexicon.resolve(name)
    spans = sent.spans_of(canon) if canon else []
    others = [(m.start, m.end) for m in sent.mentions if m.subject != canon]
    for m in _name_pattern(name).finditer(sent.text):
        if not any(a < m.end() and m.start() < b for a, b in others):
            spans.append(m.span())
    return sorted(set(spans))


def _stated_value(sent, v: Value, needed, lexicon, errs, label="value"):
    """Check the sentence states v once, plainly, with no other value of its kind.
    Returns the spans of the stated value (for the date and time-word checks).
    """
    if v.kind == "name":
        spans = _name_spans(sent, str(v.value), lexicon)
        spans = [s for s in spans if not _span_inside(s, needed)] or spans
        if not spans:
            errs.append(f"the sentence does not name the {label} {v.value!r}")
        return spans
    readings = [r for r in sent.readings if not _inside(r.num_start, needed)]
    hits = [r for r in readings if V.states_value(r, v)]
    if not hits:
        errs.append(f"the sentence does not state the {label} {V.format_value(v)!r} as value-forms.md writes it")
        return []
    hit = hits[0]
    for r in readings:
        if r is not hit and _same_kind(r, v):
            errs.append(f"another value of the {label}'s kind: {sent.text[r.start:r.end]!r}")
    return [(hit.start, hit.end)]


def _other_names(sent, allowed, subject_canons, lexicon) -> list[str]:
    """Names other than the allowed ones, for name claims ("no other entity")."""
    out = []
    for m in sent.mentions:
        if m.subject not in subject_canons and not _span_inside((m.start, m.end), allowed):
            out.append(m.surface)
    first = re.match(r"\s*\S+", sent.text)
    first_end = first.end() if first else 0
    for m in _CAP_WORD.finditer(sent.text):
        if m.start() < first_end or _span_inside(m.span(), allowed):
            continue
        if any(mn.start <= m.start() < mn.end for mn in sent.mentions):
            continue
        out.append(m.group(0))
    return out


def _date_and_time_errors(sent, allowed, errs) -> None:
    for w, a, b in C.own_dates_outside(sent.text, allowed):
        errs.append(f"a date of its own: {w!r}")
    for w, a, b in C.time_words_outside(sent.text, allowed):
        errs.append(f"a time word: {w!r}")


def _boolean_errors(sent, attr: str, value: bool, errs, polarity_text: Optional[str] = None) -> list:
    spans = C.attribute_word_spans(sent.text, attr)
    if not spans:
        errs.append(f"the sentence lacks the attribute in words: {C.attribute_words(attr)!r}")
        return []
    states = not S.find_negations(polarity_text if polarity_text is not None else sent.text)
    if states != bool(value):
        errs.append(f"the sentence states {'yes' if states else 'no'}, the claim {'yes' if value else 'no'}")
    return spans


def _check_single(sent: _Sentence, kind: str, form: dict, lexicon: Lexicon) -> list[str]:
    """fact, at_event and relation: one sentence holds subject, value (and event/link)."""
    errs: list[str] = []
    subject = lexicon.resolve(form["subject"])
    subj_spans = sent.spans_of(subject)
    if not subj_spans:
        errs.append(f"the sentence does not name {subject!r}")
    needed = list(subj_spans)
    allowed = list(subj_spans)
    canons = {subject}
    if kind == "at_event":
        event = lexicon.resolve(form["event"])
        ev = [e for e in C.find_event_phrases(sent.text, lexicon) if e[0] == event]
        if not ev:
            errs.append(f"no event phrase (at, during, on the day of, at the time of) right before {event!r}")
        else:
            needed += [(e[1], e[2]) for e in ev]
            allowed += [(e[1], e[2]) for e in ev]
        canons.add(event)
    if kind == "relation":
        link_spans = C.attribute_word_spans(sent.text, form["link"])
        if not link_spans:
            errs.append(f"the sentence lacks the relation words {C.attribute_words(form['link'])!r}")
        allowed += link_spans
        target = lexicon.resolve(form["target"])
        allowed += sent.spans_of(target)
        canons.add(target)
    v = Value.from_json(form["value"])
    if v.kind == "boolean":
        allowed += _boolean_errors(sent, form["attribute"], v.value, errs)
    else:
        if sent.negations:
            errs.append(f"a negation: {sent.text[sent.negations[0][0]:sent.negations[0][1]]!r}")
        vspans = _stated_value(sent, v, needed, lexicon, errs)
        allowed += vspans
        if v.kind == "name":
            canon_v = lexicon.resolve(str(v.value))
            others = _other_names(sent, allowed, canons | ({canon_v} if canon_v else set()), lexicon)
            if others:
                errs.append(f"another name next to the claimed one: {others[0]!r}")
    _date_and_time_errors(sent, allowed, errs)
    return errs


def _attr_kind(attrs, subject: str, attribute: str) -> Optional[object]:
    if not attrs:
        return None
    spec = attrs.get((subject, attribute))
    if spec is None:
        for (s, a), sp in attrs.items():
            if a == attribute:
                spec = sp
                break
    return spec


def _spec_get(spec, key):
    if spec is None:
        return None
    return spec.get(key) if isinstance(spec, dict) else getattr(spec, key, None)


def _check_compare(sentences: list[_Sentence], form: dict, lexicon: Lexicon, claim_kind, attrs) -> list[str]:
    left = lexicon.resolve(form["left"]["subject"])
    right = lexicon.resolve(form["right"]["subject"])
    la, ra = form["left"]["attribute"], form["right"]["attribute"]
    if left == right and la == ra:
        return ["a fact does not compare with itself"]
    ls, rs = _attr_kind(attrs, left, la), _attr_kind(attrs, right, ra)
    kind = claim_kind or _spec_get(ls, "kind") or _spec_get(rs, "kind")
    errs: list[str] = []
    if kind is None:
        return ["cannot tell the kind of the compared facts (pass attrs or evidence['kind'])"]
    if kind in ("name", "boolean"):
        return [f"{kind} values do not compare"]
    if ls is not None and rs is not None:
        if _spec_get(ls, "kind") != _spec_get(rs, "kind"):
            return ["the two facts are of different kinds"]
        if kind == "money" and (_spec_get(ls, "currency"), _spec_get(ls, "per")) != (
            _spec_get(rs, "currency"), _spec_get(rs, "per")
        ):
            return ["the two prices differ in currency or period"]
        if kind in ("quantity", "duration"):
            probe = 1.0
            a = Value(kind, probe, _spec_get(ls, "unit"))
            b = Value(kind, probe, _spec_get(rs, "unit"))
            if V.compare_values(a, b) is None:
                return ["the two facts are in units that do not convert"]
    phrases = [(i, p) for i, s in enumerate(sentences) for p in C.op_phrases(s.text)]
    if len(phrases) != 1:
        return [f"the text must hold exactly one op phrase, it holds {len(phrases)}"]
    i, (fam, op, a, b) = phrases[0]
    sent = sentences[i]
    want = "date" if kind == "date" else "amount"
    if fam != want:
        errs.append(f"a {fam} phrase between {'dates' if want == 'date' else 'amounts'}")
    if op != form["op"]:
        errs.append(f"the phrase states {op}, the form {form['op']}")
    before = [m for m in sent.mentions if m.end <= a]
    after = [m for m in sent.mentions if m.start >= b]
    if not any(m.subject == left for m in before):
        errs.append(f"{left!r} is not named before the phrase")
    if not any(m.subject == right for m in after):
        errs.append(f"{right!r} is not named after the phrase")
    for m in before:
        if m.subject != left:
            errs.append(f"another name before the phrase: {m.surface!r}")
    for m in after:
        if m.subject != right:
            errs.append(f"another name after the phrase: {m.surface!r}")
    if sent.negations:
        errs.append(f"a negation: {sent.text[sent.negations[0][0]:sent.negations[0][1]]!r}")
    names = [(m.start, m.end) for m in sent.mentions if m.subject in (left, right)]
    for r in sent.readings:
        if not _inside(r.num_start, names):
            errs.append(f"a value: {sent.text[r.start:r.end]!r}")
    for m in re.finditer(r"\d", sent.text):
        if not _inside(m.start(), names):
            errs.append("a number in digits")
            break
    for m in _NUMBER_WORDS.finditer(sent.text):
        if not _inside(m.start(), names):
            errs.append(f"a number in words: {m.group(0)!r}")
    for w, x, y in S.find_yearless_date_words(sent.text):
        if not _span_inside((x, y), names):
            errs.append(f"a date word: {w!r}")
    for w, x, y in C.time_words_outside(sent.text, names + [(a, b)]):
        errs.append(f"a time word: {w!r}")
    return errs


def _side_value(text: str, a: int, b: Optional[int], v: Value, lexicon: Lexicon, from_end: bool) -> bool:
    """Does text[a:b] state v on its own (whole side for from-sides, first/last value otherwise)?"""
    seg = text[a:b] if b is not None else text[a:]
    if v.kind == "name":
        s = seg.strip()
        if from_end:
            m = None
            for m in _name_pattern(str(v.value)).finditer(s):
                pass
            return bool(m) and not s[m.end():].strip(" ,")
        if b is not None:
            return lexicon.resolve(s) == lexicon.resolve(str(v.value)) if lexicon.resolve(s) else name_key(s) == name_key(str(v.value))
        m = _name_pattern(str(v.value)).match(s)
        return bool(m)
    if v.kind == "boolean":
        return False
    rs = V.read(seg)
    if not rs:
        return False
    lead = len(seg) - len(seg.lstrip())
    if b is not None and not from_end:  # exact from-side of `from A to B`
        return len(rs) == 1 and rs[0].start == lead and rs[0].end == len(seg.rstrip()) and V.states_value(rs[0], v)
    if from_end:  # the value right before `, up from`
        r = rs[-1]
        return r.end == len(seg.rstrip()) and V.states_value(r, v)
    r = rs[0]
    return r.start == lead and V.states_value(r, v)


def _check_change(sent: _Sentence, form: dict, lexicon: Lexicon) -> list[str]:
    errs: list[str] = []
    subject = lexicon.resolve(form["subject"])
    if not sent.spans_of(subject):
        errs.append(f"the sentence does not name {subject!r}")
    f, t = Value.from_json(form["from"]), Value.from_json(form["to"])
    if f.kind == "boolean":
        return errs + ["a yes/no change is not written by this system"]
    if V.same_value(f, t):
        errs.append("from and to are the same value")
    good = []
    for c in C.find_change_phrases(sent.text):
        if c["style"] == "from_to":
            ok_from = _side_value(sent.text, c["from"][0], c["from"][1], f, lexicon, from_end=False)
            ok_to = _side_value(sent.text, c["to"][0], None, t, lexicon, from_end=False)
        else:
            ok_to = _side_value(sent.text, 0, c["to"][1], t, lexicon, from_end=True)
            ok_from = _side_value(sent.text, c["from"][0], None, f, lexicon, from_end=False)
        if ok_from and ok_to:
            good.append(c)
    if len(good) != 1:
        errs.append("no change phrase states from and to" if not good else "more than one change phrase")
        return errs
    c = good[0]
    if c["direction"]:
        if f.kind in ("name", "boolean"):
            errs.append(f"`{c['direction']}` gives an order names and yes/no do not have")
        else:
            cmp = V.compare_values(t, f)
            want = "gt" if c["direction"] == "up" else "lt"
            if cmp != want:
                errs.append(f"`{c['direction']}` does not match the values")
    if sent.negations:
        errs.append(f"a negation: {sent.text[sent.negations[0][0]:sent.negations[0][1]]!r}")
    return errs


def _entry_from_claim(claim: Claim) -> dict:
    return {"id": claim.id, "type": claim.type, "text": claim.text, "form": claim.form,
            "tag": claim.label, "confidence": claim.confidence}


def grammar_errors(entry: dict, lexicon: Lexicon, attrs=None, kind: Optional[str] = None) -> list[str]:
    """Re-read the entry's text against its form (claim-forms.md, value-forms.md).

    Assumes shape_errors() found nothing. kind is the compared facts' kind for
    a compare (else looked up in attrs).
    """
    text = entry["text"]
    if any(ch in V.INVISIBLE for ch in text):
        return ["the text holds an invisible character"]
    sentences = [_Sentence(s, lexicon) for s in split_sentences(text)]
    if not sentences:
        return ["the text holds no sentence"]
    t, form = entry["type"], entry["form"]
    if t == "compare":
        return _check_compare(sentences, form, lexicon, kind, attrs)
    best: Optional[list[str]] = None
    for sent in sentences:
        errs = _check_change(sent, form, lexicon) if t == "change" else _check_single(sent, t, form, lexicon)
        if not errs:
            return []
        if best is None or len(errs) < len(best):
            best = errs
    return best or ["no sentence holds the claim"]


def validate_entry(entry: dict, lexicon: Lexicon, attrs=None, kind: Optional[str] = None) -> list[str]:
    """[] when the referee would accept the entry (as written in a JSON example or a CSV row)."""
    errs = shape_errors(entry, lexicon)
    if errs:
        return errs
    try:
        return grammar_errors(entry, lexicon, attrs, kind)
    except Exception as exc:  # a crash is a rejection, never an acceptance
        return [f"validator error: {type(exc).__name__}: {exc}"]


def validate(claim: Claim, lexicon: Lexicon, attrs=None) -> list[str]:
    """[] means the referee would accept the claim; otherwise readable reasons.

    Checks the entry.schema.json shape and re-reads claim.text against
    claim.form by claim-forms.md and value-forms.md. A compare needs the kind of
    its facts: claim.evidence["kind"], or attrs (B's AttrSpec map).
    """
    kind = (claim.evidence or {}).get("kind") if claim.type == "compare" else None
    return validate_entry(_entry_from_claim(claim), lexicon, attrs, kind)


# ------------------------------------------------------------------ CLI


def kinds_from_forms(practice_csv: str) -> dict[tuple[str, str], dict]:
    """(subject, attribute) -> {kind, unit, currency, per} by majority over practice forms."""
    from arena.pages import read_rows

    votes: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for row in read_rows(practice_csv):
        for f in json.loads(row["form"]):
            v = f["value"]
            votes[(f["subject"], f["attribute"])][
                (v["kind"], v.get("unit"), v.get("currency"), v.get("per"))
            ] += 1
    out = {}
    for key, c in votes.items():
        (kind, unit, cur, per), n = c.most_common(1)[0]
        out[key] = {"kind": kind, "unit": unit, "currency": cur, "per": per, "n_seen": n}
    return out


def _cli_attrs():
    try:
        from arena.attrs import load_attrs  # B's module, present after the merge

        return load_attrs()
    except Exception:
        pass
    if os.path.exists("data/practice.csv"):
        return kinds_from_forms("data/practice.csv")
    return None


def _number(s):
    if isinstance(s, (int, float)):
        return s
    try:
        return float(str(s).strip().replace(",", "."))
    except ValueError:
        return s


def _entries_from_path(path: str) -> list[tuple[str, object]]:
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return [(path, json.load(f))]
    from arena.pages import read_rows

    out = []
    for n, row in enumerate(read_rows(path), start=2):
        e: dict = {}
        for k, v in row.items():
            if k is None:
                e["__extra__"] = v
                continue
            k = k.strip()
            if k == "form":
                try:
                    e["form"] = json.loads(v)
                except (TypeError, ValueError):
                    e["form"] = v
            elif k == "label":
                e["tag"] = v
            elif k == "confidence":
                e["confidence"] = _number(v)
            else:
                e[k] = v
        out.append((f"{path}:{n}", e))
    return out


def main(argv: list[str]) -> int:
    paths, lex_path, explain = [], None, False
    it = iter(argv)
    for a in it:
        if a == "--lexicon":
            lex_path = next(it)
        elif a == "--explain":
            explain = True
        else:
            paths.append(a)
    if not paths:
        print("usage: python -m arena.validate FILE.csv|ENTRY.json ... [--lexicon PATH] [--explain]")
        return 2
    if lex_path is None:
        lex_path = "/universe/lexicon.json" if os.path.exists("/universe/lexicon.json") else "data/lexicon.json"
    lexicon = Lexicon.load(lex_path)
    attrs = _cli_attrs()
    entries = [x for p in paths for x in _entries_from_path(p)]
    ids = Counter(
        (where.rsplit(":", 1)[0], e.get("id")) for where, e in entries if isinstance(e, dict) and not where.endswith(".json")
    )
    bad = 0
    for where, e in entries:
        errs = validate_entry(e, lexicon, attrs) if isinstance(e, dict) else ["not an object"]
        if isinstance(e, dict) and ids.get((where.rsplit(":", 1)[0], e.get("id")), 0) > 1:
            errs = errs + [f"id {e.get('id')!r} is not unique"]
        if errs:
            bad += 1
            print(f"INVALID {where} id={e.get('id') if isinstance(e, dict) else '?'}")
            for r in errs:
                print(f"    - {r}")
            if explain and isinstance(e, dict):
                print(f"      text: {e.get('text')!r}")
        elif explain:
            print(f"valid   {where} id={e.get('id')}")
    print(f"{len(entries)} rows, {len(entries) - bad} valid, {bad} invalid")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
