# Agent B notes: timelines, reliability, calibration

Owner: Agent B (`agent-b/timelines`). Plan: `plans/agent-b-timelines.md`.

```
python build/bake.py            # regenerate data/baked/*.json (deterministic, < 1 s)
python build/bake.py --report   # + per-pair timelines, 50 most volatile pairs, replay, calibration table
python -m pytest tests/b -s     # 52 tests (+2 that run once A is merged); -s prints the replay numbers
```

**After merging `agent-a/grammar`, rerun `python build/bake.py` and commit
`data/baked/`.** With A's extractor importable, the bake takes each practice
row's cues from A's `extract()` and measures A's precision per value kind
(`build/extraction.py`). Until then, `tests/b/test_b_bake.py` fails with "stale:
run python build/bake.py". In a merged A+B tree (A at 5143b83) the rebake
gives this table, and all 1,132 tests of `tests/a` + `tests/b` pass:

```
boolean:context 0.93  boolean:named 0.97  date:context 0.91  date:named 0.89
duration:context 0.93 duration:named 0.98 money:context 0.97 money:named 0.98
name:context 0.97     name:named 0.85     percent:context 0.96 percent:named 0.96
quantity:context 0.93 quantity:named 0.98 version:named 0.95
```

`timeline.observation_weight` multiplies every unlabelled observation by its
entry.

## Run-time call order (for C's `__main__`)

```python
from arena.attrs import load_attrs
from arena.reliability import load_priors, page_weights
from arena.timeline import load_seed, build, value_at, current, volatility
from arena.calibrate import load_calibration, confidence

obs = load_seed() + extract(pages, lexicon, attrs)       # seed first: labelled anchors
priors = load_priors()
w = page_weights(obs, priors)                             # pass 1: cue priors
tl = build(obs, w, aliases=lexicon.aliases)               # aliases is optional
w = page_weights(obs, priors, tl)                         # pass 2: + page agreement
tl = build(obs, w, aliases=lexicon.aliases)               # two rounds is the cap
```

At 10x practice size (26k observations) the four calls take about 0.4 s.
At 50x (122k), with a quarter of the numbers replaced by random noise, they
take about 5 s, against the 70% of the 30-minute run that C's runtime gives
them (starter run contract of 27 Oct). Timelines pickle (C builds them in a
forked process). The loaders' default `data/baked/...` paths resolve from
the repository root when the working directory is elsewhere.

## What goes beyond the §3 signatures (all backwards compatible)

- `build(observations, weights, aliases=None)`: optional lowercased alias ->
  canonical map, so name values written as aliases collide. Without it, names
  still merge by word prefix within a pair (`Gavin` = `Gavin Bellson`,
  `Nimbus` = `Nimbus Cloud`), and an interval shows the longest form.
- `page_weights` returns weights keyed by **row** (`timeline.row_key(o)` =
  `page_id#row_id`) **and** by page id (the mean of its rows). `build` looks up
  the row first, then the page, then 1.0. Cues are per sentence, so the row
  carries them; the page carries the agreement.
- `value_at(intervals, "2026-06")` (month or year) answers only if one
  interval holds for the whole period; before the first interval it is `None`.
- `timeline.consistent(stated, held)`: does an observation agree with a held
  value? It handles unit conversion, a coarse date covering a fine one, a name
  prefix and `op` values. C can use it to check that a perturbed value is
  really new.
- Interval values are canonical: quantity units become referee symbols
  (`inch` -> `in`), and `op` is never set.
- Seed page ids are `seed-pg-NNNN`, so they never collide with A's `pg-NNNN`.

## Evidence keys `confidence()` reads (C fills them)

`support`, `conflict`, `n_obs`, `volatility`, `kind`, `anchored`, for one
interval or for several merged flat. C's `merge_evidence` does this: min
support and n_obs, max conflict and volatility, and anchored only if both
are. Optionally, `sides: [...]` holds one dict per interval. Flags:
`perturbed` (value made up), `value_seen` (that made-up value does occur for
the pair; C never sets it, and its perturbations avoid the pair's values),
`spec_inferred` (attribute unseen in practice). `type` comes from
`claim.type`. A missing key falls back safely (support 0, volatility 1).
C's other keys (`stale`, `swapped`, `rel_diff`, `stale_support`,
`other_support`, `stale_end`) are accepted and ignored.

