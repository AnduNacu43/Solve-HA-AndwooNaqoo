"""python -m arena: /universe in, /output/output.csv out, inside the deadline.

pages -> extract -> seed + observations -> weights -> timelines -> weights
(pass 2) -> timelines -> generate -> render -> calibrate -> validate -> write.

output.csv exists, with its header, before anything else runs, and is only
ever replaced by a complete table (arena.writer), so a SIGTERM, a kill or a
crash leaves a valid table. Extraction and timeline building run in forked
workers, each with a share of the time to the deadline; when they fail or
overrun, the run carries on from the seed (baked practice) timelines alone.
After SIGTERM the run keeps writing for SIGTERM_GRACE_S, then publishes."""
from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_S = 30 * 60          # the contract's run time, when ARENA_DEADLINE is unset
SAFETY_S = 30            # stop generating this long before ARENA_DEADLINE
EXTRACT_SHARE = 0.5      # extraction must be done by half the run
TIMELINES_SHARE = 0.7    # timelines from the universe by 70% of it
GENERATE_RESERVE_S = 60  # always leave this long for generate+write
SIGTERM_GRACE_S = 6      # keep writing this long after SIGTERM (the kill comes at 10 s)


class _Stop:
    """SIGTERM/SIGINT handler: records that, and when, the signal came."""

    def __init__(self):
        self.flag = False
        self.at = None

    def __call__(self, signum, frame):
        self.flag = True
        self.at = time.time()

    def expired(self) -> bool:
        """A signal came and its grace period is over."""
        return self.flag and (self.at is None or time.time() > self.at + SIGTERM_GRACE_S)


