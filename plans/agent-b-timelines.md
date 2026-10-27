# Agent B — Baked data, timelines, reliability, calibration

Branch: `agent-b/timelines`. Read `plans/00-shared.md` first; `arena/model.py` is frozen.

## Mission

Turn observations into time-stamped truth. The practice set gives you 2,402
labelled facts over a year in which values change and some pages lie; your job
is to (1) bake everything learnable from it into the image, (2) at run time
merge the seed with ~9× more unlabelled observations into per-pair timelines,
with page reliability weighting, and (3) turn evidence into an honest
confidence number. None of this needs A's parser: practice rows already carry
structured `form` values, so you work on `Observation` objects built straight
from the CSV.

You own: `build/bake.py`, `data/baked/*`, `arena/attrs.py`,
`arena/reliability.py`, `arena/timeline.py`, `arena/calibrate.py`, `tests/b/`.

You depend on: nothing at build time. At run time A's `extract` feeds you
`Observation`s with the same shape you bake, so a stub is a trivial loader.

## Background you should internalise (from the content map)

- Labels are per row, not per fact; a false row has ≥1 false fact. 373 rows
  have 2+ facts. "True" means true on the page date.
- False rows are mostly: stale values repeated on later pages (2026-10-26 is a
  nest of them), inflated marketing numbers, early announcements of later
  facts, wrong attributions, internal contradictions. `unsure` (39 rows) is
  single-source brag/hearsay with no corroboration.
- Transcript lines (`Speaker:`), rows mentioning Gavin, testimonials and boasts
  are false about twice as often as the base rate (14.6%).
- Pairs: 185 single-valued, 214 two-valued, 115 with 3+. Known timelines:
  AI Pro price €49 → €59 on 2026-04-01; Gemini languages 6 → 12 on 2026-03-24;
  HQ Berlin → Lisbon on 2026-05-01; CTO Richard Hendrix → Bertram Gilfoil on
  2026-07-01; Series A €18M led by Raviqa Capital. Use these as regression
  tests, not as hard-coded facts.
- The as-of date is 2026-10-29, one day after the last practice page.
- The run-time lexicon may hold subjects and attributes practice never shows.

## Deliverables, in priority order

### B1. `build/bake.py` + `data/baked/attrs.json` (day 1, first)

