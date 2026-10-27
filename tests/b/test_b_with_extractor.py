"""B on top of A's real extractor. Skipped until agent-a/grammar is merged.

The run's situation in miniature (Agent C's held-out design): half of the
practice pages are the labelled seed, the other half's text is the universe,
read by A's extract() without labels. The answer key is the timelines built
with every practice label. Reading the other half must fix most of the
current values the seed half alone gets wrong.
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


def test_unlabelled_text_fixes_most_current_values_a_labelled_half_gets_wrong(
        extracted, practice_obs, priors):
    key = run_pipeline(practice_obs, priors)

    def wrong(tl):
        return sum(1 for k, ivs in key.items() if current(ivs) and (
            k not in tl or not current(tl[k]) or value_key(current(tl[k]).value) != value_key(current(ivs).value)))

    pages = sorted({o.page_id for o in practice_obs})
    half = {p: i % 2 for i, p in enumerate(pages)}
    row_half = {o.row_id: half[o.page_id] for o in practice_obs}
    seed_only = with_text = 0
    for h in (0, 1):
        seed = [o for o in practice_obs if half[o.page_id] == h]
        text = [o for o in extracted if row_half.get(o.row_id) == 1 - h]
        seed_only += wrong(run_pipeline(seed, priors))
        with_text += wrong(run_pipeline(seed + text, priors))
    print(f"\nwrong current values over both halves: seed half only {seed_only}, "
          f"with the other half's text {with_text} (of {2 * len(key)})")
    assert with_text < 0.5 * seed_only
    assert with_text <= 110          # 88 with A at 0f10197 and B at this commit
    price = [(iv.start, iv.value.value) for iv in run_pipeline(practice_obs + extracted, priors)
             [("Hooly AI Pro", "price")]]
    assert price == [("2025-10-07", 49), ("2026-04-01", 59)]
