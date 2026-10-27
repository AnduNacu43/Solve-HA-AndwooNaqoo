import json
import re
from pathlib import Path

import pytest

from arena.generate import deps
from arena.model import Claim
from arena.render import candidates, render, safe_attr_words

ROOT = Path(__file__).resolve().parents[2]
GOOD = sorted((ROOT / "contracts" / "examples" / "entry" / "good").glob("*.json"))
PLACEHOLDERS = {"subject", "value", "aw", "event", "link_words", "left", "right", "from", "to"}
MONTHS_ETC = {"january", "february", "march", "april", "may", "june", "july", "august",
              "september", "october", "november", "december", "spring", "summer",
              "autumn", "winter", "monday", "tuesday", "wednesday", "thursday", "friday",
              "saturday", "sunday"}


def _example_claim(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    f = raw["form"]
    kind = None
    if raw["type"] == "compare":
        kind = "date" if f["left"]["attribute"] == "date" else "money"
    return raw["text"], Claim(type=raw["type"], form=f, label=raw["tag"],
                              evidence={"kind": kind}, confidence=raw["confidence"],
                              id=raw["id"])


def test_frames_hold_nothing_of_their_own(templates):
    for key, frames in templates.items():
        for frame in frames:
            assert frame.endswith("."), (key, frame)
            names = set(re.findall(r"{(\w+)}", frame))
            assert names <= PLACEHOLDERS, (key, frame)
            bare = re.sub(r"{\w+}", " ", frame)
            words = [w.lower() for w in re.findall(r"[A-Za-z']+", bare)]
            assert not re.search(r"\d", bare), (key, frame)
            assert not set(words) & MONTHS_ETC, (key, frame)
            joined = " " + " ".join(words) + " "
            time_words = [t for t in deps.TIME_WORDS if f" {t} " in joined]
            if key.startswith("compare.date"):  # the date phrases' own words
                time_words = [t for t in time_words if t not in ("after", "before", "later", "earlier")]
            if key.startswith("at_event"):  # the event phrase "at the time of"
                time_words = [t for t in time_words if t != "at the time"]
            assert not time_words, (key, frame, time_words)
            negations = [w for w in words if w in deps.NEGATION_WORDS or w.endswith("n't")]
            if key.endswith(".false"):
                assert negations, (key, frame)
            else:
                assert not negations, (key, frame)


@pytest.mark.parametrize("path", GOOD, ids=[p.stem for p in GOOD])
def test_contract_examples_are_among_candidates_and_validate(path, lexicon, templates):
    text, claim = _example_claim(path)
    texts = candidates(claim, lexicon, templates)
    assert text in texts, texts
    claim.text = text
    assert deps.validate(claim, lexicon) == []


def test_render_is_deterministic(lexicon, templates):
    for path in GOOD:
        _, claim = _example_claim(path)
        first = render(claim, lexicon, templates)
        again = render(Claim(**{**claim.__dict__, "form": json.loads(json.dumps(claim.form))}),
                       lexicon, json.loads(json.dumps(templates)))
        assert first == again


def test_yes_no_claims_carry_attribute_words_and_polarity(lexicon, templates):
    form = {"subject": "Hooly", "attribute": "soc2_certified",
            "value": {"kind": "boolean", "value": False}}
    claim = Claim(type="fact", form=form, label="true", evidence={}, confidence=0.8)
    texts = candidates(claim, lexicon, templates)
    assert "Hooly is not SOC 2 certified." in texts
    claim.form = dict(form, value={"kind": "boolean", "value": True})
    assert candidates(claim, lexicon, templates) == ["Hooly is SOC 2 certified."]


@pytest.mark.parametrize("subject,attr", [
    ("Hooly Cloud", "uptime_last_quarter"),   # "last quarter" is a time word
    ("Hooly Board", "chair_since"),           # "since"
    ("Hooly Gemini", "p99_response_time"),    # a number
    ("Hooly Android 17", "on_device_gemini"),  # names another subject
])
def test_unsafe_attribute_words_are_withheld(lexicon, subject, attr):
    assert safe_attr_words(attr, lexicon, (subject,)) is None


def test_compare_never_writes_a_number_or_two_phrases(lexicon, templates):
    claim = Claim(type="compare", evidence={"kind": "quantity"}, label="true", confidence=0.8,
                  id="t-1", form={"left": {"subject": "Hooly Pixel 10", "attribute": "screen_size"},
                        "right": {"subject": "Hooly Pixel 9", "attribute": "screen_size"},
                        "op": "gt"})
    for text in candidates(claim, lexicon, templates):
        claim.text = text
        assert deps.validate(claim, lexicon) == [], text
