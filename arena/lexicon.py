"""The universe's lexicon: subjects, aliases, attributes and events.

Names match as whole words, in any case and spacing, and the longest name wins:
`Hooly AI Pro` names the plan, never the company `Hooly` (claim-forms.md).
Nothing here is specific to the practice lexicon; the run-time one is larger.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from arena.model import Mention

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", " ": " "})


def name_key(name: str) -> str:
    """Lookup key of a name: lower case, apostrophes unified, no whitespace."""
    return re.sub(r"\s+", "", name.translate(_APOSTROPHES).lower())


def _name_pattern(name: str) -> re.Pattern:
    tokens = name.translate(_APOSTROPHES).split()
    body = r"\s*".join(re.escape(tok).replace("'", "['’]") for tok in tokens)
    tail = r"(?![.,]\d)" if tokens and tokens[-1][-1:].isdigit() else ""  # `Android 16` is not in `Android 16.1`
    return re.compile(r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])" + tail, re.I)


@dataclass
class _Name:
    surface: str  # as the lexicon writes it
    subject: str  # canonical
    pattern: re.Pattern
    probe: str  # lower-case first token, a cheap pre-filter
    single_word: bool
    has_capital: bool


@dataclass
class Lexicon:
    """Subjects with their aliases and attributes, plus the event names."""

    subjects: dict[str, list[str]] = field(default_factory=dict)  # canonical name -> attributes
    events: set[str] = field(default_factory=set)  # canonical event names
    aliases: dict[str, str] = field(default_factory=dict)  # name_key(alias or name) -> canonical
    names: dict[str, list[str]] = field(default_factory=dict)  # canonical -> [name, *aliases]
    _names: list[_Name] = field(default_factory=list, repr=False)

    @staticmethod
    def load(path: str) -> "Lexicon":
        """Read a lexicon.json: {subjects: [{name, aliases, attributes}], events: [name]}."""
        with open(path, encoding="utf-8") as f:
            return Lexicon.from_dict(json.load(f))

    @staticmethod
    def from_dict(data: dict) -> "Lexicon":
        lex = Lexicon()
        for s in data.get("subjects", []):
            name = s["name"].strip()
            lex.subjects[name] = list(s.get("attributes", []))
            spellings = [name] + [a.strip() for a in s.get("aliases", []) if a and a.strip()]
            lex.names[name] = spellings
            for sp in spellings:
                lex.aliases.setdefault(name_key(sp), name)
        for ev in data.get("events", []):
            canon = lex.aliases.get(name_key(ev), ev.strip())
            lex.events.add(canon)
            if name_key(ev) not in lex.aliases:
                lex.aliases[name_key(ev)] = canon
                lex.names.setdefault(canon, [canon])
        seen = set()
        for canon, spellings in lex.names.items():
            for sp in spellings:
                k = (name_key(sp), canon)
                if k in seen:
                    continue
                seen.add(k)
                lex._names.append(
                    _Name(
                        surface=sp,
                        subject=lex.aliases.get(name_key(sp), canon),
                        pattern=_name_pattern(sp),
                        probe=sp.split()[0].lower().translate(_APOSTROPHES).split("'")[0],
                        single_word=len(sp.split()) == 1,
                        has_capital=any(ch.isupper() for ch in sp),
                    )
                )
        return lex

    def resolve(self, name: str) -> Optional[str]:
        """Canonical subject or event for a name or alias in any case and spacing."""
        if not isinstance(name, str):
            return None
        return self.aliases.get(name_key(name))

    def has_attribute(self, subject: str, attr: str) -> bool:
        """True when the subject (any of its names) has the attribute."""
        canon = self.resolve(subject)
        return canon is not None and attr in self.subjects.get(canon, ())

    def attributes(self, subject: str) -> list[str]:
        canon = self.resolve(subject)
        return list(self.subjects.get(canon, ())) if canon else []

    def is_event(self, name: str) -> bool:
        canon = self.resolve(name)
        return canon is not None and canon in self.events

    def event_date_attr(self, event: str) -> Optional[str]:
        """"date" when the event has a `date` attribute (its date fact), else None."""
        canon = self.resolve(event)
        if canon is None or canon not in self.events:
            return None
        return "date" if "date" in self.subjects.get(canon, ()) else None

    def find_mentions(self, sentence: str, any_case: bool = True) -> list[Mention]:
        """Every lexicon name in the sentence, as the referee reads names.

        Whole words, any case and spacing; the longest match wins and matches do
        not overlap, so `Hooly AI Pro` never yields `Hooly`. any_case=False is the
        stricter reading for universe pages: a one-word name the lexicon writes
        with a capital (`Search`, `Maps`, `Jules`) then needs a capital in the
        text too, while `outage` still matches in lower case.
        """
        low = sentence.lower().translate(_APOSTROPHES)
        squashed = re.sub(r"\s+", "", low)
        found: list[tuple[int, int, _Name]] = []
        for nm in self._names:
            if nm.probe not in low and nm.probe not in squashed:
                continue
            for m in nm.pattern.finditer(sentence):
                surface = m.group(0)
                if not any_case and nm.single_word and nm.has_capital and not any(c.isupper() for c in surface):
                    continue
                found.append((m.start(), m.end(), nm))
        found.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
        taken: list[tuple[int, int]] = []
        out: list[Mention] = []
        for a, b, nm in found:
            if any(a < tb and ta < b for ta, tb in taken):
                continue
            taken.append((a, b))
            out.append(Mention(subject=nm.subject, surface=sentence[a:b], start=a, end=b))
        out.sort(key=lambda m: m.start)
        return out
