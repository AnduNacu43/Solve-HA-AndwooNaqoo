"""Every accepted and refused row of contracts/claim-forms.md, as a case."""
import pytest

from arena.validate import validate_entry

PRO_59 = {"kind": "money", "value": 59, "currency": "EUR", "per": "month"}
PRO_49 = {"kind": "money", "value": 49, "currency": "EUR", "per": "month"}


def entry(type_, text, form):
    return {"id": "t1", "type": type_, "text": text, "form": form, "tag": "true", "confidence": 0.9}


def check(lexicon, attrs, e, accepted):
    errs = validate_entry(e, lexicon, attrs)
    if accepted:
        assert errs == [], errs
    else:
        assert errs, f"false accept: {e['text']!r}"


FACT_PRICE = [
    ("Hooly AI Pro costs €59 per month.", True),
    ("At €59 per month, Hooly AI Pro is our best seller.", True),
    ("Hooly AI Pro costs over €59 per month.", False),
    ("Hooly AI Pro costs about €59 per month.", False),
    ("Hooly AI Pro costs €59.", False),
    ("It costs €59 per month.", False),
    ("Hooly AI Pro is our plan. It costs €59 per month.", False),
    ("Hooly costs €59 per month.", False),
    ("Hooly AI Pro costs €59 per month, and never more.", False),
    ("Hooly AI Pro costs €59 per month or €590 per year.", True),
    ("Hooly AI Pro costs €59 per month, up from €49 per month.", False),
    ("In March 2026, Hooly AI Pro cost €59 per month.", False),
    ("In April, Hooly AI Pro cost €59 per month.", False),
    ("Hooly AI Pro used to cost €59 per month.", False),
]


