import json

from arena.model import Value
from arena.timeline import (
    build, consistent, current, load_seed, observation_from_json, observation_to_json,
    same_value, value_at, volatility,
)
from build.replay import hide, run_pipeline

from b_helpers import BAKED, ROOT, load_stub

EUR = dict(currency="EUR", per="month")


def money(x):
    return Value("money", x, **EUR)


def qty(x, unit="language"):
    return Value("quantity", x, unit=unit)


# ---------------------------------------------------------------- values


def test_unit_conversions():
    assert same_value(Value("duration", 14, unit="day"), Value("duration", 2, unit="week"))
    assert same_value(Value("duration", 12, unit="month"), Value("duration", 1, unit="year"))
    assert not same_value(Value("duration", 30, unit="day"), Value("duration", 1, unit="month"))
    assert same_value(qty(1, "TB"), qty(1000, "GB"))
    assert same_value(qty(6.1, "inch"), qty(6.1, "in"))
    assert not same_value(money(49), Value("money", 49, currency="EUR"))   # monthly vs one-off


def test_consistent_coarse_dates_names_and_ops():
    assert consistent(Value("date", "2026-06"), Value("date", "2026-06-09"))
    assert consistent(Value("date", "2026"), Value("date", "2026-06-09"))
    assert not consistent(Value("date", "2026-06-09"), Value("date", "2026-06"))
    assert consistent(Value("name", "Gavin"), Value("name", "Gavin Bellson"))
    assert not consistent(Value("name", "Gavin Bellson"), Value("name", "Gavin"))
    assert consistent(Value("quantity", 100, unit="customer", op="gt"), qty(120, "customer"))
    assert not consistent(Value("quantity", 100, unit="customer", op="gt"), qty(100, "customer"))
    assert consistent(Value("duration", 1, unit="s", op="lt"), Value("duration", 500, unit="ms"))
    assert consistent(Value("date", "2026-03", op="lt"), Value("date", "2026-02-15"))


def test_name_aliases_collide_when_given():
    lex = load_stub("lexicon_stub").Lexicon.load(str(ROOT / "data" / "lexicon.json"))
    a, b = Value("name", "Workspace plan"), Value("name", "Hooly Workspace")
    assert not same_value(a, b)
    assert same_value(a, b, lex.aliases)


# ---------------------------------------------------------------- synthetic timelines


def test_stale_nest_after_a_change_is_conflict_not_a_revert(make_obs):
    obs = [make_obs(money(49), d) for d in ("2025-11-01", "2025-12-01", "2026-01-10", "2026-02-01", "2026-03-01")]
    obs += [make_obs(money(59), d) for d in ("2026-04-01", "2026-04-03", "2026-06-01", "2026-08-01", "2026-09-01")]
    obs += [make_obs(money(49), "2026-10-26") for _ in range(3)]
    ivs = build(obs, {})[("Acme", "attr")]
    assert [iv.value.value for iv in ivs] == [49, 59]
    assert ivs[1].start == "2026-04-01" and ivs[1].end is None
    assert ivs[1].conflict == 3.0
    assert current(ivs).value.value == 59
    assert volatility(ivs) == 2


def test_stale_repeats_over_several_late_dates_do_not_revert_a_dense_pair(make_obs):
    obs = [make_obs(money(49), f"2025-{m:02d}-{d:02d}") for m in (10, 11, 12) for d in (3, 10, 17, 24)]
    obs += [make_obs(money(59), f"2026-{m:02d}-{d:02d}") for m in range(4, 11) for d in (3, 10, 17)]
    obs += [make_obs(money(49), d) for d in ("2026-10-20", "2026-10-22", "2026-10-26", "2026-10-27")]
    ivs = build(obs, {})[("Acme", "attr")]
    assert [iv.value.value for iv in ivs] == [49, 59]


