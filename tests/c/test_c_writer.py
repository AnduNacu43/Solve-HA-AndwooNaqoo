import csv
import json

import pytest

from arena.model import Claim
from arena.writer import HEADER, OutputFull, Writer


def _claim(text, form, **kw):
    return Claim(type="fact", form=form, label="true", evidence={}, text=text,
                 confidence=0.8, **kw)


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_header_is_published_before_any_row(tmp_path):
    path = tmp_path / "out" / "output.csv"
    w = Writer(str(path))
    assert path.read_text(encoding="utf-8") == ",".join(f'"{h}"' for h in HEADER) + "\n"
    w.close()


def test_quoting_survives_commas_quotes_newlines_and_unicode(tmp_path):
    path = tmp_path / "output.csv"
    w = Writer(str(path))
    form = {"subject": 'Say "hi", then\nleave', "attribute": "price",
            "value": {"kind": "money", "value": 59, "currency": "EUR", "per": "month"}}
    w.write(_claim('Hooly AI Pro costs €59 per month, "really".', form))
    w.close()
    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0]["text"] == 'Hooly AI Pro costs €59 per month, "really".'
    assert json.loads(rows[0]["form"]) == form
    assert rows[0]["form"] == json.dumps(form, separators=(",", ":"), ensure_ascii=False)
    assert rows[0]["label"] == "true" and rows[0]["confidence"] == "0.8"


def test_output_csv_only_ever_holds_complete_tables(tmp_path):
    path = tmp_path / "output.csv"
    w = Writer(str(path), checkpoint_rows=3, checkpoint_s=3600)
    w.write(_claim("a.", {}))
    w.write(_claim("b.", {}))
    assert _rows(path) == []                       # not published yet: header only
    w.write(_claim("c.", {}))                      # third row: checkpoint
    assert [r["text"] for r in _rows(path)] == ["a.", "b.", "c."]
    w.write(_claim("d.", {}))
    assert len(_rows(path)) == 3
    w.close()                                      # close publishes the rest
    assert [r["text"] for r in _rows(path)] == ["a.", "b.", "c.", "d."]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["output.csv"]


def test_ids_are_unique_and_patterned(tmp_path):
    w = Writer(str(tmp_path / "output.csv"))
    for _ in range(3):
        w.write(_claim("x.", {}))
    with pytest.raises(ValueError):
        w.write(_claim("x.", {}, id="c-000002"))
    w.close()
    assert [r["id"] for r in _rows(tmp_path / "output.csv")] == ["c-000001", "c-000002", "c-000003"]


def test_the_table_stops_at_its_size_limit(tmp_path):
    w = Writer(str(tmp_path / "output.csv"), max_bytes=400)
    with pytest.raises(OutputFull):
        for _ in range(100):
            w.write(_claim("A sentence of some length.", {"k": "v"}))
    w.close()
    assert (tmp_path / "output.csv").stat().st_size <= 400
    assert 0 < len(_rows(tmp_path / "output.csv")) < 100


def test_confidence_is_clamped_and_compact(tmp_path):
    w = Writer(str(tmp_path / "output.csv"))
    for c in (1.0, 0.3, 0.87654):
        claim = _claim("x.", {})
        claim.confidence = c
        w.write(claim)
    w.close()
    assert [r["confidence"] for r in _rows(tmp_path / "output.csv")] == ["1", "0.5", "0.877"]
