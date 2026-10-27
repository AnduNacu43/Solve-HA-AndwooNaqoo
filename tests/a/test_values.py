"""contracts/value-forms.md tables, the claimed_value examples, and round trips."""
import glob
import json

import pytest

from arena.grammar.values import compare_values, format_value, parse_values, read, same_value
from arena.model import Value
from arena.validate import value_errors


def V(kind, value, unit=None, currency=None, per=None, op=None):
    return Value(kind, float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value,
                 unit, currency, per, op)


READS = [
    ("128 GB of storage", V("quantity", 128, "GB")),
    ("128GB", V("quantity", 128, "GB")),
    ("2 terabytes", V("quantity", 2, "TB")),
    ("a 5,000 mAh battery", V("quantity", 5000, "mAh")),
    ("weighs 1.2 kg", V("quantity", 1.2, "kg")),
    ('a 6.1" display', V("quantity", 6.1, "in")),
    ("a 6.1-inch display", V("quantity", 6.1, "in")),
    ("3.2 GHz", V("quantity", 3.2, "GHz")),
    ("a 65-watt charger", V("quantity", 65, "W")),
    ("water resistant to 100 m", V("quantity", 100, "m")),
    ("1 GB", V("quantity", 1000, "MB")),
    ("speaks 40 languages", V("quantity", 40, "language")),
    ("speaks forty languages", V("quantity", 40, "language")),
    ("trusted by 10,000 companies", V("quantity", 10000, "company")),
    ("1,200 paying customers", V("quantity", 1200, "customer")),
    ("10,000 of our customers", V("quantity", 10000, "customer")),
    ("1.2 million users", V("quantity", 1200000, "user")),
    ("1M tests", V("quantity", 1000000, "test")),
    ("10k steps", V("quantity", 10000, "step")),
    ("twenty-four engineers", V("quantity", 24, "engineer")),
    ("a dozen partners", V("quantity", 12, "partner")),
    ("12 people", V("quantity", 12, "person")),
    ("zero outages", V("quantity", 0, "outage")),
    ("2,048 customers", V("quantity", 2048, "customer")),
    ("speaks 30 languages and never misses a beat", V("quantity", 30, "language")),
    ("€49 a month", V("money", 49, currency="EUR", per="month")),
    ("€49/mo", V("money", 49, currency="EUR", per="month")),
    ("49 euros per month", V("money", 49, currency="EUR", per="month")),
    ("EUR 49 monthly", V("money", 49, currency="EUR", per="month")),
    ("€49,99 a month", V("money", 49.99, currency="EUR", per="month")),
    ("€10 per user per month", V("money", 10, currency="EUR", per="month")),
    ("AI Pro from €39/month", V("money", 39, currency="EUR", per="month")),
    ("£9 a week", V("money", 9, currency="GBP", per="week")),
    ("€490 per annum", V("money", 490, currency="EUR", per="year")),
    ("$299.99", V("money", 299.99, currency="USD")),
    ("US$12", V("money", 12, currency="USD")),
    ("a €12M seed round", V("money", 12000000, currency="EUR")),
    ("€1.2bn", V("money", 1200000000, currency="EUR")),
    ("1,999 lei", V("money", 1999, currency="RON")),
    ("€49 a month or €490 a year", V("money", 490, currency="EUR", per="year")),
    ("99.99% uptime", V("percent", 99.99)),
    ("99.9 % uptime", V("percent", 99.9)),
    ("50 percent", V("percent", 50)),
    ("50 per cent", V("percent", 50)),
    ("fifty percent", V("percent", 50)),
    ("99.999% uptime", V("percent", 99.999)),
    ("2026-03-12", V("date", "2026-03-12")),
    ("2026-03", V("date", "2026-03")),
    ("12 March 2026", V("date", "2026-03-12")),
    ("12th March 2026", V("date", "2026-03-12")),
    ("the 12th of March 2026", V("date", "2026-03-12")),
    ("12March 2026", V("date", "2026-03-12")),
    ("March 12, 2026", V("date", "2026-03-12")),
    ("Mar 12th 2026", V("date", "2026-03-12")),
    ("since 1 Mar. 2026", V("date", "2026-03-01")),
    ("March 2026", V("date", "2026-03")),
    ("Sept 2026", V("date", "2026-09")),
    ("founded in 2025", V("date", "2025")),
    ("v2.3", V("version", "2.3")),
    ("version 2.3", V("version", "2.3")),
    ("ver. 2.3", V("version", "2.3")),
    ("v3", V("version", "3")),
    ("2.3.1", V("version", "2.3.1")),
    ("Hooly Gemini 2.2", V("version", "2.2")),
    ("battery lasts 14 days", V("duration", 14, "day")),
    ("a 14-day trial", V("duration", 14, "day")),
    ("a 14-day trial", V("duration", 2, "week")),
    ("14days", V("duration", 14, "day")),
    ("two weeks", V("duration", 2, "week")),
    ("a two-week trial", V("duration", 2, "week")),
    ("for a fortnight", V("duration", 2, "week")),
    ("24 hours", V("duration", 24, "h")),
    ("24h", V("duration", 24, "h")),
    ("30 min", V("duration", 30, "min")),
    ("p95 latency 1.8 s", V("duration", 1.8, "s")),
    ("500 ms", V("duration", 500, "ms")),
    ("12 months", V("duration", 1, "year")),
    ("for a week", V("duration", 1, "week")),
    ("over 10,000 customers", V("quantity", 10000, "customer", op="gt")),
    ("10,000+ customers", V("quantity", 10000, "customer", op="ge")),
    ("at least 12 languages", V("quantity", 12, "language", op="ge")),
    ("40 languages or more", V("quantity", 40, "language", op="ge")),
    ("uploads up to 25 MB", V("quantity", 25, "MB", op="le")),
    ("no more than 2 GB", V("quantity", 2, "GB", op="le")),
    ("2 GB or less", V("quantity", 2, "GB", op="le")),
    ("fewer than 50 employees", V("quantity", 50, "employee", op="lt")),
    ("under $300", V("money", 300, currency="USD", op="lt")),
    ("over 99% accuracy", V("percent", 99, op="gt")),
    ("answers in under a second", V("duration", 1, "s", op="lt")),
    ("within an hour", V("duration", 1, "h", op="le")),
    ("before March 2026", V("date", "2026-03", op="lt")),
    ("after 2025", V("date", "2025", op="gt")),
    ("by 1 May 2026", V("date", "2026-05-01", op="le")),
]


