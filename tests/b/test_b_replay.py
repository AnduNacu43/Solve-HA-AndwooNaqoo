"""The main check of plans/agent-b-timelines.md B3: rebuild practice timelines
with labels hidden and see whether value_at(date) agrees with each row label.

Run with -s to see the numbers. The floors are regression guards at the
level reached on 27 Oct 2026; build/NOTES.md explains why false-row recall
with labels hidden stays below the plan's 0.60 target at practice density.
"""
import json

from arena.reliability import page_weights
from arena.timeline import build
from build.replay import replay

from b_helpers import load_stub


def test_hidden_cv_and_visible_replays(practice_obs, priors):
    hidden = replay(practice_obs, priors, "hidden")[0]
    cv = replay(practice_obs, priors, "cv")[0]
    visible = replay(practice_obs, priors, "visible")[0]
    for name, m in (("hidden", hidden), ("cv", cv), ("visible", visible)):
        print(f"\nreplay {name:8} {json.dumps(m)}")

    assert hidden["rows"] == 1858 and hidden["false_rows"] == 277
    assert hidden["accuracy"] >= 0.90
    assert hidden["false_recall"] >= 0.45
    assert hidden["true_accuracy"] >= 0.97
    assert cv["accuracy"] >= 0.92 and cv["false_recall"] >= 0.55 and cv["false_precision"] >= 0.85
    # anchors raise both numbers
    assert visible["accuracy"] > cv["accuracy"] > hidden["accuracy"]
    assert visible["false_recall"] > cv["false_recall"] > hidden["false_recall"]


def test_seed_plus_unlabelled_observations(practice_obs, priors):
    """Run-time shape: labelled seed plus unlabelled extracted observations
    (here the stub re-reads practice without labels, on its own pages)."""
    from dataclasses import replace

    extracted = [replace(o, page_id="u" + o.page_id, row_id="u" + o.row_id)
                 for o in load_stub("extract_stub").extract()]
    obs = practice_obs + extracted
    w = page_weights(obs, priors)
    tl = build(obs, page_weights(obs, priors, build(obs, w)))
    price = tl[("Hooly AI Pro", "price")]
    assert [(iv.start, iv.value.value) for iv in price] == [("2025-10-07", 49), ("2026-04-01", 59)]
    assert price[-1].anchored and price[-1].n_obs > 20
