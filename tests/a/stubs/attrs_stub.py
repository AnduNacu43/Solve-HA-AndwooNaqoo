"""Stand-in for B's arena.attrs until the merge: AttrSpecs by majority vote over practice forms."""
from __future__ import annotations

from typing import Optional

from arena.model import AttrSpec
from arena.validate import kinds_from_forms


def load_attrs(path: str = "data/practice.csv") -> dict[tuple[str, str], AttrSpec]:
    return {
        key: AttrSpec(kind=d["kind"], unit=d["unit"], currency=d["currency"], per=d["per"], n_seen=d["n_seen"])
        for key, d in kinds_from_forms(path).items()
    }


def spec_for(attrs, subject: str, attribute: str) -> Optional[AttrSpec]:
    spec = attrs.get((subject, attribute))
    if spec is not None:
        return spec
    for (s, a), sp in attrs.items():
        if a == attribute:
            return sp
    return None
