"""Claim -> one sentence in the referee's grammar (contracts/claim-forms.md).

Frames come from data/templates.json, keyed from most to least specific
("fact.money.price", "fact.money", "fact"). A frame is usable only when every
placeholder it names can be filled safely; attribute words that carry a digit,
a month, a time word, a negation, a number word or another subject's name are
withheld, so frames that need them drop out. The frame order inside a key is
rotated by a hash of the claim's form, so output is reproducible."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

import arena
from arena.generate import deps
from arena.model import Claim, Value

TEMPLATES_PATH = Path(arena.__file__).resolve().parent.parent / "data" / "templates.json"

# claim-forms.md: words a fact/at_event/relation/compare sentence may not hold
# outside the names, the value and the phrases. Union with A's lists at run time.
_SEASONS_DAYS = {"spring", "summer", "autumn", "winter", "monday", "tuesday",
                 "wednesday", "thursday", "friday", "saturday", "sunday"}
_NUMBER_WORDS = set(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty "
    "sixty seventy eighty ninety hundred dozen thousand million billion bn k".split())
_APPROX_WORDS = {"about", "around", "approximately", "approx", "roughly", "nearly",
                 "almost", "circa", "ca", "some", "estimated", "est"}
_COMPARE_WORDS = {"more", "less", "fewer", "higher", "lower", "greater", "larger",
                  "bigger", "longer", "shorter", "cheaper", "same", "equal", "than",
                  "as", "after", "before", "later", "earlier", "over", "under",
                  "above", "below"}
_BOOL_VERBS = {"is", "has", "had", "was", "raised", "passed", "offers", "supports",
               "can", "runs"}
_ADJ_ENDINGS = ("ed", "able", "ible", "ous", "al", "ive", "ic")


def load_templates(path: str | Path = TEMPLATES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+|\d+", text)


def unsafe_words(text: str) -> set[str]:
    """The words of text that a claim sentence may not hold on their own."""
    lower = [w.lower() for w in _words(text)]
    joined = " " + " ".join(lower) + " "
    bad = set()
    months = {m.lower() for m in deps.MONTH_WORDS} | _SEASONS_DAYS
    for w in lower:
        if (w.isdigit() or w in deps.NEGATION_WORDS or w.endswith("n't")
                or w in months or w in _NUMBER_WORDS or w in _APPROX_WORDS):
            bad.add(w)
    for tw in deps.TIME_WORDS:
        if f" {tw} " in joined:
            bad.add(tw)
    for period in ("week", "month", "quarter", "year"):  # A refuses "this year" too
        if f" this {period} " in joined:
            bad.add(f"this {period}")
    return bad


def safe_attr_words(attr: str, lexicon, own_subjects: tuple[str, ...],
                    for_compare: bool = False) -> Optional[str]:
    """Attribute words fit to sit in a claim sentence, or None."""
    aw = deps.attribute_words(attr)
    if re.search(r"\d", aw) or unsafe_words(aw):
        return None
    if any(m.subject not in own_subjects for m in lexicon.find_mentions(aw)):
        return None
    if for_compare:
        if len(aw.split()) > 3 or {w.lower() for w in aw.split()} & _COMPARE_WORDS:
            return None
    return aw


def bool_shape(aw: str) -> str:
    words = aw.lower().split()
    if words[0] in _BOOL_VERBS:
        return "verb"
    if len(words) > 1 and words[0].endswith("s") and not words[0].endswith("ss"):
        return "verb"  # chairs audit committee
    if words[-1].endswith(_ADJ_ENDINGS) or words[0] in ("open", "fully"):
        return "adj"
    return "noun"


def mid(name: str) -> str:
    """A name as written mid-sentence ("The May 2026 outage" -> "the May 2026 outage")."""
    return "the" + name[3:] if name.startswith("The ") else name


def _date_shape(aw: Optional[str], value: Value) -> Optional[str]:
    if not aw or " " in aw or not aw.endswith("ed"):
        return None
    precision = {4: "year", 7: "month", 10: "day"}.get(len(str(value.value)), "day")
    return f"verb.{precision}"


def _form_hash(claim: Claim) -> int:
    raw = json.dumps([claim.type, claim.form], sort_keys=True, ensure_ascii=False)
    return int(hashlib.md5(raw.encode("utf-8")).hexdigest()[:8], 16)


def _value_keys(prefix: str, value: Value, attr: str, aw: Optional[str],
                polarity_words: Optional[str]) -> list[str]:
    k = value.kind
    if k == "boolean":
        if not polarity_words:
            return []
        pol = "true" if value.value else "false"
        return [f"{prefix}.boolean.{bool_shape(polarity_words)}.{pol}"]
    keys = [f"{prefix}.{k}.{attr}"]
    if k == "date" and _date_shape(aw, value):
        keys.append(f"{prefix}.date.{_date_shape(aw, value)}")
    if k == "quantity" and aw and value.unit and value.unit.lower() in aw.lower():
        keys.append(f"{prefix}.quantity.counted")  # "12 languages" names the attribute
    return keys + [f"{prefix}.{k}", prefix]


def _context(claim: Claim, lexicon) -> tuple[dict, list[str]]:
    f, t = claim.form, claim.type
    ctx: dict[str, str] = {}
    if t in ("fact", "at_event", "relation"):
        value = Value.from_json(f["value"])
        subject = f["subject"]
        own = (subject, f.get("target") or subject, f.get("event") or subject)
        ctx["subject"] = mid(subject)
        aw = safe_attr_words(f["attribute"], lexicon, own)
        bool_words = deps.attribute_words(f["attribute"]) if value.kind == "boolean" else None
        if bool_words and unsafe_words(bool_words) - {w for w in bool_words.lower().split() if w.isdigit()}:
            bool_words = None
        if aw:
            ctx["aw"] = aw
        if bool_words:
            ctx["aw"] = bool_words
        if value.kind != "boolean":
            ctx["value"] = deps.format_value(value)
        if t == "at_event":
            ctx["event"] = mid(f["event"])
        if t == "relation":
            link = deps.attribute_words(f["link"])
            if unsafe_words(link) - {w for w in link.lower().split() if w.isdigit()}:
                return ctx, []
            ctx["link_words"] = link
        return ctx, _value_keys(t, value, f["attribute"], aw, bool_words)
    if t == "compare":
        left, right = f["left"], f["right"]
        ctx["left"], ctx["right"] = mid(left["subject"]), mid(right["subject"])
        kind = claim.evidence.get("kind")
        if left["attribute"] == right["attribute"]:
            aw = safe_attr_words(left["attribute"], lexicon,
                                 (left["subject"], right["subject"]), for_compare=True)
            if aw:
                ctx["aw"] = aw
        else:
            aw = None
        op = f["op"]
        if kind == "date":
            keys = [f"compare.date.{left['attribute']}.{op}"]
            if aw and " " not in aw and aw.endswith("ed"):
                keys.append(f"compare.date.verb.{op}")
            return ctx, keys + [f"compare.date.{op}"]
        keys = [f"compare.{kind}.{left['attribute']}.{op}"]
        if kind == "quantity" and aw and re.search(r"[^s]s$", aw):
            keys.append(f"compare.quantity.plural.{op}")
        return ctx, keys + [f"compare.{kind}.{op}", f"compare.amount.{op}"]
    if t == "change":
        a, b = Value.from_json(f["from"]), Value.from_json(f["to"])
        ctx["subject"] = mid(f["subject"])
        if a.kind == "boolean":
            words = deps.attribute_words(f["attribute"])
            if (unsafe_words(words) - {w for w in words.lower().split() if w.isdigit()}
                    or {"to", "from"} & set(words.lower().split())):
                return ctx, []
            ctx["from"] = words if a.value else f"not {words}"
            ctx["to"] = words if b.value else f"not {words}"
            return ctx, ["change.boolean"]
        aw = safe_attr_words(f["attribute"], lexicon, (f["subject"],))
        if aw and not ({"to", "from", "up", "down"} & set(aw.lower().split())):
            ctx["aw"] = aw
        ctx["from"], ctx["to"] = deps.format_value(a), deps.format_value(b)
        order = deps.compare_values(b, a)
        keys = [f"change.{a.kind}.{f['attribute']}"]
        if order == "gt":
            keys.append("change.ordered.up")
        elif order == "lt":
            keys.append("change.ordered.down")
        return ctx, keys + ["change"]
    return ctx, []


def candidates(claim: Claim, lexicon, templates: dict) -> list[str]:
    """Every sentence this claim can be written as, best first, deduplicated."""
    try:
        ctx, keys = _context(claim, lexicon)
    except (ValueError, KeyError, TypeError, IndexError):
        return []
    rot = _form_hash(claim)
    out: list[str] = []
    for key in keys:
        frames = templates.get(key) or []
        # frames that say which attribute the claim is about come first
        groups = [[f for f in frames if "{aw}" in f], [f for f in frames if "{aw}" not in f]]
        ordered = []
        for group in groups:
            if group:
                r = rot % len(group)
                ordered += group[r:] + group[:r]
        for frame in ordered:
            try:
                text = frame.format_map(ctx)
            except KeyError:
                continue
            text = re.sub(r"\s+", " ", text).strip()
            text = text[0].upper() + text[1:]
            if text not in out and len(text) <= 300:
                out.append(text)
    return out


def render(claim: Claim, lexicon, templates: dict) -> str:
    """The claim's sentence: the best usable frame for its type, kind and attribute.
    Raises ValueError when no frame fits."""
    texts = candidates(claim, lexicon, templates)
    if not texts:
        raise ValueError(f"no frame fits {claim.type} {claim.form}")
    return texts[0]