def log(msg: str) -> None:
    print(f"[arena {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _child(conn, fn, args):
    signal.signal(signal.SIGTERM, signal.SIG_DFL)  # the parent's terminate() must kill
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        conn.send(("ok", fn(*args)))
    except BaseException as e:  # report, never hang the parent
        conn.send(("err", f"{type(e).__name__}: {e}"))
    finally:
        conn.close()


def run_bounded(jobs: list[tuple], until: float, stop: _Stop) -> list:
    """Run each (fn, args) in its own forked process; return their results in
    order. Raises TimeoutError past `until` or on SIGTERM, RuntimeError when a
    job fails. Without fork, runs in-process (no time bound)."""
    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        return [fn(*args) for fn, args in jobs]
    procs, conns = [], []
    for fn, args in jobs:
        recv, send = ctx.Pipe(duplex=False)
        p = ctx.Process(target=_child, args=(send, fn, args), daemon=True)
        p.start()
        send.close()
        procs.append(p)
        conns.append(recv)
    results: list = [None] * len(jobs)
    pending = set(range(len(jobs)))
    try:
        while pending:
            if stop.flag or time.time() > until:
                raise TimeoutError(f"{len(pending)} of {len(jobs)} jobs unfinished")
            for i in list(pending):
                if conns[i].poll(0.2):
                    try:
                        status, payload = conns[i].recv()
                    except EOFError:
                        raise RuntimeError("worker died without a result")
                    if status != "ok":
                        raise RuntimeError(payload)
                    results[i] = payload
                    pending.discard(i)
                elif not procs[i].is_alive() and not conns[i].poll(0):
                    raise RuntimeError(f"worker exited with code {procs[i].exitcode}")
        return results
    finally:
        for p in procs:
            if p.is_alive():
                p.terminate()
            p.join(timeout=1)


def _chunks(items: list, n: int) -> list[list]:
    n = max(1, min(n, len(items)))
    size = -(-len(items) // n)
    return [items[i:i + size] for i in range(0, len(items), size)]


def _timelines(deps, seed, observations, aliases):
    """Two rounds of page weights and timeline building (00-shared.md, B)."""
    obs = seed + observations
    priors = deps.load_priors()
    weights = deps.page_weights(obs, priors)
    timelines = deps.build(obs, weights, aliases=aliases)
    weights = deps.page_weights(obs, priors, timelines)
    return deps.build(obs, weights, aliases=aliases)


def _seed_timelines(deps, seed, aliases):
    priors = deps.load_priors()
    return deps.build(seed, deps.page_weights(seed, priors), aliases=aliases)


def _load_seed(deps):
    """The baked seed, or ARENA_SEED: a seed file in its place, or "none"
    (held-out evaluation runs)."""
    path = os.environ.get("ARENA_SEED")
    if path == "none":
        return []
    return deps.load_seed(path) if path else deps.load_seed()


def main() -> int:
    t0 = time.time()
    deadline = float(os.environ.get("ARENA_DEADLINE") or t0 + RUN_S)
    stop_at = deadline - SAFETY_S
    stop = _Stop()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    universe = Path(os.environ.get("ARENA_UNIVERSE_DIR", "/universe"))
    output = Path(os.environ.get("ARENA_OUTPUT_DIR", "/output"))

    from arena.writer import Writer
    writer = Writer(str(output / "output.csv"))
    log(f"output {output / 'output.csv'} open; {stop_at - t0:.0f}s to generate")
    stats: dict = {}
    try:
        _run(t0, stop_at, stop, universe, writer, stats)
    except Exception as e:  # whatever is on disk still counts
        log(f"run stopped early: {type(e).__name__}: {e}")
    finally:
        writer.close()
        log(f"wrote {writer.count} rows in {time.time() - t0:.1f}s"
            + (" (SIGTERM)" if stop.flag else ""))
    return 0


def _run(t0, stop_at, stop, universe, writer, stats) -> None:
    def stage(name, since):
        log(f"{name}: {time.time() - since:.1f}s")
        return time.time()

    t = time.time()
    from arena.generate import deps, generate
    from arena.render import candidates, load_templates
    from arena.writer import OutputFull
    if deps.stubbed():
        log(f"stubbed: {', '.join(deps.stubbed())}")

    lexicon_path = universe / "lexicon.json"
    if not lexicon_path.exists():
        log(f"{lexicon_path} missing; using the baked practice lexicon")
        lexicon_path = ROOT / "data" / "lexicon.json"
    lexicon = deps.Lexicon.load(str(lexicon_path))
    attrs = deps.load_attrs()
    seed = _load_seed(deps)
    t = stage(f"load: {len(lexicon.subjects)} subjects, {len(seed)} seed observations", t)

    span = stop_at - t0
    observations = []
    try:
        pages = deps.load_universe(str(universe / "universe.csv"))
        t = stage(f"pages: {len(pages)}", t)
        until = min(t0 + EXTRACT_SHARE * span, stop_at - GENERATE_RESERVE_S)
        workers = int(os.environ.get("ARENA_EXTRACT_WORKERS", "2"))
        parts = run_bounded([(deps.extract, (chunk, lexicon, attrs))
                             for chunk in _chunks(pages, workers)], until, stop)
        observations = [o for part in parts for o in part]
        t = stage(f"extract: {len(observations)} observations", t)
    except Exception as e:
        log(f"extraction skipped ({type(e).__name__}: {e}); seed timelines only")
        observations = []

    timelines = None
    if observations and not stop.flag:
        try:
            until = min(t0 + TIMELINES_SHARE * span, stop_at - GENERATE_RESERVE_S)
            timelines = run_bounded([(_timelines, (deps, seed, observations, lexicon.aliases))],
                                    until, stop)[0]
            t = stage(f"timelines: {len(timelines)} pairs from seed + universe", t)
        except Exception as e:
            log(f"universe timelines failed ({type(e).__name__}: {e}); seed timelines only")
    if timelines is None:
        timelines = _seed_timelines(deps, seed, lexicon.aliases)
        t = stage(f"timelines: {len(timelines)} pairs from seed", t)

    calibration = deps.load_calibration()
    templates = load_templates()
    # names the universe states besides the lexicon's own: A's validate refuses others
    known_names = {o.value.value for o in seed if o.value.kind == "name"}
    kept, dropped, reasons = Counter(), Counter(), Counter()
    for claim in generate(timelines, lexicon, attrs, stats=stats):
        if stop.expired() or time.time() > stop_at:
            log("deadline reached; stopping generation")
            break
        try:
            claim.confidence = min(1.0, max(0.5, float(deps.confidence(claim, calibration))))
            claim.id = writer.next_id()
            errors = ["no frame fits"]
            for text in candidates(claim, lexicon, templates):
                claim.text = text
                errors = deps.validate(claim, lexicon, attrs=attrs, known_names=known_names)
                if not errors:
                    break
            if errors:
                dropped[claim.type] += 1
                reasons[errors[0][:60]] += 1
                continue
            writer.write(claim)
            kept[(claim.type, claim.label)] += 1
        except OutputFull as e:
            log(f"table is full ({e}); stopping generation")
            break
        except Exception as e:  # one bad claim never stops the run
            dropped[claim.type] += 1
            reasons[f"{type(e).__name__}: {e}"[:60]] += 1
    stage("generate+write", t)
    _summary(kept, dropped, reasons, stats)


def _summary(kept: Counter, dropped: Counter, reasons: Counter, stats: dict) -> None:
    for ctype in ("fact", "compare", "change", "at_event", "relation"):
        log(f"  {ctype:9} true {kept[(ctype, 'true')]:5}  false {kept[(ctype, 'false')]:5}"
            f"  dropped {dropped[ctype]:5}")
    for reason, n in reasons.most_common(8):
        log(f"  dropped {n:5} x {reason}")
    for name, err in stats.get("generator_errors", {}).items():
        log(f"  generator {name} failed: {err}")


if __name__ == "__main__":
    sys.exit(main())
