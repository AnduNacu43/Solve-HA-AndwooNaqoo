from arena.attrs import AttrMap, canonical_unit, infer_spec, spec_for, unit_dimension
from arena.model import AttrSpec, Value


def test_every_lexicon_pair_has_a_spec(attrs, lexicon_json):
    pairs = [(s["name"], a) for s in lexicon_json["subjects"] for a in s["attributes"]]
    assert len(pairs) == 514
    missing = [p for p in pairs if spec_for(attrs, *p) is None]
    assert missing == []


def test_known_kinds(attrs):
    price = spec_for(attrs, "Hooly AI Pro", "price")
    assert (price.kind, price.currency, price.per) == ("money", "EUR", "month")
    langs = spec_for(attrs, "Hooly Gemini", "languages")
    assert (langs.kind, langs.unit) == ("quantity", "language")
    assert spec_for(attrs, "Hooly Cloud", "launched").kind == "date"
    assert spec_for(attrs, "Hooly", "cto").kind == "name"
    assert spec_for(attrs, "Hooly", "soc2_certified").kind == "boolean"
    assert spec_for(attrs, "Hooly AI Pro", "free_trial").unit == "day"   # 25 day vs 1 week


def test_units_stored_as_practice_writes_them(attrs):
    screen = spec_for(attrs, "Hooly Pixel 10", "screen_size")
    assert screen.unit == "inch"
    assert canonical_unit(screen.unit) == "in"


def test_fallback_by_attribute_name(attrs):
    spec = spec_for(attrs, "Some New Product", "price")
    assert spec is not None and spec.kind == "money"
    assert spec_for(attrs, "Some New Product", "never_seen_attribute") is None


def test_fallback_on_a_plain_dict():
    plain = {("A", "price"): AttrSpec("money", currency="EUR", per="month", n_seen=3),
             ("B", "price"): AttrSpec("money", currency="EUR", n_seen=9)}
    assert spec_for(plain, "C", "price").per is None   # most seen wins
    assert isinstance(AttrMap(plain), dict)


def test_infer_spec_majority():
    vals = [Value("quantity", 3, unit="seat"), Value("quantity", 5, unit="seat"),
            Value("quantity", 1, unit="user"), Value("money", 9, currency="EUR", per="month")]
    spec = infer_spec(vals)
    assert (spec.kind, spec.unit, spec.n_seen) == ("quantity", "seat", 4)
    money = infer_spec([Value("money", 9, currency="EUR", per="month")] * 2 + [Value("money", 90, currency="EUR")])
    assert (money.kind, money.currency, money.per) == ("money", "EUR", "month")


def test_infer_spec_rejects_empty():
    import pytest
    with pytest.raises(ValueError):
        infer_spec([])


def test_canonical_units_are_case_sensitive_symbols():
    assert canonical_unit("m") == "m"          # metre, not million
    assert canonical_unit("gigabyte") == "GB"
    assert canonical_unit("mW") == "mW"
    assert canonical_unit("Languages") == "languages"
    assert unit_dimension("TB") == ("data", 1e12)
    assert unit_dimension("language") is None
