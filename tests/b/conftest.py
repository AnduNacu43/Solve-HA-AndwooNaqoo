"""Shared fixtures for Agent B's tests.

Stubs are loaded by file path under unique module names (b_helpers) so that
tests/a, tests/b and tests/c can run in one pytest session without a `stubs`
package clash.
"""
from __future__ import annotations

import pytest

from b_helpers import BAKED, ROOT  # noqa: F401  (puts ROOT on sys.path)
from arena.attrs import load_attrs  # noqa: E402
from arena.calibrate import load_calibration  # noqa: E402
from arena.model import Observation, Value  # noqa: E402
from arena.reliability import load_priors  # noqa: E402
from build.practice import load_lexicon, practice_observations  # noqa: E402
from build.replay import run_pipeline  # noqa: E402

@pytest.fixture(scope="session")
def practice_obs() -> list[Observation]:
    return practice_observations(str(ROOT / "data" / "practice.csv"), str(ROOT / "data" / "lexicon.json"))


@pytest.fixture(scope="session")
def lexicon_json() -> dict:
    return load_lexicon(str(ROOT / "data" / "lexicon.json"))


@pytest.fixture(scope="session")
def priors() -> dict:
    return load_priors(str(BAKED / "priors.json"))


@pytest.fixture(scope="session")
def attrs():
    return load_attrs(str(BAKED / "attrs.json"))


@pytest.fixture(scope="session")
def calibration() -> dict:
    return load_calibration(str(BAKED / "calibration.json"))


@pytest.fixture(scope="session")
def timelines(practice_obs, priors):
    """Practice timelines with labels visible (the run-time seed situation)."""
    return run_pipeline(practice_obs, priors)


@pytest.fixture
def make_obs():
    """Factory for synthetic observations; every call is its own row and page
    unless page/row are given."""
    counter = iter(range(1, 10_000))

    def make(value: Value, date: str, subject="Acme", attribute="attr", page=None, row=None,
             label=None, cues=(), named=True) -> Observation:
        n = next(counter)
        return Observation(subject=subject, attribute=attribute, value=value, date=date,
                           page_id=page or f"pg-{n:04d}", row_id=row or f"r-{n}",
                           sentence="synthetic", subject_in_sentence=named,
                           cues=frozenset(cues), label=label)

    return make