@pytest.mark.parametrize("text,accepted", FACT_PRICE)
def test_fact_price(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly AI Pro", "attribute": "price", "value": PRO_59}
    check(lexicon, attrs, entry("fact", text, form), accepted)


FACT_SOC2 = [
    ("Hooly is not SOC 2 certified.", True),
    ("Hooly has never been SOC2-certified.", True),
    ("Hooly is fully SOC 2 certified.", False),
    ("Hooly has never passed a SOC 2 audit.", False),
    ("Hooly is not profitable.", False),
]


@pytest.mark.parametrize("text,accepted", FACT_SOC2)
def test_fact_yes_no(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly", "attribute": "soc2_certified", "value": {"kind": "boolean", "value": False}}
    check(lexicon, attrs, entry("fact", text, form), accepted)


COMPARE_PRICES = [
    ("Hooly Workspace costs more than Hooly AI Pro.", "gt", True),
    ("Hooly Workspace is more expensive than Hooly AI Pro.", "gt", True),
    ("The Workspace plan costs a higher monthly price than Hooly AI Pro.", "gt", True),
    ("Hooly Workspace costs the same as Hooly AI Pro.", "eq", True),
    ("Hooly Workspace costs as much as Hooly AI Pro.", "eq", True),
    ("Hooly Workspace costs more than Hooly AI Pro.", "lt", False),
    ("Hooly AI Pro costs less than Hooly Workspace.", "lt", False),
    ("Hooly Workspace costs more than its rivals.", "gt", False),
    ("Hooly Workspace outprices Hooly AI Pro.", "gt", False),
    ("Hooly Workspace does not cost more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace costs more than Hooly AI Pro, and less than Hooly AI Free.", "gt", False),
    ("Hooly Workspace is our biggest plan. It costs more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace costs more than Hooly.", "gt", False),
    ("Hooly Workspace comes after Hooly AI Pro.", "gt", False),
    ("Hooly Workspace costs more per month than Hooly AI Pro.", "gt", True),
    ("Hooly Workspace costs more than Hooly AI Pro. We checked in June 2026.", "gt", True),
    ("Hooly Workspace costs €100 more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace costs 100 more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace costs a hundred more than Hooly AI Pro.", "gt", False),
    ("In June 2026, Hooly Workspace cost more than Hooly AI Pro.", "gt", False),
    ("In June, Hooly Workspace cost more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace used to cost more than Hooly AI Pro.", "gt", False),
    ("Hooly Workspace cost more than Hooly AI Pro before the outage.", "gt", False),
]


@pytest.mark.parametrize("text,op,accepted", COMPARE_PRICES)
def test_compare_prices(lexicon, attrs, text, op, accepted):
    form = {"left": {"subject": "Hooly Workspace", "attribute": "price"},
            "right": {"subject": "Hooly AI Pro", "attribute": "price"}, "op": op}
    check(lexicon, attrs, entry("compare", text, form), accepted)


COMPARE_DATES = [
    ("Hooly I/O 2026 took place before the May 2026 outage.", "lt", True),
    ("Hooly I/O 2026 came earlier than the outage.", "lt", True),
    ("Hooly I/O took place on the same day as the outage.", "eq", True),
    ("Hooly I/O 2026 was more than the May 2026 outage.", "gt", False),
    ("Hooly I/O 2026 took place two weeks before the May 2026 outage.", "lt", False),
    ("Hooly I/O 2026 took place before the outage, in March 2026.", "lt", False),
]


@pytest.mark.parametrize("text,op,accepted", COMPARE_DATES)
def test_compare_dates(lexicon, attrs, text, op, accepted):
    form = {"left": {"subject": "Hooly I/O 2026", "attribute": "date"},
            "right": {"subject": "The May 2026 outage", "attribute": "date"}, "op": op}
    check(lexicon, attrs, entry("compare", text, form), accepted)


CHANGE = [
    ("Hooly AI Pro went from €49 per month to €59 per month.", True),
    ("The price of Hooly AI Pro rose from €49 per month to €59 per month in April.", True),
    ("Hooly AI Pro costs €59 per month, up from €49 per month.", True),
    ("Hooly AI Pro went up from €49 per month to €59 per month.", True),
    ("Hooly AI Pro costs €59 per month, down from €49 per month.", False),
    ("Hooly AI Pro went down from €49 per month to €59 per month.", False),
    ("Hooly AI Pro went from €59 per month to €49 per month.", False),
    ("Hooly AI Pro went from €49 to €59 per month.", False),
    ("Hooly AI Pro cost €49 per month and now costs €59 per month.", False),
    ("Hooly AI Pro never went from €49 per month to €59 per month.", False),
]


@pytest.mark.parametrize("text,accepted", CHANGE)
def test_change(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly AI Pro", "attribute": "price", "from": PRO_49, "to": PRO_59}
    check(lexicon, attrs, entry("change", text, form), accepted)


def test_change_of_names(lexicon, attrs):
    form = {"subject": "Hooly", "attribute": "cto", "from": {"kind": "name", "value": "Richard Hendrix"},
            "to": {"kind": "name", "value": "Bertram Gilfoil"}}
    check(lexicon, attrs, entry("change", "Hooly's CTO changed from Richard Hendrix to Bertram Gilfoil.", form), True)
    check(lexicon, attrs, entry("change", "Hooly's CTO went up from Richard Hendrix to Bertram Gilfoil.", form), False)
    check(lexicon, attrs, entry("change", "Hooly's CTO changed from Bertram Gilfoil to Richard Hendrix.", form), False)


AT_EVENT = [
    ("Hooly Gemini spoke 12 languages at Hooly I/O 2026.", True),
    ("At Hooly I/O, Hooly Gemini spoke a dozen languages.", True),
    ("Hooly Gemini supported 12 languages on the day of Hooly I/O 2026.", True),
    ("Hooly Gemini spoke 12 languages at the time of Hooly I/O 2026.", True),
    ("Hooly Gemini spoke 12 languages before Hooly I/O 2026.", False),
    ("Hooly Gemini spoke 12 languages in March.", False),
    ("At Hooly I/O 2026, Hooly spoke 12 languages.", False),
    ("Hooly Gemini spoke 12 languages at Hooly I/O 2026, up from 6 languages.", False),
    ("In March 2026, at Hooly I/O 2026, Hooly Gemini spoke 12 languages.", False),
]


@pytest.mark.parametrize("text,accepted", AT_EVENT)
def test_at_event(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly Gemini", "attribute": "languages", "event": "Hooly I/O 2026",
            "value": {"kind": "quantity", "value": 12, "unit": "language"}}
    check(lexicon, attrs, entry("at_event", text, form), accepted)


RELATION = [
    ("The CTO of Hooly joined on 1 July 2026.", True),
    ("Hooly's CTO started on 2026-07-01.", True),
    ("Hooly's chief technology officer joined on 1 July 2026.", False),
    ("Bertram Gilfoil joined Hooly on 1 July 2026.", False),
    ("The CTO joined on 1 July 2026.", False),
    ("The CTO of Hooly, who left on 3 May 2027, joined on 1 July 2026.", False),
    ("The CTO of Hooly joined on 1 July 2026, after Richard Hendrix.", False),
]


@pytest.mark.parametrize("text,accepted", RELATION)
def test_relation(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly", "link": "cto", "target": "Bertram Gilfoil", "attribute": "joined",
            "value": {"kind": "date", "value": "2026-07-01"}}
    check(lexicon, attrs, entry("relation", text, form), accepted)


FACT_NAME = [
    ("Bertram Gilfoil is the CTO of Hooly.", True),
    ("Hooly's CTO is Bertram Gilfoil.", True),
    ("Hooly's CTO is not Bertram Gilfoil.", False),
    ("Hooly's CTO is Bertram Gilfoil, not Richard Hendrix.", False),
    ("Hooly's CTO is Bertram Gilfoil and Dinesh Chugtay runs product.", False),
    ("Hooly's CTO is Richard Hendrix.", False),
]


@pytest.mark.parametrize("text,accepted", FACT_NAME)
def test_fact_name(lexicon, attrs, text, accepted):
    form = {"subject": "Hooly", "attribute": "cto", "value": {"kind": "name", "value": "Bertram Gilfoil"}}
    check(lexicon, attrs, entry("fact", text, form), accepted)


MORE_FACTS = [
    # (subject, attribute, value, text, accepted)
    ("Hooly Gemini", "version", {"kind": "version", "value": "2.2"}, "Hooly Gemini runs v2.2.", True),
    ("Hooly Gemini", "version", {"kind": "version", "value": "2.2"}, "Hooly Gemini 2.2 is the current release.", True),
    ("Hooly Gemini", "version", {"kind": "version", "value": "2.2"}, "Hooly Gemini runs v2.2, after v2.1.", False),
    ("Hooly Gemini", "version", {"kind": "version", "value": "11"}, "Hooly Gemini 11 is out.", False),
    ("Hooly Gemini", "languages", {"kind": "quantity", "value": 12, "unit": "language"},
     "Hooly Gemini speaks 12 languages.", True),
    ("Hooly Gemini", "languages", {"kind": "quantity", "value": 12, "unit": "language"},
     "Hooly Gemini speaks 12 languages and offers 9 integrations.", True),
    ("Hooly Gemini", "languages", {"kind": "quantity", "value": 12, "unit": "language"},
     "Hooly Gemini speaks 12 languages, 6 more languages than last spring.", False),
    ("Hooly Gemini", "languages", {"kind": "quantity", "value": 12, "unit": "language"},
     "Hooly Gemini speaks 12 languages since the launch.", False),
    ("Hooly Gemini", "languages", {"kind": "quantity", "value": 12, "unit": "language"},
     "Hooly Gemini speaks 12​ languages.", False),
    ("Hooly Drive", "max_file_size", {"kind": "quantity", "value": 50, "unit": "GB"},
     "Hooly Drive takes files of up to 50 GB.", False),
    ("Hooly Drive", "max_file_size", {"kind": "quantity", "value": 50, "unit": "GB"},
     "Hooly Drive takes files of 50 GB.", True),
    ("Hooly Drive", "max_file_size", {"kind": "quantity", "value": 50, "unit": "GB"},
     "Hooly Drive takes files of 50,000 MB.", True),
    ("Hooly Drive", "max_file_size", {"kind": "quantity", "value": 50, "unit": "GB"},
     "Hooly Drive takes files of 50 GB, and 10 GB is free.", False),
    ("Hooly Cloud", "uptime_sla", {"kind": "percent", "value": 99.9}, "Hooly Cloud promises 99.9% uptime.", True),
    ("Hooly Cloud", "uptime_sla", {"kind": "percent", "value": 99.9}, "Hooly Cloud promises 99,9% uptime.", False),
    ("Hooly AI Pro", "free_trial", {"kind": "duration", "value": 14, "unit": "day"},
     "Hooly AI Pro starts with a 14-day trial.", True),
    ("Hooly AI Pro", "free_trial", {"kind": "duration", "value": 2, "unit": "week"},
     "Hooly AI Pro starts with a 14-day trial.", True),
    ("Hooly AI Pro", "free_trial", {"kind": "duration", "value": 1, "unit": "month"},
     "Hooly AI Pro starts with a 30-day trial.", False),
    ("Hooly", "founded", {"kind": "date", "value": "2025-01-14"}, "Hooly was founded on 14 January 2025.", True),
    ("Hooly", "founded", {"kind": "date", "value": "2025-01"}, "Hooly was founded on 14 January 2025.", False),
    ("Hooly", "founded", {"kind": "date", "value": "2025-01-14"}, "Hooly was founded on 14/01/2025.", False),
    ("Hooly", "employees", {"kind": "quantity", "value": 2026, "unit": "employee"},
     "Hooly has 2026 employees.", False),
    ("Hooly", "employees", {"kind": "quantity", "value": 2026, "unit": "employee"},
     "Hooly has 2,026 employees.", True),
    ("Hooly", "employees", {"kind": "quantity", "value": 120, "unit": "employee"},
     "Hooly has 120 employees in Q4 2026.", False),
]


@pytest.mark.parametrize("subject,attribute,value,text,accepted", MORE_FACTS)
def test_more_facts(lexicon, attrs, subject, attribute, value, text, accepted):
    form = {"subject": subject, "attribute": attribute, "value": value}
    check(lexicon, attrs, entry("fact", text, form), accepted)