def _states(text, v):
    for p in parse_values(text):
        if p.negated or p.approximate or p.range_end:
            continue
        if same_value(p.value, v):
            return True
    return False


@pytest.mark.parametrize("text,value", READS)
def test_reads_as_shown(text, value):
    assert _states(text, value), [p.value for p in parse_values(text)]


NOT_READ = [
    ("12/03/2026", V("date", "2026-03-12")),
    ("12.03.2026", V("date", "2026-03-12")),
    ("March 12", V("date", "2026-03-12")),
    ("Q4 2026", V("date", "2026")),
    ("12 March 2026", V("date", "2026-03")),
    ("1.000.000 users", V("quantity", 1000000, "user")),
    ("1,5 GB", V("quantity", 1.5, "GB")),
    ("1,5 GB", V("quantity", 5, "GB")),
    ("99,9% uptime", V("percent", 9)),
    ("99,9% uptime", V("percent", 99.9)),
    ("1.500 mAh", V("quantity", 1500, "mAh")),
    ("1.500 mAh", V("quantity", 1.5, "mAh")),
    ("99.6% uptime", V("percent", 6)),
    ("we do not offer 99.9% uptime", V("percent", 99.9)),
    ("no 14-day trial", V("duration", 14, "day")),
    ("about 10,000 customers", V("quantity", 10000, "customer")),
    ("~10 GB", V("quantity", 10, "GB")),
    ("40 languages or so", V("quantity", 40, "language")),
    ("10–20 GB", V("quantity", 20, "GB")),
    ("10–20 GB", V("quantity", 10, "GB")),
    ("10 GB to 20 GB", V("quantity", 10, "GB")),
    ("between 10 and 20 GB", V("quantity", 20, "GB")),
    ("1 or 2 days", V("duration", 2, "day")),
    ("10m users", V("quantity", 10000000, "user")),
    ("2026 customers", V("quantity", 2026, "customer")),
    ("half an hour", V("duration", 30, "min")),
    ("1,000 requests a day", V("duration", 1, "day")),
    ("€49 a month", V("money", 49, currency="EUR")),
    ("5 pounds", V("money", 5, currency="GBP")),
    ("Hooly Gemini 11", V("version", "11")),
    ("v2.3", V("version", "2.3.0")),
    ("30 days", V("duration", 1, "month")),
    ("over 10,000 customers", V("quantity", 10000, "customer")),
    ("~ 10 GB", V("quantity", 10, "GB")),
    ("€49 a month, give or take", V("money", 49, currency="EUR", per="month")),
    ("12​GB", V("quantity", 12, "GB")),
    ("12 GB⁠", V("quantity", 12, "GB")),
]


