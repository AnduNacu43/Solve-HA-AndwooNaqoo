"""extract() on the practice set and on small pages."""
from arena.extract import extract, replay_scores
from arena.model import Page, Row


def _page(*texts, date="2026-04-01"):
    return Page("pg-0001", date, [Row(f"r-{i}", t) for i, t in enumerate(texts, start=1)])


def _facts(obs):
    return {(o.subject, o.attribute, o.value.value, o.value.unit, o.value.per, o.value.op) for o in obs}


def test_practice_replay_precision(lexicon, attrs):
    s = replay_scores("data/practice.csv", lexicon, attrs)
    assert s["precision"] >= 0.85, s
    assert s["recall"] >= 0.6, s


def test_subject_in_sentence(lexicon, attrs):
    obs = extract([_page("Hooly AI Pro costs €59 per month, or €590 a year.")], lexicon, attrs)
    f = _facts(obs)
    assert ("Hooly AI Pro", "price", 59.0, None, "month", None) in f
    assert ("Hooly AI Pro", "annual_price", 590.0, None, "year", None) in f
    assert all(o.subject_in_sentence for o in obs)


def test_subject_from_previous_sentence(lexicon, attrs):
    obs = extract([_page("Holdan started at Hooly on 12 January 2026.",
                         "He begins with a small crew of 4 engineers, and he is hiring.")], lexicon, attrs)
    f = _facts(obs)
    assert ("Holdan", "joined", "2026-01-12", None, None, None) in f
    assert ("Holdan", "team_size", 4.0, "engineer", None, None) in f


def test_version_after_its_name(lexicon, attrs):
    obs = extract([_page("Suggestions in Hooly Docs come from Hooly Gemini 2.2.")], lexicon, attrs)
    assert ("Hooly Gemini", "version", "2.2", None, None, None) in _facts(obs)


def test_values_that_read_as_nothing_are_dropped(lexicon, attrs):
    obs = extract([_page("Hooly Gemini speaks about 40 languages.", "Hooly Gemini does not speak 30 languages.",
                         "Hooly Gemini speaks 10-20 languages.")], lexicon, attrs)
    assert not [o for o in obs if o.attribute == "languages"]


def test_op_is_kept(lexicon, attrs):
    obs = extract([_page("Hooly Cloud already serves over 100 customers.")], lexicon, attrs)
    assert ("Hooly Cloud", "customers", 100.0, "customer", None, "gt") in _facts(obs)


def test_cues_and_labels(lexicon, attrs):
    page = _page("Gavin: Hooly Gemini speaks 40 languages, I have been told.")
    obs = extract([page], lexicon, attrs, labels={"r-1": "false"})
    o = [o for o in obs if o.attribute == "languages"][0]
    assert {"speaker", "gavin", "hearsay"} <= o.cues and o.label == "false" and o.date == "2026-04-01"


def _names(lexicon, attrs, text):
    obs = extract([_page(text)], lexicon, attrs)
    return {(o.subject, o.attribute, o.value.value) for o in obs if o.value.kind == "name"}


def test_names_go_to_the_nearest_attribute_words(lexicon, attrs):
    # misreads Agent C saw fan out into relation claims
    assert _names(lexicon, attrs, "Davis Bannerchek leads the Android group at Hooly.") == {
        ("Hooly Android", "lead", "Davis Bannerchek")}
    assert _names(lexicon, attrs, "The Hooly Berlin Office is Hooly's headquarters for now.") == set()
    assert _names(lexicon, attrs, "Hooly employs 74 employees people, and its Jules lead is Nelson Bighettie.") == {
        ("Hooly Jules", "lead", "Nelson Bighettie")}
    assert _names(lexicon, attrs, "Hooly's CTO is Richard Hendrix, who calls Hooly Jules \"Gemini for code\".") == {
        ("Hooly", "cto", "Richard Hendrix")}
    assert _names(lexicon, attrs, "Hooly raised €25 million in its Series A, led by Raviqa Capital with "
                                  "Breem-Hall as co-investor.") == {
        ("Hooly", "series_a_lead", "Raviqa Capital"), ("Hooly", "series_a_co_investor", "Breem-Hall")}
    assert ("Hooly Cloud", "reliability_lead", "Holdan") in _names(
        lexicon, attrs, "From today, Hooly Cloud's reliability team answers to Holdan.")
    assert _names(lexicon, attrs, "Bertram Gilfoil is the CTO of Hooly.") == {("Hooly", "cto", "Bertram Gilfoil")}


def test_name_values_fit_the_attribute_type(lexicon, attrs):
    # a venue (capacity) is no city or host; a person (joined) is no provider
    assert _names(lexicon, attrs, "The agenda of Made by Hooly lists 18 talks, all in Rheinhalle.") == set()
    assert _names(lexicon, attrs, "Made by Hooly is hosted at Rheinhalle, in Frankfurt.") == {
        ("Made by Hooly 2026", "city", "Frankfurt")}
    assert _names(lexicon, attrs, "Before Hooly, Holdan ran incident response at Nimbus Cloud, "
                                  "the provider Gemini still runs on.") == {
        ("Hooly Gemini", "cloud_provider", "Nimbus Cloud")}
    assert ("Hooly Maps Day", "venue", "Quayside Hall") in _names(
        lexicon, attrs, "Hooly Maps Day takes place in Dublin, and the venue is Quayside Hall.")
    assert _names(lexicon, attrs, "Gavin Bellson hosts Made by Hooly 2026.") == {
        ("Made by Hooly 2026", "host", "Gavin Bellson")}
