import pytest

from arena.model import Value
from arena.reliability import cue_weight, derived_cues, page_agreement, page_weights
from arena.timeline import build, row_key


def qty(x):
    return Value("quantity", x, unit="language")


def test_priors_learned_the_known_bad_signals(priors):
    m = priors["multipliers"]
    assert 0 < priors["base_rate"] < 1
    assert m["date:2026-10-26"] < 0.8          # the stale nest
    for cue in ("gavin", "boast", "hearsay", "testimonial"):
        assert m[cue] < 1.0, cue
    assert all(priors["clip"][0] <= v <= priors["clip"][1] for v in m.values())


def test_weights_cover_rows_and_pages_in_range(practice_obs, priors, timelines):
    for tl in (None, timelines):
        w = page_weights(practice_obs, priors, tl)
        for o in practice_obs:
            assert 0 < w[row_key(o)] <= 1.0
            assert 0 < w[o.page_id] <= 1.0


def test_cue_weight_multiplies_and_clips():
    priors = {"multipliers": {"a": 0.5, "b": 0.4}, "clip": [0.3, 1.0]}
    assert cue_weight({"a"}, priors) == 0.5
    assert cue_weight({"a", "b"}, priors) == 0.3          # 0.2 clipped up
    assert cue_weight({"unknown"}, priors) == 1.0


def test_derived_cues(make_obs):
    o = make_obs(qty(6), "2026-10-26", named=False, cues={"speaker"})
    assert derived_cues(o) == {"speaker", "context_subject", "month:2026-10", "date:2026-10-26"}


def test_pass_two_lowers_a_disagreeing_page(make_obs):
    good = [make_obs(qty(12), d, page="good") for d in ("2026-04-01",)]
    good += [make_obs(qty(12), d) for d in ("2026-04-02", "2026-05-01", "2026-06-01", "2026-07-01")]
    liar = [make_obs(qty(40), "2026-05-15", page="liar")]
    obs = good + liar
    priors = {"multipliers": {}, "clip": [0.3, 1.0]}
    w1 = page_weights(obs, priors)
    assert w1["liar"] == w1["good"] == 1.0
    tl = build(obs, w1)
    w2 = page_weights(obs, priors, tl)
    assert w2["liar"] < w2["good"]


def test_extraction_precision_weighs_unlabelled_observations_only(make_obs):
    from arena.timeline import extraction_key, observation_weight

    priors = {"multipliers": {}, "clip": [0.3, 1.0], "extraction": {"name:context": 0.5}}
    unlabelled = make_obs(Value("name", "Holdan"), "2026-01-01", named=False)
    labelled = make_obs(Value("name", "Holdan"), "2026-01-01", named=False, label="true")
    named = make_obs(Value("name", "Holdan"), "2026-01-01", named=True)
    w = page_weights([unlabelled, labelled, named], priors)
    assert extraction_key(unlabelled) == "extract:name:context" and w["extract:name:context"] == 0.5
    assert observation_weight(unlabelled, w) == 0.5
    assert observation_weight(labelled, w) == 1.0
    assert observation_weight(named, w) == 1.0          # no entry for name:named -> 1.0


def test_beta_smoothing_of_one_observation_pages(make_obs):
    obs = [make_obs(qty(12), d) for d in ("2026-04-01", "2026-04-02", "2026-04-03", "2026-04-05")]
    obs.append(make_obs(qty(40), "2026-04-04", page="liar"))
    tl = build(obs, {})
    agree = page_agreement(obs, tl)
    assert agree["liar"] == pytest.approx(2 / 5)
    assert agree[obs[0].page_id] == pytest.approx(3 / 5)
