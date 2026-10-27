# Agent C — Generators, rendering, runtime, Docker, demo

Branch: `agent-c/generate-runtime`. Read `plans/00-shared.md` first; `arena/model.py` is frozen.

## Mission

Everything from timelines to a valid `/output/output.csv` on disk inside ten
minutes, in a Docker image that builds and runs under the organisers' rules.
You are also the owner of the first shippable artefact: by end of day 1 there
must be an image that produces valid entries from the baked practice data
alone, with A's and B's modules stubbed. Each later merge only adds entries.

You own: `arena/generate/*`, `arena/render.py`, `arena/writer.py`,
`arena/__main__.py`, `data/templates.json`, `Dockerfile`, `requirements.txt`,
`tests/c/`.

You depend on (stubbed until merge): A's `Lexicon`, `validate`,
`format_value`, `attribute_words`; B's `Timelines`, `confidence`, `load_attrs`.

## Deliverables, in priority order

### C1. Runtime skeleton: `__main__.py`, `writer.py`, `Dockerfile` (day 1, first)

`python -m arena` must:

1. Read `ARENA_DEADLINE` (Unix seconds; default now+540 if missing). Keep a
   30 s safety margin: stop generating at deadline−30.
2. Install a `SIGTERM` handler that sets a flag; the main loop checks the flag
   and the clock between claims. Never block on anything longer than 1 s.
3. Load `/universe/lexicon.json`, `/universe/universe.csv`
   (paths overridable by `ARENA_UNIVERSE_DIR` and `ARENA_OUTPUT_DIR` for
   local runs), then call A/B/C modules in order:
   `pages → extract → seed+observations → weights → timelines → weights
   (pass 2) → timelines → generate → render → validate → calibrate → write`.
4. Stage timing: log each stage's seconds to stderr. If extraction has not
   finished by minute 5, proceed with the seed timelines alone (baked practice
   data) — that is the MVP path and it must always exist.
5. `Writer` opens `/output/output.csv` immediately, writes the header, and
   writes+flushes one row per claim (`csv.QUOTE_ALL`, UTF-8, `\n`). The `form`
   column is `json.dumps(form, separators=(",", ":"))`. Ids: `c-000001`
   style, unique. On exit (normal or signal) close the file; whatever is on
   disk counts.
6. Memory: never hold more than the observations + timelines; stream claims.
   `/tmp` counts against RAM — do not write there.

`Dockerfile`: `python:3.12-slim`, `COPY arena/ data/baked/ data/templates.json`,
no pip at all, `ENTRYPOINT ["python", "-m", "arena"]`, last line `USER 10001`.
Verify locally with the exact `docker run` from `00-shared.md` §6, including
`--read-only` and `--network none`, and that killing with `SIGTERM` at minute 2
leaves a readable CSV.

### C2. Day-1 MVP generator: `generate/fact.py` + `generate/perturb.py`

Using only the seed timelines (stub B with a loader over
`data/baked/timelines_seed.json`, grouping by pair and taking the latest
labelled-true value as `current`):

- `fact.py`: for each pair whose current interval exists and the kind is not
  boolean, yield a true `fact` claim with `form = {subject, attribute, value}`.
  Booleans: yield too, but `render` uses attribute words and a negation for
  false values (`Hooly is not SOC 2 certified.`).
- `perturb.py`: for each such pair, yield false `fact` claims by substituting
  the value with one of the same kind/unit/currency/period that **appears
  nowhere in the timelines for that pair** (and, for names, is a different
  lexicon subject or name of the same type seen elsewhere). Numeric
  perturbations: ×0.5, ×2, +1 unit, a plausible round number; dates: ±1 month
  same precision; versions: bump last component; set `evidence.perturbed=True`.
  Also yield "stale" falses: a superseded interval's value as a current-date
  fact, with `evidence.perturbed=False, stale=True` (B calibrates these lower).

Order of yield: anchored single-valued pairs first, then by support, then the
perturbed twins of each. Cap per pair: 1 true + 2 false by default (config
constant), so a 500-pair universe gives ~1,500 claims before the other types.

### C3. `render.py` + `data/templates.json` (day 1–2)

`render(claim, lexicon, templates) -> str`. Rules that keep A's validator
happy (and therefore the referee):

- One sentence; ends with `.`; names written as the canonical lexicon name
  (never a bare `Hooly` for a plan); values via A's `format_value`.
- `templates.json`: per claim type a list of frames, optionally keyed by
  attribute or kind, e.g. `"fact.money": ["{subject} costs {value}.",
  "{subject} is priced at {value}."]`, `"fact.date.launched":
  ["{subject} launched on {value}."]`, `"fact.boolean":
  ["{subject} is {attr_words}.", "{subject} is not {attr_words}."]`.
  Keep frames free of: any other number, any month name, any time word from
  `claims.TIME_WORDS`, any negation (except the boolean-false frame),
  comparison words (`over`, `at least`). Default frame when nothing keyed
  matches: `"{subject} {attr_words}: {value}."` — plain but valid.
- `compare`: `"{left} has a {op_phrase} {attr_words_right} than {right}."` with
  `more … than` / `fewer … than` / `the same … as` / `after` / `before`;
  never a number, never two op phrases.
