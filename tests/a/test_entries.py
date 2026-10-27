"""The 7 good and 13 bad entry examples keep their verdicts."""
import glob
import json

import pytest

from arena.model import Claim
from arena.validate import main, validate, validate_entry


def _load(pattern):
    out = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as f:
            out.append((path, json.load(f)))
    return out


GOOD = _load("contracts/examples/entry/good/*.json")
BAD = _load("contracts/examples/entry/bad/*.json")


def test_counts():
    assert len(GOOD) == 7 and len(BAD) == 13


@pytest.mark.parametrize("path,e", GOOD, ids=[p for p, _ in GOOD])
def test_good_entries(lexicon, attrs, path, e):
    assert validate_entry(e, lexicon, attrs) == []


@pytest.mark.parametrize("path,e", BAD, ids=[p for p, _ in BAD])
def test_bad_entries(lexicon, attrs, path, e):
    assert validate_entry(e, lexicon, attrs)


def test_validate_claim_uses_evidence_kind(lexicon):
    c = Claim(type="compare", form={"left": {"subject": "Hooly Workspace", "attribute": "price"},
                                    "right": {"subject": "Hooly AI Pro", "attribute": "price"}, "op": "gt"},
              label="true", evidence={"kind": "money"}, text="Hooly Workspace costs more than Hooly AI Pro.",
              confidence=0.9, id="c1")
    assert validate(c, lexicon) == []
    c.evidence = {}
    assert validate(c, lexicon)  # the kind of the facts is unknown: reject


def test_lexicon_checks(lexicon, attrs):
    e = {"id": "x", "type": "fact", "text": "Hooly Foo costs €59 per month.", "tag": "true", "confidence": 0.9,
         "form": {"subject": "Hooly Foo", "attribute": "price",
                  "value": {"kind": "money", "value": 59, "currency": "EUR", "per": "month"}}}
    assert validate_entry(e, lexicon, attrs)
    e["form"]["subject"] = "hooly  ai pro"  # any case and spacing
    e["text"] = "Hooly AI Pro costs €59 per month."
    assert validate_entry(e, lexicon, attrs) == []
    e["form"]["attribute"] = "colours"
    assert validate_entry(e, lexicon, attrs)


def test_event_without_date_fact_is_refused(lexicon, attrs):
    e = {"id": "x", "type": "at_event", "text": "Hooly had 2,000 employees at Hooly Employee Survey.",
         "tag": "true", "confidence": 0.9,
         "form": {"subject": "Hooly", "attribute": "employees", "event": "Hooly Employee Survey",
                  "value": {"kind": "quantity", "value": 2000, "unit": "employee"}}}
    assert any("date fact" in r for r in validate_entry(e, lexicon, attrs))


def test_cli(tmp_path, capsys):
    good = sorted(glob.glob("contracts/examples/entry/good/*.json"))
    assert main(good) == 0
    assert "7 rows, 7 valid, 0 invalid" in capsys.readouterr().out
    csv_path = tmp_path / "out.csv"
    csv_path.write_text(
        "id,type,text,form,label,confidence\n"
        'e1,compare,Hooly Workspace costs more than Hooly AI Pro.,"{""left"": {""subject"": ""Hooly Workspace"", '
        '""attribute"": ""price""}, ""right"": {""subject"": ""Hooly AI Pro"", ""attribute"": ""price""}, '
        '""op"": ""gt""}",true,0.9\n'
        'e1,fact,Hooly AI Pro costs €59.,"{""subject"": ""Hooly AI Pro"", ""attribute"": ""price"", '
        '""value"": {""kind"": ""money"", ""value"": 59, ""currency"": ""EUR"", ""per"": ""month""}}",true,"0,9"\n',
        encoding="utf-8",
    )
    assert main([str(csv_path)]) == 1
    out = capsys.readouterr().out
    assert "2 rows, 0 valid, 2 invalid" in out and "not unique" in out