def test_a_last_day_lie_does_not_become_current_in_a_dense_pair(make_obs):
    obs = [make_obs(qty(12), f"2026-{m:02d}-{d:02d}") for m in range(1, 11) for d in (5, 15, 25)]
    obs.append(make_obs(qty(40), "2026-10-28"))
    assert current(build(obs, {})[("Acme", "attr")]).value.value == 12
    sparse = [make_obs(qty(12), "2026-05-05"), make_obs(qty(40), "2026-10-28")]
    assert current(build(sparse, {})[("Acme", "attr")]).value.value == 40   # sparse: a change is believed


def test_a_one_day_nest_of_a_new_value_does_not_take_over_a_dense_pair(make_obs):
    obs = [make_obs(Value("date", "2025-01-14"), f"2026-{m:02d}-10") for m in range(1, 11)]
    obs += [make_obs(Value("date", "2024-06-01"), "2026-10-26") for _ in range(8)]
    assert current(build(obs, {})[("Acme", "attr")]).value.value == "2025-01-14"
    # the same nest pinned by a labelled row is believed
    obs.append(make_obs(Value("date", "2024-06-01"), "2026-10-26", label="true"))
    assert current(build(obs, {})[("Acme", "attr")]).value.value == "2024-06-01"


def test_one_misread_sentence_does_not_overturn_a_labelled_value(make_obs):
    obs = [make_obs(qty(1500, "user"), d, label="true") for d in ("2026-02-01", "2026-05-01")]
    obs.append(make_obs(qty(70000, "user"), "2026-09-01"))       # unlabelled, one day
    assert current(build(obs, {})[("Acme", "attr")]).value.value == 1500
    obs.append(make_obs(qty(70000, "user"), "2026-09-20"))       # seen again on another day
    assert current(build(obs, {})[("Acme", "attr")]).value.value == 70000


def test_genuine_revert_is_kept(make_obs):
    obs = [make_obs(money(49), d) for d in ("2025-11-01", "2025-12-01", "2026-01-10")]
    obs += [make_obs(money(59), d) for d in ("2026-04-01", "2026-04-20", "2026-05-01")]
    obs += [make_obs(money(49), d) for d in ("2026-07-01", "2026-07-03", "2026-07-08", "2026-08-01", "2026-09-01")]
    ivs = build(obs, {})[("Acme", "attr")]
    assert [iv.value.value for iv in ivs] == [49, 59, 49]
    assert ivs[2].start == "2026-07-01"


def test_lone_lie_and_early_announcement_are_not_intervals(make_obs):
    obs = [make_obs(qty(12), "2025-12-10")]                     # early announcement
    obs += [make_obs(qty(6), d) for d in ("2025-10-07", "2025-11-01", "2026-01-20", "2026-03-01")]
    obs += [make_obs(qty(40), "2026-02-10")]                    # inflated lie
    obs += [make_obs(qty(12), d) for d in ("2026-03-24", "2026-03-24", "2026-05-12", "2026-08-20")]
    ivs = build(obs, {})[("Acme", "attr")]
    assert [(iv.start, iv.value.value) for iv in ivs] == [("2025-10-07", 6), ("2026-03-24", 12)]
    assert value_at(ivs, "2025-12-10").value.value == 6
    assert value_at(ivs, "2026-02-10").value.value == 6


def test_anchors_pin_and_exclude(make_obs):
    obs = [make_obs(qty(6), d) for d in ("2026-01-01", "2026-01-15", "2026-02-01", "2026-03-01")]
    obs.append(make_obs(qty(12), "2026-02-01", label="true"))   # one labelled row outweighs the crowd
    ivs = build(obs, {})[("Acme", "attr")]
    assert [(iv.start, iv.value.value) for iv in ivs] == [("2026-01-01", 6), ("2026-02-01", 12)]
    assert ivs[0].anchored is False and ivs[1].anchored
    assert ivs[1].conflict == 2.0                                # 6 on the same day and after

    obs = [make_obs(qty(12), d) for d in ("2026-01-01", "2026-02-01")]
    obs.append(make_obs(qty(6), "2026-01-15"))
    obs.append(make_obs(qty(12), "2026-01-15", label="false"))  # single-fact false row
    ivs = build(obs, {})[("Acme", "attr")]
    assert value_at(ivs, "2026-01-15").value.value != 12


