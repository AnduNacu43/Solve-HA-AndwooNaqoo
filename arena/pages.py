"""Reading the universe: rows into pages, text into sentences."""
from __future__ import annotations

import csv
import io
import re

from arena.grammar.sentences import sentence_spans
from arena.model import Page, Row

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def split_sentences(text: str, lenient: bool = False) -> list[str]:
    """The sentences of a text, as value-forms.md splits them.

    A sentence ends at `.`, `!` or `?` before a space, or at a blank line; a
    single line break is a space; abbreviation points (e.g., Inc., J., No. 1)
    end nothing. lenient=True is for universe pages: it also keeps `ver. 2`,
    `Mar. 2026` together and ends a sentence after a closing quote.
    """
    return [text[a:b] for a, b in sentence_spans(text, lenient=lenient)]


def _natural_key(row_id: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", row_id)]


def normalize_date(s: str) -> str:
    """YYYY-MM-DD for the date forms a CSV export may hold (ISO, D.M.YYYY, D/M/YYYY)."""
    s = (s or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        return f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.match(r"^(\d{1,2})[ -]([A-Za-z]{3})[A-Za-z]*[ -](\d{4})", s)
    if m and m.group(2).lower() in _MONTHS:
        return f"{int(m.group(3)):04d}-{_MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return s


def read_rows(path: str) -> list[dict]:
    """Rows of a universe or practice CSV as dicts; `,` or `;` separated, UTF-8 (BOM ok)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        data = f.read()
    first = data.split("\n", 1)[0]
    delim = ";" if first.count(";") > first.count(",") else ","
    return list(csv.DictReader(io.StringIO(data), delimiter=delim))


def load_universe(path: str) -> list[Page]:
    """Pages of a universe CSV (`id,text,date`).

    Rows are taken in id order (natural sort, so p-2 < p-10); a page is a maximal
    run of consecutive rows sharing a date. Page ids are pg-0001, pg-0002, ...
    """
    rows = []
    for r in read_rows(path):
        rid = (r.get("id") or "").strip()
        text = r.get("text") or ""
        if not rid or not text.strip():
            continue
        rows.append((rid, text, normalize_date(r.get("date") or "")))
    rows.sort(key=lambda x: _natural_key(x[0]))
    pages: list[Page] = []
    for rid, text, d in rows:
        if not pages or pages[-1].date != d:
            pages.append(Page(page_id=f"pg-{len(pages) + 1:04d}", date=d, rows=[]))
        pages[-1].rows.append(Row(id=rid, text=text))
    return pages