Read `data/practice.csv`; for every fact in every `form` build an
`Observation` (`label` set from the row, `subject_in_sentence` by alias
substring test, cues by the rule list in A's plan §A5 — copy the simple
regexes; they need not match A's exactly). Write:

- `attrs.json`: `{ "subject|attribute": AttrSpec }` with kind, unit (singular),
  currency, per, n_seen, by majority vote; keep a second map keyed by bare
  attribute name for fallback. Note the quirks: forms use `inch` where the
  referee writes `in`; counted nouns like `star`, `fold`, `megapixel`. Store
  what practice says and expose `canonical_unit()` that maps `inch → in`.
- `timelines_seed.json`: the full observation list (JSON of `Observation`),
  so run time starts from labelled anchors.
- `priors.json`: see B2.
- `calibration.json`: see B4.

`arena/attrs.py` loads these; `infer_spec(values)` picks the majority kind/unit
for an attribute the baked file has never seen.

Tests: every one of the 514 lexicon pairs has a spec; the known kinds (price →
money EUR/month, languages → quantity language, launched → date) come out right.

### B2. `reliability.py` (day 1)

`page_weights(observations, priors, timelines=None) -> dict[page_id, float]`.

Pass 1 (no timelines): weight = product of cue multipliers from `priors.json`,
learned at bake time as P(true | cue) / P(true) on practice rows, clipped to
[0.3, 1.0]. Include a `date_bucket` cue (month) because 2026-10-26 pages are
systematically stale.

Pass 2 (with timelines): multiply by the page's agreement rate — share of its
observations whose value equals `value_at(intervals, page.date)` — smoothed
with a Beta(2,2) prior so one-observation pages don't swing. This is one EM
round of classic truth discovery; two rounds is the cap (10-minute budget, and
it converges fast).

Observations with `op` set (over/under) count at 0.5 weight; `approximate`
never reaches you (A drops them).

### B3. `timeline.py` (day 1–2) — the core

`build(observations, weights) -> Timelines`, plus `value_at`, `current`,
`volatility`, `load_seed`.

Algorithm per (subject, attribute), observations sorted by date:

1. Group observations by `same_value` (write your own equality on
   `Value.to_json()` plus the unit conversions listed in A's plan — duplicate
   the small conversion table rather than import across the boundary; note it
   in "deferred" so one copy is deleted after merge).
2. Anchors: a labelled-true practice observation pins its value at its date;
   a labelled-false single-fact row excludes that value at that date. For
   multi-fact false rows, exclude nothing (you don't know which fact lied)
   but halve the row's weight.
3. Change-point search: sweep dates; a candidate boundary between value V1
   and V2 is placed where weighted support flips. Prefer boundaries that
   coincide with an `announce_future` observation of V2, a page date with
   many V2 observations (e.g. 2026-04-01 for the price), or the event's date.
4. After the last boundary, late observations of an old value are "stale"
   and count as conflict, not as a new interval, unless their weighted
   support exceeds the current value's by 2× over a 14-day window (a genuine
   revert).
5. Every interval records support, conflict, n_obs, anchored. Volatility =
   number of intervals.

Name-valued attributes: same algorithm; the value key is the resolved
canonical name (ask A's lexicon at run time; at bake time use the lexicon
JSON directly). Treat `"Gavin"` and `"Gavin Bellson"` as the same value via
alias resolution.

Booleans: same algorithm; conflict is frequent (marketing says yes), so
booleans get an extra conservative multiplier in calibration.

Events: `date` attribute intervals are what `at_event` claims will index; make
sure `value_at` on an event's date works with month-precision observations
(`2026-06` covers 2026-06-09).

Validation (this is your main test): rebuild timelines from practice with
labels **hidden**, then for every practice row check that `value_at(date)`
equals the stated value iff the row is labelled true (multi-fact rows: all
facts). Report accuracy, and separately for false rows (recall of lies).
Targets: ≥0.90 overall, ≥0.60 on false rows on day 2. Then rerun with labels
visible to confirm anchors raise both.

### B4. `calibrate.py` + `calibration.json` (day 2)

`confidence(claim, calibration) -> float` in [0.5, 1.0].

Features from `claim.evidence` (C fills these from your `Interval`s; agree the
names in `model.py`'s comment): support, conflict, n_obs, volatility, kind,
anchored, perturbed, days_since_last_obs, type.

Fit at bake time by generating pseudo-claims from the labels-hidden rebuild
(B3) and recording whether each matched the label: bucket by (type, kind,
volatility bucket, anchored, support bucket) and store the empirical accuracy
with Laplace smoothing. That is a lookup table — no model at run time. Apply:

- `perturbed` false claims whose value appears nowhere in the universe: 0.95.
- `fact`/`compare` on a single-valued, anchored pair with ≥3 obs: ≥0.9.
- anything on a pair with volatility ≥4: cap 0.7.
- booleans: cap 0.8 unless anchored.
- a true claim with conflict > support/3: cap 0.65.
- never emit 1.0 except support ≥10, conflict 0, anchored.
- unseen run-time attribute (spec inferred): cap 0.6.

If the hidden score is Brier/log-loss, honest probabilities win; if it is
accuracy-weighted, the caps cost little. Document the table so C can print it
in the demo.

### B5. Nice-to-haves

- A `python -m build.bake --report` that prints per-pair timelines as text for
  the README and the demo video.
- A list of the 50 most volatile pairs for C to deprioritise.

## Stubs you write (in `tests/b/stubs/`)

- `extract_stub.py`: converts `practice.csv` into `Observation`s (which is
  mostly your bake code — share it via `build/`).
- `lexicon_stub.py`: minimal alias → canonical resolver read from
  `data/lexicon.json`, used only for name-valued attributes.

## Do not

- Do not import from `arena.grammar`, `arena.lexicon`, `arena.extract`,
  `arena.generate`. Duplicate tiny helpers and list them under "deferred" so
  the merger can dedupe.
- Do not load pandas/numpy inside `arena/`. Build-time code may.
- Do not hard-code any Hooly fact into `arena/`; everything comes from
  `data/baked/`.

## Done means

- `python build/bake.py` regenerates `data/baked/*` deterministically.
- `tests/b` green, including the labels-hidden replay with the accuracy
  numbers printed.
- Timelines for the five known pairs match the content-map worked timelines.
- `confidence()` returns values in [0.5, 1] for every pseudo-claim and is
  monotone in support.