- `change`: `"{subject} went from {from} to {to}."` and
  `"{subject} {verb} {to}, up from {from}."` where the direction word is set
  from `compare_values(from, to)`; names/booleans use plain `from … to`.
- `at_event`: `"{subject} had {value} at {event}."` / `"At {event}, {subject}
  ... {value}."` — event phrase immediately before the event name.
- `relation`: `"The {link_words} of {subject} {verb} {value}."`
  (`joined on 1 July 2026`).

Pick a frame deterministically by hashing the claim form so output is
reproducible. Every rendered text is immediately passed to A's `validate`
(stubbed on day 1 by a schema-only check in `tests/c/stubs/validate_stub.py`;
keep the stub strict about one sentence, no digits in compare, no negation).

### C4. The other generators (day 2)

All take `(timelines, lexicon, attrs)` and yield `Claim`s with `evidence` filled
from the intervals they used (support, conflict, n_obs, volatility, anchored,
kind, type).

- `compare.py`: pairs of (subject, attribute) with the same kind and
  comparable units (same currency AND period for money; both dates at day or
  both at month precision; both quantities in the same dimension or same
  counted noun). Use `current()` of each; `op` from A's `compare_values`;
  skip `None`. Prefer different subjects, same attribute (`price` across
  plans; `attendees` across events; `launched` across products). True claims
  with the correct op; one false twin with the opposite op. Never `eq` unless
  values are exactly equal. Never names, booleans, or the same fact twice.
- `change.py`: pairs with ≥2 intervals; yield true `from=interval[i].value,
  to=interval[i+1].value`; false twins swap from/to (only for ordered kinds)
  or use a never-seen `to`. Direction word from `compare_values`.
- `at_event.py`: for each event with a `date` interval, for each subject
  attribute with `value_at(event_date)`, yield true; false twin with a
  value from a different interval of the same pair (a genuine
  "wrong-at-the-time" lie) or a perturbed one. Prefer subjects that practice
  links to the event (Gemini languages at I/O 2026, registrations at Cloud
  Next).
- `relation.py`: walk every name-valued attribute whose current value
  resolves to a lexicon subject (cto → Bertram Gilfoil, reliability_lead →
  Holdan, venue → Quayside Hall, chair → Peter Gregori …). For the target's
  attributes with an interval overlapping the link interval, yield
  `{subject, link, target, attribute, value}`. False twin: a value of the
  target from outside the link period, or perturbed.

`generate/__init__.py` interleaves the five streams by a static priority
(`fact` true/perturbed → `compare` → `change` → `at_event` → `relation`),
round-robin inside each tier so the deadline cuts a mix rather than a type.
Expose `GEN_CONFIG` with per-type caps; default total target ~5,000 entries,
which must render+validate+write in under 2 minutes on 2 CPUs (measure).

### C5. Demo + PR hygiene (29 Oct morning)

- `scripts/demo.sh` (your file; add `scripts/` to your ownership in the PR
  description): converts `sample/sample.csv` into `/universe`, runs the
  image, prints the first 20 output rows and the validator summary. Record
  this for the video.
- README section "How to run" and "Architecture" (one paragraph each, point
  to `plans/`).
- PR title = team name; PR body = this layout and the test counts.

## Stubs you write (in `tests/c/stubs/`)

- `lexicon_stub.py`: loads `data/lexicon.json`; `resolve`, `has_attribute`,
  `events`, a naive `find_mentions`.
- `grammar_stub.py`: `format_value` for the kinds (good enough: `€59 per month`,
  `12 languages`, `99.9%`, `12 March 2026`, `v2.3`, `14 days`);
  `attribute_words` (replace `_` with space, upper-case known acronyms soc2 →
  `SOC 2`, eu → `EU`, sso, api, ar, ai, cli); `compare_values` by numeric
  value with the duration/data conversions.
- `validate_stub.py`: schema shape + "one sentence, no digits in compare, no
  negation except boolean" — strict, so day-1 output is likely still valid
  under A's real validator.
- `timelines_stub.py`: seed loader described in C2; `confidence` returns 0.8
  for true, 0.9 for perturbed false, 0.6 otherwise.

## Do not

- Do not import pandas/numpy/jsonschema inside `arena/`.
- Do not write any Hooly fact into code or templates; values always come
  from timelines.
- Do not emit a claim whose `validate()` is non-empty — drop it and count it
  in the stderr summary.
- Do not use `Hooly` as a subject for any plan or product; the lexicon
  canonical name is the only name you render.

## Done means

- Day 1: `docker build` + `docker run` on the practice stand-in produces
  ≥1,000 rows, validator-clean under your stub, in under 60 s; `SIGTERM`
  mid-run leaves a complete CSV.
- Day 2: all five generators yield; a mix of true/false by type is printed in
  the stderr summary; total run under 5 minutes with margin.
- `tests/c` green: writer quoting (commas, quotes, newlines in form), id
  uniqueness, deadline handling (simulate with a 5-second deadline), each
  generator's claims pass the stub validator, render is deterministic.
