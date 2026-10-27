"""Stand-in for A's arena.lexicon.Lexicon: only what B uses.

B needs `aliases` (lowercased name or alias -> canonical subject) to make
name values written as aliases collide in timeline.build.
"""
from __future__ import annotations

import json
from typing import Optional


class Lexicon:
    def __init__(self, data: dict):
        self.subjects: dict[str, list[str]] = {s["name"]: list(s["attributes"]) for s in data["subjects"]}
        self.events: set[str] = set(data.get("events", []))
        self.aliases: dict[str, str] = {}
        for s in data["subjects"]:
            for n in [s["name"], *s.get("aliases", [])]:
                self.aliases[" ".join(n.split()).casefold()] = s["name"]

    @staticmethod
    def load(path: str) -> "Lexicon":
        with open(path, encoding="utf-8") as f:
            return Lexicon(json.load(f))

    def resolve(self, name: str) -> Optional[str]:
        return self.aliases.get(" ".join(name.split()).casefold())

    def has_attribute(self, subject: str, attr: str) -> bool:
        return attr in self.subjects.get(subject, ())