def test_equivalent_forms_make_one_interval(make_obs):
    obs = [make_obs(Value("duration", 14, unit="day"), "2026-01-01"),
           make_obs(Value("duration", 2, unit="week"), "2026-02-01"),
           make_obs(Value("duration", 14, unit="day"), "2026-03-01")]
    ivs = build(obs, {})[("Acme", "attr")]
    assert len(ivs) == 1 and ivs[0].value == Value("duration", 14, unit="day") and ivs[0].n_obs == 3

    names = [make_obs(Value("name", "Gavin"), "2026-01-01"), make_obs(Value("name", "Gavin Bellson"), "2026-02-01"),
             make_obs(Value("name", "Gavin"), "2026-03-01")]
    ivs = build(names, {})[("Acme", "attr")]
    assert len(ivs) == 1 and ivs[0].value.value == "Gavin Bellson"

    dates = [make_obs(Value("date", "2026-06"), "2026-01-21"), make_obs(Value("date", "2026-06-09"), "2026-03-18"),
             make_obs(Value("date", "2026-06-09"), "2026-04-02")]
    ivs = build(dates, {})[("Acme", "attr")]
    assert len(ivs) == 1 and ivs[0].value.value == "2026-06-09" and ivs[0].n_obs == 3

    inches = [make_obs(qty(6.1, "inch"), "2026-01-01")]
    assert build(inches, {})[("Acme", "attr")][0].value.unit == "in"


def test_op_observations_support_at_half_weight(make_obs):
    only_op = [make_obs(Value("quantity", 100, unit="customer", op="gt"), "2026-01-01")]
    assert build(only_op, {}) == {}
    obs = only_op + [make_obs(qty(120, "customer"), "2026-01-05")]
    iv = build(obs, {})[("Acme", "attr")][0]
    assert iv.value.value == 120 and iv.support == 1.5 and iv.conflict == 0


def test_value_at_partial_dates_and_bounds(make_obs):
    obs = [make_obs(qty(1), "2026-01-10"), make_obs(qty(1), "2026-02-01"),
           make_obs(qty(2), "2026-06-15"), make_obs(qty(2), "2026-07-01")]
    ivs = build(obs, {})[("Acme", "attr")]
    assert value_at(ivs, "2025-12-31") is None
    assert value_at(ivs, "2026-03").value.value == 1     # whole month inside one interval
    assert value_at(ivs, "2026-06") is None              # the change falls inside June
    assert value_at(ivs, "2026") is None
    assert value_at(ivs, "2027-01-01").value.value == 2


def test_timelines_cross_a_process_pipe(timelines):
    """C builds timelines in a forked process and sends them back pickled."""
    import pickle

    assert pickle.loads(pickle.dumps(timelines)) == timelines


def test_loaders_work_from_any_directory(tmp_path, monkeypatch):
    from arena.attrs import load_attrs
    from arena.calibrate import load_calibration
    from arena.reliability import load_priors

    monkeypatch.chdir(tmp_path)
    assert len(load_seed()) == 2402
    assert load_attrs() and load_priors()["multipliers"] and load_calibration()["table"]


def test_scales_to_many_noisy_observations(practice_obs, priors):
    """20x practice, a fifth of the numbers replaced by noise: well inside
    the run's budget, and the known timelines hold."""
    import random
    import time
    from dataclasses import replace

    from arena.reliability import page_weights

    rng = random.Random(7)
    extra = []
    for n in range(20):
        for o in hide(practice_obs):
            v = o.value
            if v.kind in ("quantity", "money", "percent") and rng.random() < 0.2:
                v = replace(v, value=rng.randint(1, 100000))
            extra.append(replace(o, value=v, page_id=f"u{n}-{o.page_id}", row_id=f"u{n}-{o.row_id}"))
    obs = practice_obs + extra
    t = time.time()
    w = page_weights(obs, priors)
    tl = build(obs, page_weights(obs, priors, build(obs, w)))
    assert time.time() - t < 30
    assert _seq(tl, "Hooly AI Pro", "price") == [("2025-10-07", 49), ("2026-04-01", 59)]
    assert [v for _, v in _seq(tl, "Hooly Gemini", "languages")] == [6, 12]


