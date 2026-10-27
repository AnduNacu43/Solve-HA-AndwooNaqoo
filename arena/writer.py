"""The output table: /output/output.csv, written row by row so whatever is on
disk when the run ends is a complete, valid CSV."""
from __future__ import annotations

import csv
import json
import os

from arena.model import Claim

HEADER = ["id", "type", "text", "form", "label", "confidence"]


class Writer:
    def __init__(self, path: str):
        """Open path and write the header immediately (UTF-8, every cell quoted)."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self._f = open(path, "w", encoding="utf-8", newline="")
        self._csv = csv.writer(self._f, quoting=csv.QUOTE_ALL, lineterminator="\n")
        self._csv.writerow(HEADER)
        self._f.flush()
        self._ids: set[str] = set()
        self.count = 0

    def next_id(self) -> str:
        """The id the next row gets: c-000001, c-000002, ..."""
        return f"c-{self.count + 1:06d}"

    def write(self, claim: Claim) -> None:
        """Write one row and flush it. Assigns a c-000001 style id when the claim
        has none; refuses a duplicate id."""
        if claim.id is None:
            claim.id = self.next_id()
        if claim.id in self._ids:
            raise ValueError(f"duplicate id {claim.id}")
        confidence = min(1.0, max(0.5, float(claim.confidence)))
        self._csv.writerow([
            claim.id,
            claim.type,
            claim.text,
            json.dumps(claim.form, separators=(",", ":"), ensure_ascii=False),
            claim.label,
            f"{confidence:.3f}".rstrip("0").rstrip("."),
        ])
        self._f.flush()
        self._ids.add(claim.id)
        self.count += 1

    def close(self) -> None:
        if self._f.closed:
            return
        self._f.flush()
        try:
            os.fsync(self._f.fileno())
        except OSError:
            pass
        self._f.close()
