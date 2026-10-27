import csv
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from arena.__main__ import _Stop, run_bounded
from arena.generate import deps
from arena.model import Claim

ROOT = Path(__file__).resolve().parents[2]


def _ok(x):
    return x * 2


def _boom():
    raise ValueError("boom")


def _sleep():
    time.sleep(30)


def test_run_bounded_returns_results_in_order():
    assert run_bounded([(_ok, (1,)), (_ok, (2,))], time.time() + 20, _Stop()) == [2, 4]


def test_run_bounded_reports_a_failing_job():
    with pytest.raises(RuntimeError, match="boom"):
        run_bounded([(_boom, ())], time.time() + 20, _Stop())


def test_run_bounded_gives_up_at_its_budget():
    t = time.time()
    with pytest.raises(TimeoutError):
        run_bounded([(_sleep, ())], time.time() + 1, _Stop())
    assert time.time() - t < 5


def test_run_bounded_gives_up_on_sigterm():
    stop = _Stop()
    stop.flag = True
    with pytest.raises(TimeoutError):
        run_bounded([(_sleep, ())], time.time() + 20, stop)


@pytest.fixture(scope="module")
def universe(tmp_path_factory):
    """practice.csv cut to id,text,date: the stand-in universe of 00-shared.md §6."""
    d = tmp_path_factory.mktemp("universe")
    with open(ROOT / "data" / "practice.csv", encoding="utf-8", newline="") as f, \
            open(d / "universe.csv", "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(["id", "text", "date"])
        for r in csv.DictReader(f):
            w.writerow([r["id"], r["text"], r["date"]])
    (d / "lexicon.json").write_text((ROOT / "data" / "lexicon.json").read_text(encoding="utf-8"),
                                    encoding="utf-8")
    return d


def _env(universe, out, deadline=None):
    env = dict(os.environ, ARENA_UNIVERSE_DIR=str(universe), ARENA_OUTPUT_DIR=str(out))
    if deadline is not None:
        env["ARENA_DEADLINE"] = str(int(deadline))
    return env


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["id", "type", "text", "form", "label", "confidence"]
    assert all(len(r) == 6 for r in rows)
    return rows[1:]


def test_full_run_writes_a_valid_table_fast(universe, tmp_path, lexicon, attrs):
    t = time.time()
    p = subprocess.run([sys.executable, "-m", "arena"], cwd=ROOT, env=_env(universe, tmp_path),
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    assert time.time() - t < 60
    assert sorted(f.name for f in tmp_path.iterdir()) == ["output.csv"]
    rows = _rows(tmp_path / "output.csv")
    assert len(rows) >= 1000, p.stderr
    assert len({r[0] for r in rows}) == len(rows)
    assert {r[1] for r in rows} == {"fact", "compare", "change", "at_event", "relation"}
    for id_, type_, text, form, label, conf in rows:
        claim = Claim(type=type_, form=json.loads(form), label=label, evidence={},
                      text=text, confidence=float(conf), id=id_)
        if type_ == "compare":  # the CSV does not carry the kind; the validator needs it
            left = claim.form["left"]
            claim.evidence["kind"] = deps.spec_for(attrs, left["subject"], left["attribute"]).kind
        assert deps.validate(claim, lexicon) == [], (text, form)
        assert label in ("true", "false") and 0.5 <= float(conf) <= 1.0


def test_a_past_deadline_still_leaves_a_table(universe, tmp_path):
    t = time.time()
    p = subprocess.run([sys.executable, "-m", "arena"], cwd=ROOT,
                       env=_env(universe, tmp_path, deadline=time.time() + 5),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert time.time() - t < 10
    _rows(tmp_path / "output.csv")


def test_sigterm_early_still_writes_rows_within_the_grace_period(universe, tmp_path):
    p = subprocess.Popen([sys.executable, "-m", "arena"], cwd=ROOT, env=_env(universe, tmp_path),
                         stderr=subprocess.PIPE, text=True)
    out = tmp_path / "output.csv"
    for _ in range(100):
        if out.exists():
            break
        time.sleep(0.02)
    t = time.time()
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=20) == 0
    assert time.time() - t < 10                  # done before the kill would come
    assert len(_rows(out)) > 0                   # the seed claims made it in
    assert sorted(f.name for f in tmp_path.iterdir()) == ["output.csv"]
