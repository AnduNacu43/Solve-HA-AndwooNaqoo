"""B on top of A's real extractor. Skipped until agent-a/grammar is merged.

The practice text is read by A's extract() exactly as the universe will be,
added unlabelled to the labelled seed, and the timelines must keep the
current values the labels give (one misread sentence must not replace them).
"""
import pytest

from arena.attrs import load_attrs
from arena.timeline import current, value_key
from build.extraction import available, extract_practice, precision_table
from build.replay import run_pipeline

from b_helpers import BAKED, ROOT

pytestmark = pytest.mark.skipif(not available(), reason="A's arena.extract is not merged yet")


@pytest.fixture(scope="module")
def extracted():
    return extract_practice(str(ROOT / "data" / "practice.csv"), str(ROOT / "data" / "lexicon.json"),
                            load_attrs(str(BAKED / "attrs.json")))


def test_extractor_precision_table(extracted, practice_obs):
    table = precision_table(extracted, practice_obs)
    assert table and all(0 < p <= 1 for p in table.values())
    assert sum(table.values()) / len(table) > 0.8


def test_seed_plus_extracted_practice_keeps_the_labelled_current_values(extracted, practice_obs, priors):
    seed_only = run_pipeline(practice_obs, priors)
    merged = run_pipeline(practice_obs + extracted, priors)
    differ = [k for k, ivs in seed_only.items()
              if k in merged and current(ivs) and current(merged[k])
              and value_key(current(ivs).value) != value_key(current(merged[k]).value)]
    print(f"\ncurrent value differs on {len(differ)} of {len(seed_only)} pairs: {differ}")
    assert len(differ) <= 10
    price = [(iv.start, iv.value.value) for iv in merged[("Hooly AI Pro", "price")]]
    assert price == [("2025-10-07", 49), ("2026-04-01", 59)]
