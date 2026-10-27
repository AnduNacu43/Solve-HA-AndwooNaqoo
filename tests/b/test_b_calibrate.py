import itertools



from arena.calibrate import confidence, describe
from arena.model import Claim
from build.calibration import pseudo_claims


def claim(label="true", type_="fact", **ev):
    base = {"support": 3.0, "conflict": 0.0, "n_obs": 3, "volatility": 2, "kind": "quantity",
            "anchored": True, "perturbed": False, "type": type_}
    base.update(ev)
    return Claim(type=type_, form={}, label=label, evidence=base)


def test_every_pseudo_claim_lands_in_range(practice_obs, priors, calibration):
    records = pseudo_claims(practice_obs, priors)
    assert len(records) > 1500
    for r in records:
        c = claim(label=r["label"], kind=r["kind"], volatility=r["vol"], anchored=r["anchored"],
                  support=r["support"], n_obs=1)
        assert 0.5 <= confidence(c, calibration) <= 1.0


def test_monotone_in_support(calibration):
    kinds = ["quantity", "money", "percent", "date", "version", "duration", "name", "boolean"]
    supports = [0, 0.3, 0.7, 1, 1.5, 2, 3, 4, 6, 8, 12, 20, 50]
    for label, anchored, kind, vol, conflict in itertools.product(
            ("true", "false"), (False, True), kinds, (1, 2, 3, 5), (0.0, 1.0)):
        seq = [confidence(claim(label, kind=kind, anchored=anchored, volatility=vol, support=s,
                                conflict=conflict, n_obs=4), calibration) for s in supports]
        assert seq == sorted(seq), (label, anchored, kind, vol, conflict, seq)


def test_anchored_beats_unanchored(calibration):
    assert confidence(claim(anchored=True), calibration) > confidence(claim(anchored=False), calibration)


def test_rules(calibration):
    assert confidence(claim("false", perturbed=True), calibration) == 0.95
    assert confidence(claim("false", perturbed=True, value_seen=True), calibration) != 0.95
    # a flipped boolean is not a made-up value: it rests on our timeline
    assert confidence(claim("false", perturbed=True, kind="boolean", anchored=False), calibration) <= 0.8
    assert confidence(claim(volatility=1, anchored=True, n_obs=3, support=2.0), calibration) >= 0.9
    assert confidence(claim(volatility=1, anchored=True, n_obs=3, type_="compare"), calibration) >= 0.9
    assert confidence(claim(volatility=5, support=30), calibration) <= 0.7
    assert confidence(claim(kind="boolean", anchored=False, volatility=1), calibration) <= 0.8
    assert confidence(claim(conflict=2.0, support=3.0), calibration) <= 0.65
    assert confidence(claim(spec_inferred=True, volatility=1, n_obs=5), calibration) <= 0.6


def test_one_point_zero_only_when_certain(calibration):
    rules = dict(calibration["rules"], below_certain_cap=0.99, stable_anchored_floor=1.0)
    cal = dict(calibration, rules=rules)
    assert confidence(claim(volatility=1, support=12, conflict=0, n_obs=12), cal) == 1.0
    assert confidence(claim(volatility=1, support=9, conflict=0, n_obs=12), cal) == 0.99
    assert confidence(claim(volatility=1, support=12, conflict=0.5, n_obs=12), cal) == 0.99
    assert confidence(claim(volatility=1, support=12, anchored=False, n_obs=12), cal) <= 0.99


def test_multi_interval_claims_combine(calibration):
    one = confidence(claim(), calibration)
    side = {"support": 3.0, "conflict": 0.0, "n_obs": 3, "volatility": 2, "anchored": True}
    two = confidence(Claim(type="change", form={}, label="true",
                           evidence={"kind": "quantity", "sides": [side, side], "type": "change"}), calibration)
    assert 0.5 <= two <= one
    weak = dict(side, anchored=False, support=0.5)
    strong_cmp = confidence(Claim(type="compare", form={}, label="true",
                                  evidence={"kind": "quantity", "sides": [side, side]}), calibration)
    weak_cmp = confidence(Claim(type="compare", form={}, label="true",
                                evidence={"kind": "quantity", "sides": [side, weak]}), calibration)
    assert 0.5 <= weak_cmp < strong_cmp


def test_flat_merged_evidence_as_agent_c_sends_it(calibration):
    """C merges two-interval evidence flat (weaker side) and never sends `sides`.
    compare/change/relation are scored on interval correctness, whatever the label."""
    ev = dict(support=2.0, conflict=0.0, n_obs=3, volatility=2, kind="quantity", anchored=True,
              perturbed=False, stale=False, rel_diff=0.4, swapped=True)
    for ctype in ("compare", "change", "relation"):
        t = confidence(Claim(type=ctype, form={}, label="true", evidence=dict(ev, type=ctype)), calibration)
        f = confidence(Claim(type=ctype, form={}, label="false", evidence=dict(ev, type=ctype)), calibration)
        assert t == f and 0.5 <= t <= 1.0, ctype
    cmp_ = confidence(Claim(type="compare", form={}, label="true", evidence=dict(ev, type="compare")), calibration)
    chg = confidence(Claim(type="change", form={}, label="true", evidence=dict(ev, type="change")), calibration)
    assert cmp_ > chg                      # a wrong side still leaves a compare's op half right
    true_fact = confidence(Claim(type="fact", form={}, label="true", evidence=dict(ev, type="fact")), calibration)
    stale = confidence(Claim(type="fact", form={}, label="false",
                             evidence=dict(ev, type="fact", stale=True, stale_support=3.0)), calibration)
    assert stale == true_fact          # both rest on the current interval being right


def test_empty_evidence_is_safe(calibration):
    assert 0.5 <= confidence(Claim(type="fact", form={}, label="true", evidence={}), calibration) <= 1.0


def test_describe_prints_the_table(calibration):
    text = describe(calibration)
    assert "label" in text and "rules:" in text
    assert "true   1        money" in text
