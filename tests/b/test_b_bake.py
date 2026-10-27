"""build/bake.py regenerates data/baked/* deterministically, and the
committed files are what it produces."""
import filecmp

from build import bake

from b_helpers import BAKED

FILES = ["attrs.json", "timelines_seed.json", "priors.json", "calibration.json"]


def test_bake_is_deterministic_and_committed_files_are_fresh(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert bake.main(["--out", str(a)]) == 0
    assert bake.main(["--out", str(b)]) == 0
    for name in FILES:
        assert filecmp.cmp(a / name, b / name, shallow=False), name
        assert filecmp.cmp(a / name, BAKED / name, shallow=False), f"{name} is stale: run python build/bake.py"


def test_runtime_code_does_not_import_build_or_third_party():
    import ast
    from pathlib import Path

    allowed = {"__future__", "bisect", "calendar", "collections", "dataclasses", "datetime", "json",
               "math", "os", "typing", "arena"}
    for name in ("attrs", "reliability", "timeline", "calibrate"):
        tree = ast.parse((BAKED.parents[1] / "arena" / f"{name}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            else:
                continue
            for m in mods:
                assert m.split(".")[0] in allowed, (name, m)
