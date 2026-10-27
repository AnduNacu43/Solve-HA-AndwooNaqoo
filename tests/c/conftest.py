"""tests/c runs against C's stubs by default. After the merge,
`ARENA_STUBS= python -m pytest tests/c` runs the same tests against A's and
B's real modules (an integration check)."""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("ARENA_STUBS", "1")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def lexicon():
    from arena.generate import deps
    return deps.Lexicon.load(str(ROOT / "data" / "lexicon.json"))


@pytest.fixture(scope="session")
def attrs():
    from arena.generate import deps
    return deps.load_attrs()


@pytest.fixture(scope="session")
def timelines():
    from arena.generate import deps
    seed = deps.load_seed()
    return deps.build(seed, deps.page_weights(seed, deps.load_priors()))


@pytest.fixture(scope="session")
def templates():
    from arena.render import load_templates
    return load_templates()