@pytest.mark.parametrize("text,value", NOT_READ)
def test_not_read(text, value):
    assert not _states(text, value)


def test_more_than_two_words_between_number_and_noun():
    rs = read("10,000 of our happy loyal customers")
    assert not any("customer" in r.nouns for r in rs)
    rs = read("10,000 of our customers")
    assert any("customer" in r.nouns and r.value.value == 10000 for r in rs)


def test_soft_hyphen_inside_word_is_dropped():
    assert _states("speaks 12 lan­guages", V("quantity", 12, "language"))


def test_choice_of_kinds_reads_both():
    vals = [p.value for p in parse_values("€49 a month or €490 a year")]
    assert len(vals) == 2 and not any(p.range_end for p in parse_values("€49 a month or €490 a year"))


def test_range_flags():
    ps = parse_values("between 10 and 20 GB")
    assert ps and all(p.range_end for p in ps)


def test_negation_after_value_does_not_count():
    ps = parse_values("speaks 30 languages and never misses a beat")
    assert ps and not ps[0].negated


def test_comparison_words_are_not_negation():
    ps = parse_values("no more than 2 GB")
    assert ps[0].value.op == "le" and not ps[0].negated


def _good_values():
    for path in sorted(glob.glob("contracts/examples/claimed_value/good/*.json")):
        with open(path, encoding="utf-8") as f:
            yield path, json.load(f)


def _bad_values():
    for path in sorted(glob.glob("contracts/examples/claimed_value/bad/*.json")):
        with open(path, encoding="utf-8") as f:
            yield path, json.load(f)


def test_examples_counted():
    assert len(list(_good_values())) == 14
    assert len(list(_bad_values())) == 19


@pytest.mark.parametrize("path,v", list(_good_values()))
def test_good_claimed_values(path, v):
    assert value_errors(v, path, allow_op=True) == []
    val = Value.from_json(v)
    if val.kind == "boolean":
        with pytest.raises(ValueError):
            format_value(val)
        return
    plain = Value(val.kind, val.value, val.unit, val.currency, val.per)
    text = format_value(plain)
    if val.kind == "name":
        assert text == val.value
        return
    ps = parse_values(text)
    assert len(ps) == 1 and same_value(ps[0].value, plain), (text, ps)


@pytest.mark.parametrize("path,v", list(_bad_values()))
def test_bad_claimed_values(path, v):
    assert value_errors(v, path, allow_op=True), path


def test_entries_refuse_op():
    assert value_errors({"kind": "quantity", "value": 10000, "unit": "customer", "op": "gt"}, "v")


