import json
from collections import Counter

import pytest

from arena.generate import GEN_CONFIG, deps, generate
from arena.generate.at_event import generate_at_events
from arena.generate.change import generate_changes
from arena.generate.compare import generate_compares
from arena.generate.fact import generate_facts
from arena.generate.perturb import perturbed_values
from arena.generate.relation import generate_relations
from arena.model import Value
from arena.render import candidates

GENERATORS = {"fact": generate_facts, "compare": generate_compares, "change": generate_changes,
              "at_event": generate_at_events, "relation": generate_relations}
FORM_KEYS = {"fact": {"subject", "attribute", "value"}, "compare": {"left", "right", "op"},
             "change": {"subject", "attribute", "from", "to"},
             "at_event": {"subject", "attribute", "event", "value"},
             "relation": {"subject", "link", "target", "attribute", "value"}}


@pytest.fixture(scope="module")
def claims(timelines, lexicon, attrs):
    return {t: list(g(timelines, lexicon, attrs, GEN_CONFIG)) for t, g in GENERATORS.items()}


@pytest.mark.parametrize("ctype", list(GENERATORS))
def test_each_generator_yields_both_labels_in_shape(claims, ctype):
    got = claims[ctype]
    assert got, ctype
    assert {c.label for c in got} == {"true", "false"}
    for c in got:
        assert c.type == ctype and set(c.form) == FORM_KEYS[ctype]
        assert c.evidence["type"] == ctype and "kind" in c.evidence
        for key in ("value", "from", "to"):
            if key in c.form:
                assert "op" not in c.form[key]


@pytest.mark.parametrize("ctype", list(GENERATORS))
def test_each_generators_claims_pass_the_validator(claims, ctype, lexicon, templates):
    """Every claim renders to a sentence the validator accepts, except claims
    whose name value the lexicon cannot resolve (a data gap) and a few whose
    attribute words cannot sit in a sentence (withheld on purpose, then dropped)."""
    failures, unrenderable = Counter(), 0
    for c in claims[ctype]:
        c.confidence = 0.8
        texts = candidates(c, lexicon, templates)
        if not texts:
            unrenderable += 1
            continue
        for text in texts:
            c.text = text
            errors = deps.validate(c, lexicon)
            if not errors:
                break
        if errors and not all("is not in the lexicon" in e for e in errors):
            failures[f"{errors[0]} | {c.text} | {json.dumps(c.form)}"] += 1
    assert not failures, failures.most_common(10)
    assert unrenderable <= max(2, 0.02 * len(claims[ctype])), unrenderable


def test_compare_ops_follow_current_values(claims, timelines, lexicon):
    for c in claims["compare"]:
        left, right = c.form["left"], c.form["right"]
        assert left != right
        a = deps.current(timelines[(left["subject"], left["attribute"])]).value
        b = deps.current(timelines[(right["subject"], right["attribute"])]).value
        assert a.kind not in ("name", "boolean")
        truth = deps.compare_values(a, b)
        assert (c.form["op"] == truth) == (c.label == "true")


def test_true_changes_change_and_happen_in_order(claims, timelines):
    for c in claims["change"]:
        a, b = Value.from_json(c.form["from"]), Value.from_json(c.form["to"])
        assert not deps.same_value(a, b)
        if c.label == "true":
            ivs = timelines[(c.form["subject"], c.form["attribute"])]
            ia = min(i for i, iv in enumerate(ivs) if deps.same_value(iv.value, a))
            assert any(deps.same_value(iv.value, b) for iv in ivs[ia + 1:])


def test_perturbed_values_keep_shape_and_are_never_seen(timelines, lexicon):
    checked = 0
    for (s, a), ivs in timelines.items():
        cur = deps.current(ivs)
        if cur is None:
            continue
        seen = [iv.value for iv in ivs]
        for v in perturbed_values(s, a, cur.value, seen, timelines, lexicon):
            assert v.kind == cur.value.kind
            assert (v.unit, v.currency, v.per) == (cur.value.unit, cur.value.currency, cur.value.per)
            assert not any(deps.same_value(v, x) for x in seen)
            if v.kind == "date":
                assert len(v.value) == len(cur.value.value)
            checked += 1
    assert checked > 500


def test_generate_interleaves_types_without_duplicates(timelines, lexicon, attrs):
    out = list(generate(timelines, lexicon, attrs))
    assert len(out) <= GEN_CONFIG["total"]
    keys = [json.dumps([c.type, c.form], sort_keys=True) for c in out]
    assert len(keys) == len(set(keys))
    assert len({c.type for c in out[:50]}) == 5
