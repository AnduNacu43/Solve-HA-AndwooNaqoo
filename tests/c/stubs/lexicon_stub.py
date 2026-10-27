"""Stub of A's arena.lexicon.Lexicon (00-shared.md §3), for C's tests and the
pre-merge image. Naive but honest: canonical names, aliases, whole-word
longest-match mentions."""
from __future__ import annotations

import json
import re
from typing import Optional

from arena.model import Mention


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


class Lexicon:
    def __init__(self, subjects: dict[str, list[str]], events: set[str],
                 aliases: dict[str, str]):
        self.subjects = subjects
        self.events = events
        self.aliases = aliases
        names = sorted(aliases, key=len, reverse=True)
        self._pattern = re.compile(
            r"(?<![\w])(" + "|".join(re.escape(n).replace(r"\ ", r"\s+") for n in names) + r")(?![\w])",
            re.IGNORECASE,
        )

    @staticmethod
    def load(path: str) -> "Lexicon":
        """Load {subjects:[{name, aliases, attributes}], events:[...]}."""
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        subjects: dict[str, list[str]] = {}
        aliases: dict[str, str] = {}
        for s in raw.get("subjects", []):
            subjects[s["name"]] = list(s.get("attributes", []))
            aliases[_norm(s["name"])] = s["name"]
            for a in s.get("aliases", []):
                aliases.setdefault(_norm(a), s["name"])
        events = set()
        for e in raw.get("events", []):
            canon = aliases.get(_norm(e), e)
            events.add(canon)
            aliases.setdefault(_norm(e), canon)
        return Lexicon(subjects, events, aliases)

    def resolve(self, name: str) -> Optional[str]:
        """Canonical subject name for any name or alias, any case/spacing."""
        if not isinstance(name, str):
            return None
        return self.aliases.get(_norm(name))

    def has_attribute(self, subject: str, attr: str) -> bool:
        canon = self.resolve(subject)
        return canon is not None and attr in self.subjects.get(canon, [])

    def find_mentions(self, sentence: str) -> list[Mention]:
        """Whole-word, case-insensitive, longest match wins, non-overlapping."""
        out = []
        for m in self._pattern.finditer(sentence):
            canon = self.resolve(m.group(1))
            if canon:
                out.append(Mention(canon, m.group(1), m.start(), m.end()))
        return out

    def event_date_attr(self, event: str) -> Optional[str]:
        """"date" when the event has a date attribute, else None."""
        canon = self.resolve(event)
        if canon in self.events and "date" in self.subjects.get(canon, []):
            return "date"
        return None