def _practice_values():
    import csv

    seen = {}
    with open("data/practice.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for fact in json.loads(row["form"]):
                v = fact["value"]
                if v.get("op") or v["kind"] in ("boolean", "name"):
                    continue
                seen[json.dumps(v, sort_keys=True)] = v
    return list(seen.values())


@pytest.mark.parametrize("v", _practice_values(), ids=lambda v: json.dumps(v, sort_keys=True))
def test_format_round_trips_practice_values(v):
    val = Value.from_json(v)
    text = format_value(val)
    ps = parse_values(text)
    assert len(ps) == 1, (text, ps)
    p = ps[0]
    assert not (p.negated or p.approximate or p.range_end) and p.value.op is None
    assert same_value(p.value, val), (text, p.value)


def test_round_trip_random_values():
    import random

    rnd = random.Random(7)
    units = ["GB", "MB", "kg", "mAh", "language", "user", "person", "company", "watch", "in", "W", "Hz"]
    for _ in range(2000):
        k = rnd.choice(["quantity", "money", "percent", "duration", "date", "version"])
        if k == "quantity":
            v = Value(k, float(rnd.choice([rnd.randint(0, 10**7), round(rnd.uniform(0, 999), rnd.randint(1, 3))])),
                      rnd.choice(units))
        elif k == "money":
            v = Value(k, float(rnd.choice([rnd.randint(0, 10**6), round(rnd.uniform(0, 999), 2)])),
                      currency=rnd.choice(["EUR", "USD", "GBP", "CHF", "RON"]),
                      per=rnd.choice([None, "day", "week", "month", "year"]))
        elif k == "percent":
            v = Value(k, round(rnd.uniform(0, 100), rnd.randint(0, 3)))
        elif k == "duration":
            v = Value(k, float(rnd.choice([rnd.randint(0, 999), round(rnd.uniform(0, 99), 1)])),
                      rnd.choice(["ms", "s", "min", "h", "day", "week", "month", "year"]))
        elif k == "date":
            y, m, d = rnd.randint(1990, 2030), rnd.randint(1, 12), rnd.randint(1, 28)
            v = Value(k, rnd.choice([f"{y}", f"{y}-{m:02d}", f"{y}-{m:02d}-{d:02d}"]))
        else:
            v = Value(k, ".".join(str(rnd.randint(0, 30)) for _ in range(rnd.randint(1, 4))))
        text = format_value(v)
        ps = parse_values(text)
        assert len(ps) == 1 and same_value(ps[0].value, v) and ps[0].value.op is None, (v, text, ps)


def test_same_value_rules():
    assert same_value(V("duration", 14, "day"), V("duration", 2, "week"))
    assert same_value(V("quantity", 1, "GB"), V("quantity", 1000, "MB"))
    assert same_value(V("duration", 12, "month"), V("duration", 1, "year"))
    assert not same_value(V("duration", 30, "day"), V("duration", 1, "month"))
    assert not same_value(V("version", "2.3"), V("version", "2.3.0"))
    assert not same_value(V("date", "2026-03-12"), V("date", "2026-03"))
    assert not same_value(V("money", 49, currency="EUR", per="month"), V("money", 49, currency="EUR"))
    assert same_value(V("quantity", 6.1, "inch"), V("quantity", 6.1, "in"))
    assert same_value(V("quantity", 3, "languages"), V("quantity", 3, "language"))


def test_compare_values_rules():
    assert compare_values(V("money", 59, currency="EUR", per="month"), V("money", 49, currency="EUR", per="month")) == "gt"
    assert compare_values(V("money", 59, currency="EUR", per="month"), V("money", 49, currency="EUR", per="year")) is None
    assert compare_values(V("money", 59, currency="EUR"), V("money", 49, currency="USD")) is None
    assert compare_values(V("quantity", 1, "GB"), V("quantity", 999, "MB")) == "gt"
    assert compare_values(V("quantity", 1, "GB"), V("quantity", 999, "user")) is None
    assert compare_values(V("duration", 2, "week"), V("duration", 14, "day")) == "eq"
    assert compare_values(V("duration", 1, "month"), V("duration", 30, "day")) is None
    assert compare_values(V("date", "2026-03-24"), V("date", "2026-05-19")) == "lt"
    assert compare_values(V("date", "2026-03-24"), V("date", "2026-05")) is None
    assert compare_values(V("version", "2.10"), V("version", "2.9")) == "gt"
    assert compare_values(V("version", "2.3"), V("version", "2.3.0")) is None
    assert compare_values(V("name", "A"), V("name", "B")) is None
    assert compare_values(V("boolean", True), V("boolean", False)) is None
