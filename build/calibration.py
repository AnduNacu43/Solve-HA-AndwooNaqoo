"""Fit data/baked/calibration.json from cross-validated fact pseudo-claims.

Each practice fact is a pseudo-claim "this value held on the row date". For
each fold, timelines are rebuilt with that fold's labels hidden and the other
folds' labels as anchors; the pseudo-claim's predicted label is whether the
value holds at the date, and it is right when that matches the row label
(true row: every fact true; false single-fact row: the fact false; facts of
false multi-fact rows and of unsure rows are skipped, their truth unknown).
"""
from __future__ import annotations

from collections import defaultdict

from arena.calibrate import DEFAULT_RULES, bucket_path, describe, support_bucket  # noqa: F401
from arena.model import Observation
from arena.timeline import consistent, value_at, volatility
from build.replay import FOLDS, by_row, fold_of_page, gold_priors, hide, run_pipeline

SUPPORT_EDGES = [1.0, 2.0, 4.0, 8.0]
M_ESTIMATE = 10.0


def pseudo_claims(obs: list[Observation], priors: dict) -> list[dict]:
    """One record per judgeable fact: label, anchored, kind, vol, support, right."""
    priors = gold_priors(priors)
    fold = fold_of_page(obs)
    n_facts = {r: len(fs) for r, fs in by_row(obs).items()}
    out = []
    for k in range(FOLDS):
        rows = {o.row_id for o in obs if fold[o.page_id] == k}
        tl = run_pipeline(hide(obs, rows), priors)
        for o in obs:
            if o.row_id not in rows:
                continue
            if o.label == "true":
                truth = "true"
            elif o.label == "false" and n_facts[o.row_id] == 1:
                truth = "false"
            else:
                continue
            ivs = tl.get(o.key(), [])
            iv = value_at(ivs, o.date)
            if iv is None:
                continue
            predicted = "true" if consistent(o.value, iv.value) else "false"
            out.append({"label": predicted, "anchored": iv.anchored, "kind": o.value.kind,
                        "vol": volatility(ivs), "support": iv.support,
                        "right": predicted == truth})
    return out


def fit(obs: list[Observation], priors: dict) -> dict:
    table = defaultdict(lambda: [0, 0])
    hits = n = 0
    for c in pseudo_claims(obs, priors):
        sup = support_bucket(c["support"], SUPPORT_EDGES)
        for key in bucket_path(c["label"], c["anchored"], c["kind"], c["vol"], sup):
            table[key][0] += int(c["right"])
            table[key][1] += 1
        hits += int(c["right"])
        n += 1
    return {"version": 1, "support_edges": SUPPORT_EDGES, "m": M_ESTIMATE,
            "global": [hits, n], "table": {k: v for k, v in sorted(table.items())},
            "rules": dict(DEFAULT_RULES)}
