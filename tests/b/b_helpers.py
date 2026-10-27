"""Paths and stub loading for tests/b (named uniquely so a combined pytest
run with tests/a and tests/c never imports another agent's helper)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAKED = ROOT / "data" / "baked"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_stub(name: str):
    path = Path(__file__).parent / "stubs" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"tests_b_stubs_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
