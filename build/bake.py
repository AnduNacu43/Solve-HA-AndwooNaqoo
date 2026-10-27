"""Bake everything learnable from practice into data/baked/.

    python build/bake.py            # regenerate data/baked/*.json
    python build/bake.py --report   # also print per-pair timelines and replay numbers

Writes, deterministically:
  attrs.json           kind/unit/currency/period per pair and per bare attribute
  timelines_seed.json  every practice fact as a labelled Observation
  priors.json          cue multipliers P(true | cue) / P(true), clipped
  calibration.json     empirical accuracy table for arena.calibrate
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from arena.attrs import infer_spec, spec_to_json  # noqa: E402
from arena.model import Observation  # noqa: E402
from arena.reliability import derived_cues  # noqa: E402
from arena.timeline import observation_to_json, row_key, volatility  # noqa: E402
from build import calibration as calib  # noqa: E402
from build.practice import practice_observations  # noqa: E402
from build.replay import replay, run_pipeline  # noqa: E402

BAKED = os.path.join(ROOT, "data", "baked")
PRIOR_SMOOTHING = 10.0   # pseudo-rows pulling a cue's rate toward the base rate
CLIP = (0.3, 1.0)
LABEL_TRUTH = {"true": 1.0, "false": 0.0, "unsure": 0.5}


def bake_attrs(obs: list[Observation]) -> dict:
    by_pair = defaultdict(list)
    by_attr = defaultdict(list)
    for o in obs:
        by_pair[o.key()].append(o.value)
        by_attr[o.attribute].append(o.value)
    return {
        "pairs": {f"{s}|{a}": spec_to_json(infer_spec(v)) for (s, a), v in sorted(by_pair.items())},
        "by_attribute": {a: spec_to_json(infer_spec(v)) for a, v in sorted(by_attr.items())},
    }


def bake_priors(obs: list[Observation]) -> dict:
    """Multiplier per cue = smoothed P(true | cue) / P(true), clipped.

    Rows are the unit (labels are per row); unsure counts as half true. Cues
    are the row's own plus reliability.derived_cues (context_subject, month,
    date), so the same names apply at run time.
    """
    truth, cues = {}, defaultdict(set)
    for o in obs:
        truth[row_key(o)] = LABEL_TRUTH[o.label]
        cues[row_key(o)] |= derived_cues(o)
    base = sum(truth.values()) / len(truth)
    n, t = Counter(), Counter()
    for r, cs in cues.items():
        for c in cs:
            n[c] += 1
            t[c] += truth[r]
    mult, counts = {}, {}
    for c in sorted(n):
        p = (t[c] + PRIOR_SMOOTHING * base) / (n[c] + PRIOR_SMOOTHING)
        m = round(min(CLIP[1], max(CLIP[0], p / base)), 4)
        counts[c] = [round(t[c], 1), n[c]]
        if m < 1.0:
            mult[c] = m
    return {"base_rate": round(base, 4), "clip": list(CLIP), "smoothing": PRIOR_SMOOTHING,
            "multipliers": mult, "counts": counts}


def dump(name: str, data, out: str = BAKED) -> None:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def report(obs, priors, calibration) -> None:
    timelines = run_pipeline(obs, priors)
    print("# Timelines (labels visible)\n")
    for (s, a), ivs in sorted(timelines.items()):
        if len(ivs) < 2:
            continue
        print(f"{s}.{a}")
        for iv in ivs:
            v = iv.value
            unit = v.unit or (f"{v.currency}/{v.per}" if v.per else v.currency) or ""
            print(f"  {iv.start} -> {iv.end or 'now':10}  {v.value} {unit}".rstrip()
                  + f"   support {iv.support:.2f} conflict {iv.conflict:.2f} n={iv.n_obs}"
                  + (" anchored" if iv.anchored else ""))
    print("\n# 50 most volatile pairs\n")
    ranked = sorted(timelines.items(), key=lambda kv: (-volatility(kv[1]), kv[0]))[:50]
    for (s, a), ivs in ranked:
        print(f"  {volatility(ivs)}  {s}.{a}")
    print("\n# Replay")
    for mode in ("hidden", "cv", "visible"):
        print(f"  {mode:8} {json.dumps(replay(obs, priors, mode)[0])}")
    print("\n# Calibration table (fact pseudo-claims, cross-validated)\n")
    print(calib.describe(calibration))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="print timelines, replay and calibration")
    ap.add_argument("--out", default=BAKED, help="output directory (default data/baked)")
    args = ap.parse_args(argv)

    obs = practice_observations(os.path.join(ROOT, "data", "practice.csv"),
                                os.path.join(ROOT, "data", "lexicon.json"))
    priors = bake_priors(obs)
    calibration = calib.fit(obs, priors)
    dump("attrs.json", bake_attrs(obs), args.out)
    dump("timelines_seed.json", [observation_to_json(o) for o in obs], args.out)
    dump("priors.json", priors, args.out)
    dump("calibration.json", calibration, args.out)
    print(f"baked {len(obs)} observations into {args.out}", file=sys.stderr)
    if args.report:
        report(obs, priors, calibration)
    return 0


if __name__ == "__main__":
    sys.exit(main())
