# Agent B notes: timelines, reliability, calibration

Owner: Agent B (`agent-b/timelines`). Plan: `plans/agent-b-timelines.md`.

```
python build/bake.py            # regenerate data/baked/*.json (deterministic, < 1 s)
python build/bake.py --report   # + per-pair timelines, 50 most volatile pairs, replay, calibration table
python -m pytest tests/b -s     # 45 tests; -s prints the replay numbers
```

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

One interval: `support`, `conflict`, `n_obs`, `volatility`, `kind`, `anchored`.
Several intervals (compare, change, at_event, relation): put one dict per
interval in `sides: [...]`; `kind` may stay at top level. Flags: `perturbed`
(value made up), `value_seen` (that made-up value does occur for the pair in
the universe), `spec_inferred` (attribute unseen in practice). `type` comes
from `claim.type`. A missing key falls back safely (support 0, volatility 1).

Composition: a claim on several intervals uses the product of their rates. A
compare uses `q + (1 - q)/2`, because a wrong side still leaves the op right
about half the time.

## Results (practice replay, `tests/b/test_b_replay.py`)

| Replay | Accuracy | False-row recall | False-row precision | True-row accuracy |
| --- | --- | --- | --- | --- |
| labels hidden | 0.905 | 0.505 | 0.782 | 0.975 |
| 5-fold CV (other folds anchor) | 0.930 | 0.596 | 0.897 | 0.988 |
| labels visible | 0.984 | 0.906 | 0.988 | 0.998 |

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
bonus. Each traded one number for another with no net gain. At run time the
universe is about 10x denser and every practice row is an anchor, so CV is the
closer proxy.

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
- **Boundary placement.** A change starts at the new value's first supporting
  date. It is slightly cheaper on a date with a burst of the new value
  (support beyond one observation, x0.25, capped at 3). This is the plan's
  "page date with many V2 observations", and it moves the hidden-label Gemini
  change from 2026-02-17 (one early lie) to 2026-03-24.
- **Anchors.** A labelled true row scores 25 for its value at its date. A
  false single-fact row scores -25. False multi-fact rows and unsure rows
  count at half weight.
- **Coarse dates** support the finer date they cover (`2026-06` supports
  `2026-06-09`) when building timelines; that is not the referee's equality.
- **Calibration** is fitted on cross-validated fact pseudo-claims, not on the
  labels-hidden rebuild, so the `anchored` bucket has real data. Other claim
  types are composed from per-interval rates (see above). The rate is made
  non-decreasing in support at lookup.
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
  `same_value`), `build/practice.NameFinder` (vs `Lexicon.find_mentions`), and
  the cue regexes in `build/practice.py` (vs A's extract cues). Priors are
  learned per cue *name*, so A's cue names should match: `speaker`, `gavin`,
  `testimonial`, `boast`, `hearsay`, `announce_future`, `press_release`,
  `release_notes`, `table_cell`, `headline`, plus `hedge` and `first_person`.
  Unknown cue names weigh 1.0.
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

```
label  anchored kind       right     n
false  1        boolean    0.818    11
false  1        duration   0.909    11
false  1        money      1.000    13
false  1        name       1.000     7
false  1        percent    0.933    15
false  1        quantity   0.857    63
false  1        version    0.375     8
true   0        boolean    0.833    54
true   0        date       0.872    47
true   0        money      0.921    38
true   0        quantity   0.890   191
true   1        boolean    0.979    94
true   1        date       0.981   104
true   1        money      0.979   192
true   1        name       0.994   168
true   1        quantity   0.973   665
true   1        version    0.990    96
```

The full table, with volatility and support buckets, is in
`data/baked/calibration.json`. Print it with `python build/bake.py --report`
or `arena.calibrate.describe()`.
