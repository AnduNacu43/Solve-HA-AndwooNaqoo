import csv
import json

import pytest

from arena.model import Claim
from arena.writer import HEADER, Writer


def _claim(text, form, **kw):
    return Claim(type="fact", form=form, label="true", evidence={}, text=text,
                 confidence=0.8, **kw)


def test_header_is_on_disk_before_any_row(tmp_path):
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
    # flushed: readable before close
    rows = list(csv.DictReader(open(path, encoding="utf-8", newline="")))
    assert len(rows) == 1
    assert rows[0]["text"] == 'Hooly AI Pro costs €59 per month, "really".'
    assert json.loads(rows[0]["form"]) == form
    assert rows[0]["form"] == json.dumps(form, separators=(",", ":"), ensure_ascii=False)
    assert rows[0]["label"] == "true" and rows[0]["confidence"] == "0.8"
    w.close()


def test_ids_are_unique_and_patterned(tmp_path):
    w = Writer(str(tmp_path / "output.csv"))
    for _ in range(3):
        w.write(_claim("x.", {}))
    with pytest.raises(ValueError):
        w.write(_claim("x.", {}, id="c-000002"))
    w.close()
    ids = [r["id"] for r in csv.DictReader(open(tmp_path / "output.csv", encoding="utf-8"))]
    assert ids == ["c-000001", "c-000002", "c-000003"]


def test_confidence_is_clamped_and_compact(tmp_path):
    w = Writer(str(tmp_path / "output.csv"))
    for c in (1.0, 0.3, 0.87654):
        claim = _claim("x.", {})
        claim.confidence = c
        w.write(claim)
    w.close()
    confs = [r["confidence"] for r in csv.DictReader(open(tmp_path / "output.csv", encoding="utf-8"))]
    assert confs == ["1", "0.5", "0.877"]