Which rate: C builds every claim from its own intervals. A false claim
states a superseded value, another interval's value or a swapped order, and
is false whenever those intervals are right. So every claim, true or false,
uses the interval-correctness rate (the label=true rows of the table): the
product over `sides` when given. For a false claim that rate is a lower
bound. A compare uses `q + (1 - q)/2`, because a wrong side still leaves the
op right about half the time. The label=false rows measure an observed value
the timeline contradicts, which C does not emit. They are only reported.

Checked against C's branch (`agent-c/generate-runtime`, 1d5ecb7):
`Interval.end` is the first day the next value holds. Timelines are keyed by
the observations' subject names: practice canonical names for the seed, and
A's resolved names for the universe.

## Results (practice replay, `tests/b/test_b_replay.py`)

| Replay | Accuracy | False-row recall | False-row precision | True-row accuracy |
| --- | --- | --- | --- | --- |
| labels hidden | 0.905 | 0.505 | 0.782 | 0.975 |
| 5-fold CV (other folds anchor) | 0.904 | 0.700 | 0.671 | 0.940 |
| labels visible | 0.985 | 0.906 | 0.992 | 0.999 |

The best proxy for the run is **A's extractor on the practice text, added
unlabelled to the labelled seed** (`tests/b/test_b_with_extractor.py`, which
runs once A is merged). There, the current value differs from the labels-only
timeline on **1 of 514 pairs**: Android 16 `supported_models`, a table cell
whose subject A can only guess from page context. It was 19 before the
anchored-pair rule below; A's fixes (5143b83) and the labelled-op fix brought
it from 5 to 1. CV
was 0.930 / 0.596 before that rule. CV runs at practice density, where a real
change is often seen once; the rule gives up those changes so that one misread
sentence cannot overturn a labelled value.

The five known timelines come out right with labels visible and with labels
hidden: AI Pro price 49 -> 59 on 2026-04-01, Gemini languages 6 -> 12 on
2026-03-24, HQ Berlin -> Lisbon on 2026-05-01, CTO Hendrix -> Gilfoil on
2026-07-01, Series A EUR 18M led by Raviqa Capital. The Cloud Next date also
comes out right (2 June, rescheduled to 9 June).

**The plan's day-2 target of 0.60 false-row recall with labels hidden is not
met (0.505).** Most of the misses are lies in sparse pairs: a pair seen two or
three times in practice, where a lie looks exactly like a real one-sighting
change. Raising the change penalty trades true rows for false ones:

| Change penalty | Hidden accuracy | Hidden false recall | Hidden true accuracy |
| --- | --- | --- | --- |
| 0.6 (kept) | 0.905 | 0.49 | 0.977 |
| 0.8 | 0.890 | 0.62 | 0.936 |
| 1.1 | 0.838 | 0.66 | 0.869 |

I tried and rejected three other options: a log-scaled penalty alone,
excluding self-supported observations from page agreement, and a flat burst
bonus. Each traded one number for another with no net gain.

## Decisions that differ from, or add to, the plan

- **Forward-only change points.** Practice has no genuine A -> B -> A
  sequence (the seven that look like one are 14 days = 2 weeks, 1 TB =
  1,000 GB, `Gavin` = `Gavin Bellson`, or date precision). So the search is a
  DP over value *episodes* in time order. A return to an established value is
  its own candidate only if it passes plan rule 4. I compare it against the
  other values over its first 14 days **and the 30 days before**, because
  without the lookback a few stale repeats right after the current value
  stopped being said would count as a revert. A revert also costs 3 changes.
- **Density.** The change penalty is `max(0.6, 0.3 ln(1 + pair weight))`. In
  a pair of weight >= 8, a new value must be seen on two days unless a
  labelled row pins it. Without these, a 10x simulation of the universe
  changed 16 current values: the 2026-10-26 stale nest (`founded 2024-06-01`,
  Series A EUR 25M) took over the end of the timeline. With them, 1 changes.
- **Pairs with labelled rows** get the same two-day rule at any density: a
  value no labelled row pins must be seen on two days to start an interval.
  With A's extractor on the practice text, single misread sentences had
  replaced 19 labelled current values (EUR 199 read as Workspace's
  `extra_seat_price`, the Series A lead read as co-investor, and so on); with
  the rule, 5 remained, and 1 after A's fixes and the labelled-op fix below.
