"""Replay timelines against the practice labels (build time and tests).

run_pipeline() is the run-time order of B's calls: weights, timelines,
weights again with agreement, timelines again. judge_rows() predicts a row
true iff every fact holds on the row date; metrics() scores that against the
labels.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Optional

from arena.model import Observation, Timelines
from arena.reliability import page_weights
from arena.timeline import build, consistent, value_at

FOLDS = 5


def run_pipeline(obs: list[Observation], priors: dict, passes: int = 2,
                 aliases: Optional[dict[str, str]] = None) -> Timelines:
    weights = page_weights(obs, priors)
    timelines = build(obs, weights, aliases)
    for _ in range(passes - 1):
        weights = page_weights(obs, priors, timelines)
        timelines = build(obs, weights, aliases)
    return timelines


def hide(obs: list[Observation], rows: Optional[set[str]] = None) -> list[Observation]:
    """Copies with the label removed (for every row, or only for `rows`)."""
    return [replace(o, label=None) if rows is None or o.row_id in rows else o for o in obs]


def by_row(obs: list[Observation]) -> dict[str, list[Observation]]:
    out: dict[str, list[Observation]] = defaultdict(list)
    for o in obs:
        out[o.row_id].append(o)
    return out


def judge_rows(obs: list[Observation], timelines: Timelines) -> dict[str, str]:
    """Row id -> "true" when every fact with an interval holds on the row date."""
    out = {}
    for row, facts in by_row(obs).items():
        ok = True
        for o in facts:
            iv = value_at(timelines.get(o.key(), []), o.date)
            if iv is not None and not consistent(o.value, iv.value):
                ok = False
        out[row] = "true" if ok else "false"
    return out


def metrics(obs: list[Observation], predicted: dict[str, str]) -> dict:
    """Accuracy on true/false rows, recall and precision of `false`, and the
    share of unsure rows predicted false."""
    label = {o.row_id: o.label for o in obs}
    tf = [r for r in predicted if label.get(r) in ("true", "false")]
    false_rows = [r for r in tf if label[r] == "false"]
    pred_false = [r for r in tf if predicted[r] == "false"]
    unsure = [r for r in predicted if label.get(r) == "unsure"]
    hit = sum(predicted[r] == label[r] for r in tf)
    return {
        "rows": len(tf),
        "accuracy": round(hit / max(1, len(tf)), 4),
        "false_rows": len(false_rows),
        "false_recall": round(sum(predicted[r] == "false" for r in false_rows) / max(1, len(false_rows)), 4),
        "false_precision": round(sum(label[r] == "false" for r in pred_false) / max(1, len(pred_false)), 4),
        "true_accuracy": round(sum(predicted[r] == "true" for r in tf if label[r] == "true")
                               / max(1, len(tf) - len(false_rows)), 4),
        "unsure_rows": len(unsure),
        "unsure_predicted_false": sum(predicted[r] == "false" for r in unsure),
    }


def fold_of_page(obs: list[Observation]) -> dict[str, int]:
    """Deterministic page -> fold split, so a page's rows share a fold."""
    pages = sorted({o.page_id for o in obs})
    return {p: i % FOLDS for i, p in enumerate(pages)}


def replay(obs: list[Observation], priors: dict, mode: str = "hidden") -> tuple[dict, dict[str, str]]:
    """Metrics and predictions of one replay.

    hidden:  all labels removed (no anchors);
    visible: all labels kept (every row anchors itself; an upper bound);
    cv:      each fold judged with only the other folds' labels as anchors.
    """
    if mode == "hidden":
        predicted = judge_rows(obs, run_pipeline(hide(obs), priors))
    elif mode == "visible":
        predicted = judge_rows(obs, run_pipeline(obs, priors))
    elif mode == "cv":
        fold = fold_of_page(obs)
        predicted = {}
        for k in range(FOLDS):
            rows = {o.row_id for o in obs if fold[o.page_id] == k}
            tl = run_pipeline(hide(obs, rows), priors)
            predicted.update(judge_rows([o for o in obs if o.row_id in rows], tl))
    else:
        raise ValueError(mode)
    return metrics(obs, predicted), predicted
