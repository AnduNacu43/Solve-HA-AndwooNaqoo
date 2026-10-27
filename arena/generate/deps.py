"""Where C's code gets the functions A and B own (00-shared.md §3).

Each name comes from the real module when it imports and defines it, else
from C's stub in tests/c/stubs/, so the runtime works before, during and after
the merge. ARENA_STUBS=1 forces every stub (tests); ARENA_STUBS=name,name
forces only those names. SOURCES records where each name came from."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

STUBS_DIR = Path(__file__).resolve().parents[2] / "tests" / "c" / "stubs"

_WHERE = {
    "arena.lexicon": ("lexicon_stub", ["Lexicon"]),
    "arena.pages": ("extract_stub", ["load_universe"]),
    "arena.extract": ("extract_stub", ["extract"]),
    "arena.validate": ("validate_stub", ["validate"]),
    "arena.grammar.values": ("grammar_stub", ["format_value", "same_value", "compare_values"]),
    "arena.grammar.claims": ("grammar_stub", ["attribute_words"]),
    "arena.grammar.sentences": ("grammar_stub", ["NEGATION_WORDS", "TIME_WORDS", "MONTH_WORDS"]),
    "arena.attrs": ("timelines_stub", ["load_attrs", "spec_for"]),
    "arena.reliability": ("timelines_stub", ["load_priors", "page_weights"]),
    "arena.timeline": ("timelines_stub", ["load_seed", "build", "value_at", "current", "volatility"]),
    "arena.calibrate": ("timelines_stub", ["load_calibration", "confidence"]),
}

SOURCES: dict[str, str] = {}


def _forced() -> set[str]:
    raw = os.environ.get("ARENA_STUBS", "").strip()
    if raw in ("1", "all", "true"):
        return {n for _, names in _WHERE.values() for n in names}
    return {n.strip() for n in raw.split(",") if n.strip()}


def _stub(module: str):
    if str(STUBS_DIR) not in sys.path:
        sys.path.append(str(STUBS_DIR))
    return importlib.import_module(module)


def _resolve() -> dict[str, object]:
    forced = _forced()
    out = {}
    for real, (stub, names) in _WHERE.items():
        try:
            mod = importlib.import_module(real)
        except Exception as e:  # missing before merge, or broken: fall back
            mod, why = None, f"{type(e).__name__}"
        for name in names:
            if mod is not None and name not in forced and hasattr(mod, name):
                out[name] = getattr(mod, name)
                SOURCES[name] = real
            else:
                out[name] = getattr(_stub(stub), name)
                SOURCES[name] = f"stub:{stub}" + ("" if mod is not None else f" ({why})")
    return out


globals().update(_resolve())


def stubbed() -> list[str]:
    """Names currently served by a stub."""
    return sorted(n for n, src in SOURCES.items() if src.startswith("stub"))
