import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from arena.lexicon import Lexicon  # noqa: E402
from tests.a.stubs.attrs_stub import load_attrs  # noqa: E402


@pytest.fixture(scope="session")
def lexicon():
    return Lexicon.load("data/lexicon.json")


@pytest.fixture(scope="session")
def attrs():
    return load_attrs()