- **Extraction precision** (A's, measured at bake time once A is merged)
  multiplies unlabelled observations by value kind and named/context subject.
  Replays and calibration leave it out, because they judge the gold forms.
- **Boundary placement.** A change starts at the new value's first supporting
  date. It is slightly cheaper on a date with a burst of the new value
  (support beyond one observation, x0.25, capped at 3). This is the plan's
  "page date with many V2 observations", and it moves the hidden-label Gemini
  change from 2026-02-17 (one early lie) to 2026-03-24.
- **Anchors.** A labelled true row scores 25 for its value at its date. A
  false single-fact row scores -25. False multi-fact rows and unsure rows
  count at half weight. A labelled true `op` row (`over 100 customers`) names
  no value. It scores -25 for the values it rules out and its plain weight
  for the rest, and never pins or anchors. Before this fix it gave 25 to
  every value over 100, which pulled Hooly Cloud's 1,450 customers ahead of
  610 in time order, so the timeline missed the change to 1,450.
- **Coarse dates** support the finer date they cover (`2026-06` supports
  `2026-06-09`) when building timelines; that is not the referee's equality.
- **Calibration** is fitted on cross-validated fact pseudo-claims, not on the
  labels-hidden rebuild, so the `anchored` bucket has real data. Other claim
  types are composed from per-interval rates (see above). At lookup the rate
  is made non-decreasing in support, and an anchored interval never rates
  below the same interval unanchored (thin buckets can invert by noise).
- **Rules applied after the table:** the volatility, boolean and conflict caps
  judge our timeline value, so they do not lower a made-up never-seen value
  (0.95). A flipped boolean is never "made up". 1.0 is allowed only with
  support >= 10, conflict 0 and an anchor; otherwise the cap is 0.99.
- **Priors** add a `date:YYYY-MM-DD` cue next to the month bucket.
  2026-10-26 gets 0.65. They also add `context_subject` (the subject is not
  named in the sentence). Unsure rows count as half true.

## Deferred (for the merge, or after)

- **Duplicated helpers to dedupe once A is merged:** the unit tables in
  `arena/attrs.py` (vs A's grammar), `timeline.same_value`/`value_key` (vs A's
  `same_value`), and `build/practice.NameFinder` (vs `Lexicon.find_mentions`).
  The cue regexes in `build/practice.py` stay only for rows where A's
  extractor finds nothing; every other row takes A's cues at bake time. A
  emits the model's cue names (`speaker`, `gavin`, `testimonial`, `boast`,
  `hearsay`, `announce_future`, `press_release`, `release_notes`,
  `table_cell`, `headline`). Unknown cue names weigh 1.0.
- **Not done:** snapping a boundary to an `announce_future` date or an event's
  date; a "past dates do not change" rule for `launched`/`released`/`opened`
  (mixed evidence: the Sustainability Report date was moved after it had
  passed); extending a false label's exclusion beyond its own date;
  `days_since_last_obs` (an `Interval` has no last-seen date and `model.py` is
  frozen).
- **Known limit:** a lie repeated on many days with nothing contradicting it
  near the end of the year cannot be told from a real change without labels.
  The ±10-day jitter variant of the 10x simulation shows this.

## Calibration table (label x anchored x kind, CV fact pseudo-claims)

Interval correctness (the rows `confidence()` uses):

```
label  anchored kind       right     n
true   0        boolean    0.872    47
true   0        date       0.919    37
true   0        duration   0.909    22
true   0        money      0.931    29
true   0        name       0.895    19
true   0        percent    0.923    39
true   0        quantity   0.908   142
true   1        boolean    0.979    94
true   1        date       0.981   104
true   1        duration   0.982   171
true   1        money      0.979   192
true   1        name       0.994   167
true   1        percent    0.953   127
true   1        quantity   0.973   665
true   1        version    0.990    96
```

The label=false rows (an observed value the timeline contradicts, judged
false) are much lower, for example quantity 0.56 (n=111). In CV the
anchored-pair rule rejects real one-sighting changes, which is one reason
`confidence()` does not use those rows.

The full table, with volatility and support buckets, is in
`data/baked/calibration.json`. Print it with `python build/bake.py --report`
or `arena.calibrate.describe()`.