def test_build_is_deterministic(practice_obs, priors):
    a = run_pipeline(practice_obs, priors)
    b = run_pipeline(list(reversed(practice_obs)), priors)
    assert a == b


# ---------------------------------------------------------------- practice timelines


def _seq(timelines, subject, attribute):
    return [(iv.start, iv.value.value) for iv in timelines[(subject, attribute)]]


def test_known_practice_timelines(timelines):
    assert _seq(timelines, "Hooly AI Pro", "price") == [("2025-10-07", 49), ("2026-04-01", 59)]
    assert _seq(timelines, "Hooly Gemini", "languages") == [("2025-10-07", 6), ("2026-03-24", 12)]
    assert _seq(timelines, "Hooly", "headquarters") == [("2025-11-04", "Berlin"), ("2026-05-01", "Lisbon")]
    assert _seq(timelines, "Hooly", "cto") == [("2025-12-10", "Richard Hendrix"), ("2026-07-01", "Bertram Gilfoil")]
    assert current(timelines[("Hooly", "series_a_amount")]).value == Value("money", 18000000, currency="EUR")
    assert current(timelines[("Hooly", "series_a_lead")]).value.value == "Raviqa Capital"
    assert current(timelines[("Hooly", "ceo")]).value.value == "Gavin Bellson"
    assert [v for _, v in _seq(timelines, "Hooly Cloud Next 2026", "date")] == ["2026-06-02", "2026-06-09"]
    assert value_at(timelines[("Hooly AI Pro", "price")], "2026-10-26").value.value == 59


def test_known_timelines_survive_hidden_labels(practice_obs, priors):
    tl = run_pipeline(hide(practice_obs), priors)
    assert _seq(tl, "Hooly AI Pro", "price") == [("2025-10-07", 49), ("2026-04-01", 59)]
    assert _seq(tl, "Hooly Gemini", "languages") == [("2025-10-07", 6), ("2026-03-24", 12)]
    assert _seq(tl, "Hooly", "headquarters") == [("2025-11-04", "Berlin"), ("2026-05-01", "Lisbon")]
    assert [v for _, v in _seq(tl, "Hooly", "cto")] == ["Richard Hendrix", "Bertram Gilfoil"]
    assert current(tl[("Hooly", "series_a_amount")]).value.value == 18000000


def test_every_interval_is_well_formed(timelines):
    for key, ivs in timelines.items():
        assert ivs, key
        for a, b in zip(ivs, ivs[1:]):
            assert a.end == b.start and a.start < b.start
        assert ivs[-1].end is None
        for iv in ivs:
            assert iv.support > 0 and iv.conflict >= 0 and iv.n_obs >= 1
            assert iv.value.op is None


# ---------------------------------------------------------------- seed


def test_seed_round_trips(practice_obs):
    from dataclasses import replace

    seed = load_seed(str(BAKED / "timelines_seed.json"))
    assert len(seed) == 2402
    # cues come from A's extractor once it is merged (build/extraction.py)
    assert [replace(o, cues=frozenset()) for o in seed] == [replace(o, cues=frozenset()) for o in practice_obs]
    ops = [o for o in seed if o.value.op]
    assert len(ops) == 38
    assert all(observation_from_json(json.loads(json.dumps(observation_to_json(o)))) == o for o in seed)


def test_seed_pages_and_cues(practice_obs):
    pages = {o.page_id for o in practice_obs}
    assert all(p.startswith("seed-pg-") for p in pages)
    assert 250 <= len(pages) <= 320          # content map: about 291 runs
    p1080 = [o for o in practice_obs if o.row_id == "p-1080"]
    assert p1080 and not p1080[0].subject_in_sentence    # "It speaks 6 languages today ..."
    gavin = [o for o in practice_obs if o.sentence.startswith("Gavin: ")]
    tagged = [o for o in gavin if {"speaker", "gavin"} <= o.cues]
    assert len(tagged) >= 0.9 * len(gavin)       # very short lines ("Thank you, Berlin!") are missed
    assert not any("speaker" in o.cues for o in practice_obs if o.sentence.startswith("Ads: "))
