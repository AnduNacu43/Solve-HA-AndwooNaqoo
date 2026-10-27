"""The output table: /output/output.csv.

Rows are written to output.csv.writing, flushed one by one. Every
CHECKPOINT_ROWS rows or CHECKPOINT_S seconds a copy of it is renamed over
output.csv, and close() renames the working file itself, so output.csv is
always a complete table (the contract: a table still being written at the
deadline counts as it stands). The table never grows past MAX_BYTES."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import time

from arena.model import Claim

HEADER = ["id", "type", "text", "form", "label", "confidence"]
MAX_BYTES = 16 * 1024 * 1024 - 64 * 1024  # the contract's 16 MiB, with a margin
CHECKPOINT_ROWS = 250
CHECKPOINT_S = 2.0


class OutputFull(Exception):
    """The next row would take the table past its size limit."""


def _line(cells: list[str]) -> str:
    buf = io.StringIO()
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n").writerow(cells)
    return buf.getvalue()


class Writer:
    def __init__(self, path: str, max_bytes: int = MAX_BYTES,
                 checkpoint_rows: int = CHECKPOINT_ROWS, checkpoint_s: float = CHECKPOINT_S):
        """Start the table and publish it with its header at once (UTF-8, every
        cell quoted)."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self._work = path + ".writing"
        self._snapshot = path + ".snapshot"
        self.max_bytes = max_bytes
        self.checkpoint_rows = checkpoint_rows
        self.checkpoint_s = checkpoint_s
        self._f = open(self._work, "w", encoding="utf-8", newline="")
        header = _line(HEADER)
        self._f.write(header)
        self._bytes = len(header.encode("utf-8"))
        self._ids: set[str] = set()
        self.count = 0
        self.checkpoint()

    def next_id(self) -> str:
        """The id the next row gets: c-000001, c-000002, ..."""
        return f"c-{self.count + 1:06d}"

    def write(self, claim: Claim) -> None:
        """Write one row and flush it. Assigns a c-000001 style id when the claim
        has none; refuses a duplicate id; raises OutputFull past max_bytes."""
        if claim.id is None:
            claim.id = self.next_id()
        if claim.id in self._ids:
            raise ValueError(f"duplicate id {claim.id}")
        confidence = min(1.0, max(0.5, float(claim.confidence)))
        line = _line([
            claim.id,
            claim.type,
            claim.text,
            json.dumps(claim.form, separators=(",", ":"), ensure_ascii=False),
            claim.label,
            f"{confidence:.3f}".rstrip("0").rstrip("."),
        ])
        size = len(line.encode("utf-8"))
        if self._bytes + size > self.max_bytes:
            raise OutputFull(f"{self.count} rows, {self._bytes} bytes")
        self._f.write(line)
        self._f.flush()
        self._bytes += size
        self._ids.add(claim.id)
        self.count += 1
        if (self.count - self._published >= self.checkpoint_rows
                or time.time() - self._published_at >= self.checkpoint_s):
            self.checkpoint()

    def checkpoint(self) -> None:
        """Publish the rows written so far: copy the working file, then rename
        the copy over output.csv in one step."""
        self._f.flush()
        shutil.copyfile(self._work, self._snapshot)
        os.replace(self._snapshot, self.path)
        self._published = self.count
        self._published_at = time.time()

    def close(self) -> None:
        """Publish the finished table by renaming the working file over output.csv."""
        if self._f.closed:
            return
        self._f.flush()
        try:
            os.fsync(self._f.fileno())
        except OSError:
            pass
        self._f.close()
        os.replace(self._work, self.path)
        self._published = self.count
