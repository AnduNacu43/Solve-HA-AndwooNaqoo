"""Sentences, clauses, negations, refused words, lexicon names and pages."""
import pytest

from arena.grammar import claims as C
from arena.grammar import sentences as S
from arena.pages import load_universe, split_sentences


def test_split_sentences_rules():
    assert split_sentences("Hooly AI Pro is our plan. It costs €59 per month.") == [
        "Hooly AI Pro is our plan.", "It costs €59 per month."]
    assert len(split_sentences("Hooly Inc. raised €18 million, e.g. from Raviqa vs. others.")) == 1
    assert len(split_sentences("Ask Dr. Bachmann or J. Smith about No. 1 today.")) == 1
    assert split_sentences("Wow! Really? Yes.") == ["Wow!", "Really?", "Yes."]
    assert split_sentences("one line\nstill one") == ["one line\nstill one"]
    assert split_sentences("first\n\nsecond") == ["first", "second"]
    assert len(split_sentences("The price is 2.5 GB. Next")) == 2
    assert len(split_sentences("Version ver. 2.3 ships", lenient=True)) == 1
    assert len(split_sentences("Version ver. 2.3 ships")) == 2
    assert len(split_sentences('He said "it is done." Then left.', lenient=True)) == 2


def test_clauses_and_negation():
    s = "We do not offer 99.9% uptime, but 10,000 users stay."
    assert S.negated_before(s, s.index("99.9"))
    assert not S.negated_before(s, s.index("10,000"))
    assert not S.negated_before("speaks 30 languages and never misses", 7)
    assert not S.negated_before("no more than 2 GB", 13)
    assert S.find_negations("It isn't and it doesn\u2019t, cannot, nor none.")
    assert len(S.find_negations("It isn't and it doesn\u2019t")) == 2
    assert not S.find_negations("Hooly is No. 1 in Europe")


def test_refused_words():
    assert {w for w, _, _ in S.find_time_words("It used to be, last year, at that time")} == {
        "used to", "last year", "at that time"}
    assert [w for w, _, _ in S.find_yearless_date_words("In May we may grow by spring")] == ["may", "spring"]
    assert C.has_own_date("Hooly grew in Q4 2026.", [])
    assert not C.has_own_date("Hooly I/O 2026 drew 4,000 people.", [(0, 14)])


def test_attribute_words():
    assert C.attribute_words("soc2_certified") == "SOC 2 certified"
    assert C.attribute_words("had_major_outage") == "had major outage"
    assert C.attribute_words("series_a_lead") == "series A lead"
    assert C.attribute_word_spans("Hooly has never been SOC2-certified.", "soc2_certified")
    assert C.attribute_word_spans("end-to-end encrypted backups", "end_to_end_encrypted_backups")
    assert not C.attribute_word_spans("SOC 2 audit", "soc2_certified")


def test_op_phrases():
    assert C.find_op_phrase("Hooly Workspace costs more paying customers than Hooly AI Pro") == [
        ("gt", 22, 48)]
    assert len(C.find_op_phrase("more than A, and less than B")) == 2
    assert C.op_phrases("on the same day as the outage")[0][:2] == ("date", "eq")
    assert not C.find_op_phrase("more of them, honestly, really, truly, than")


def test_event_phrase(lexicon):
    ev = C.find_event_phrase("At Hooly I/O, Hooly Gemini spoke a dozen languages.", lexicon)
    assert ev and ev[0] == "Hooly I/O 2026"
    assert C.find_event_phrase("Gemini spoke 12 languages before Hooly I/O 2026.", lexicon) is None
    assert C.find_event_phrase("It went down during the outage.", lexicon)[0] == "The May 2026 outage"


def test_mentions_longest_wins(lexicon):
    ms = lexicon.find_mentions("Hooly AI Pro costs more than Hooly AI and HOOLY  ai pro.")
    assert [m.subject for m in ms] == ["Hooly AI Pro", "Hooly", "Hooly AI Pro"]
    assert [m.subject for m in lexicon.find_mentions("Hooly's board met Hooly's CTO.")] == ["Hooly Board", "Hooly"]
    assert [m.subject for m in lexicon.find_mentions("Hooly Pixel 10 Pro and Pixel 10")] == [
        "Hooly Pixel 10 Pro", "Hooly Pixel 10"]
    assert [m.subject for m in lexicon.find_mentions("HoolyAIPro")] == ["Hooly AI Pro"]
    assert not lexicon.find_mentions("Pixel 90 and Researchers")


def test_mentions_common_words(lexicon):
    assert [m.subject for m in lexicon.find_mentions("Search results load fast")] == ["Hooly Search"]
    assert [m.subject for m in lexicon.find_mentions("we search the maps")] == ["Hooly Search", "Hooly Maps"]
    assert lexicon.find_mentions("we search the maps", any_case=False) == []
    assert [m.subject for m in lexicon.find_mentions("after the outage", any_case=False)] == ["The May 2026 outage"]


def test_lexicon_lookup(lexicon):
    assert lexicon.resolve("hooly  ai   PRO") == "Hooly AI Pro"
    assert lexicon.resolve("Hooly\u2019s board") == "Hooly Board"
    assert lexicon.has_attribute("Workspace plan", "price")
    assert not lexicon.has_attribute("Hooly", "price")
    assert lexicon.event_date_attr("Hooly I/O") == "date"
    assert lexicon.event_date_attr("Hooly Q1 2026 Results") is None
    assert lexicon.event_date_attr("Hooly Gemini") is None


def test_load_universe_pages(tmp_path):
    pages = load_universe("data/practice.csv")
    assert 280 <= len(pages) <= 300
    assert max(len(p.rows) for p in pages) <= 15
    assert sum(len(p.rows) for p in pages) == 1897
    p = tmp_path / "u.csv"
    p.write_text("id;text;date\nu-10;B;12.03.2026\nu-2;A;12.03.2026\nu-11;C;2026-03-13\n", encoding="utf-8")
    pages = load_universe(str(p))
    assert [(pg.date, [r.id for r in pg.rows]) for pg in pages] == [
        ("2026-03-12", ["u-2", "u-10"]), ("2026-03-13", ["u-11"])]
