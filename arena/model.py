"""Shared data model for the Hype Arena solution.

FROZEN. Committed to main before the three agents branch. Any change needs
all three agents to agree, because every module imports from here.

Runtime constraints to remember when touching this file:
  - stdlib only (the run box is offline and the system may not be an LLM)
  - everything must be JSON-serialisable through to_json() for the baked files
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Literal, Optional, Union

AS_OF_DATE = "2026-10-29"  # judgement date for fact and compare entries

Kind = Literal[
    "quantity", "money", "percent", "date", "version", "duration", "name", "boolean"
]
ClaimType = Literal["fact", "compare", "change", "at_event", "relation"]
Label = Literal["true", "false"]
Period = Literal["day", "week", "month", "year"]

DURATION_UNITS = ("ms", "s", "min", "h", "day", "week", "month", "year")


@dataclass(frozen=True)
class Value:
    """A typed value, shaped like contracts/claimed_value.schema.json.

    value:    float for quantity/money/percent/duration,
              str for date (YYYY, YYYY-MM or YYYY-MM-DD) / version ("2.3", no v) / name,
              bool for boolean.
    unit:     quantity -> canonical unit symbol (GB, MB, kg, m, mAh, Hz, W, in)
              or singular counted noun (language, user, seat);
              duration -> one of DURATION_UNITS.
    currency: money only, ISO code (EUR).
    per:      money only, None means one-off.
    op:       only ever set on observations parsed from dataset-style text
              (over / under / at least). Never emitted in an entry.
    """

    kind: Kind
    value: Union[float, str, bool]
    unit: Optional[str] = None
    currency: Optional[str] = None
    per: Optional[Period] = None
    op: Optional[Literal["eq", "lt", "le", "gt", "ge"]] = None

    def to_json(self) -> dict:
        d: dict = {"kind": self.kind, "value": self.value}
        if self.kind in ("quantity", "duration"):
            d["unit"] = self.unit
        if self.kind == "money":
            d["currency"] = self.currency
            if self.per:
                d["per"] = self.per
        return d  # op is deliberately dropped: entries may not carry it

    @staticmethod
    def from_json(d: dict) -> "Value":
        return Value(
            kind=d["kind"],
            value=d["value"],
            unit=d.get("unit"),
            currency=d.get("currency"),
            per=d.get("per"),
            op=d.get("op"),
        )


@dataclass
class Mention:
    """A lexicon name found in a sentence (longest match wins)."""

    subject: str  # canonical lexicon subject name
    surface: str  # text as written
    start: int
    end: int


@dataclass
class ParsedValue:
    """A value read from a sentence by arena.grammar.values.parse_values."""

    value: Value
    start: int
    end: int
    negated: bool = False  # a negation earlier in the same clause
    approximate: bool = False  # about / ~ / or so
    range_end: bool = False  # 10-20 GB, between X and Y


@dataclass
class Row:
    id: str
    text: str


@dataclass
class Page:
    page_id: str  # e.g. "pg-0003"
    date: str  # YYYY-MM-DD
    rows: list[Row]


@dataclass
class Observation:
    """One (subject, attribute, value) stated by one sentence on one page."""

    subject: str
    attribute: str
    value: Value
    date: str  # page date, YYYY-MM-DD
    page_id: str
    row_id: str
    sentence: str
    subject_in_sentence: bool
    cues: frozenset[str] = field(default_factory=frozenset)
    # cue vocabulary (open, but use these names where they apply):
    #   speaker, gavin, testimonial, boast, hearsay, announce_future,
    #   stale_marker, table_cell, headline, press_release, release_notes
    label: Optional[Literal["true", "false", "unsure"]] = None  # practice rows only

    def key(self) -> tuple[str, str]:
        return (self.subject, self.attribute)


@dataclass
class Interval:
    """A period during which (subject, attribute) is believed to hold value."""

    subject: str
    attribute: str
    value: Value
    start: str  # YYYY-MM-DD, first date the value is believed to hold
    end: Optional[str]  # None -> still holds on AS_OF_DATE
    support: float  # weighted agreeing observations
    conflict: float  # weighted disagreeing observations inside the interval
    n_obs: int
    anchored: bool = False  # pinned by a labelled practice row


Timelines = dict[tuple[str, str], list[Interval]]  # intervals sorted by start


@dataclass
class Claim:
    """One output entry before and after rendering."""

    type: ClaimType
    form: dict  # exactly the form shape entry.schema.json wants; values via Value.to_json()
    label: Label
    evidence: dict  # features for calibrate, e.g.
    #   {"support": 7.0, "conflict": 0.0, "n_obs": 7, "volatility": 1,
    #    "kind": "money", "perturbed": False, "anchored": True,
    #    "days_since_last_obs": 3, "type": "fact"}
    text: Optional[str] = None
    confidence: Optional[float] = None
    id: Optional[str] = None


@dataclass
class AttrSpec:
    """What kind of value an attribute carries, learned from practice forms."""

    kind: Kind
    unit: Optional[str] = None
    currency: Optional[str] = None
    per: Optional[Period] = None
    n_seen: int = 0


ClaimStream = Iterator[Claim]
