# Agent A — Grammar, lexicon, extraction, referee clone

Branch: `agent-a/grammar`. Read `plans/00-shared.md` first; `arena/model.py` is frozen.

## Mission

Build the one parser that both reads the universe and polices our output. The
referee is deterministic and its grammars are published in
`contracts/claim-forms.md` and `contracts/value-forms.md`, so a faithful
reimplementation is the highest-leverage code in the project: every invalid
entry we never emit is a point we never lose, and every value we parse
correctly is an observation the timelines can use.

You own: `arena/lexicon.py`, `arena/pages.py`, `arena/grammar/*`,
`arena/extract.py`, `arena/validate.py`, `tests/a/`.

You depend on (via stubs until merge): B's `attrs.load_attrs` / `spec_for`.
Nothing else.

## Deliverables, in priority order

Stop at any point and you have shipped something useful. Do them in this order.

### A1. `grammar/values.py` — value parser + canonical formatter (day 1, first half)

`parse_values(sentence) -> list[ParsedValue]` and `format_value(v) -> str`.

Implement `value-forms.md` literally. The content map (§9) is a faithful digest;
the authoritative text is the contract file. Non-negotiables:

- Numbers: decimal point, thousands commas; decimal comma only for money;
  `99,9`, `1,5`, `1.000.000`, `1.500` read as nothing; percentages may have
  3 decimals; number words zero…ninety-nine, a hundred, three hundred, a dozen;
  scales thousand/million/M/billion/bn/k.
- A bare 4-digit number 1900–2099 is a year (date, year precision).
- Quantity: physical units (B/KB/MB/GB/TB, mm/cm/m/km/in/"/″, g/kg, mAh,
  Hz/kHz/MHz/GHz, mW/W/kW; `m` is metres, `M` is million), otherwise a counted
  noun stored singular, ≤2 words between number and noun. `12 people` → unit
  `person`. A duration unit is never a quantity unit.
- Money: symbols € $ £ US$, ISO codes, words euro/dollar/lei; periods
  /month /mo a month per month monthly (+day/week/year, /yr, per annum,
  annually); `per user` or `/seat` may precede; no period = one-off;
  `from €39` = 39 eq. `5 pounds` → nothing.
- Date: all listed forms, year required, precision kept; `12/03/2026`,
  `March 12`, `Q4 2026` → nothing. Month abbreviations with optional dot.
- Version: `v2.3`, `version 2.3`, `ver. 2.3`, a number with ≥2 dots, or one
  decimal point right after a capitalised name. `Hooly Gemini 11` → nothing.
- Duration: units and aliases, fortnight = 2 weeks, decade = 10 years,
  `a`/`an` = 1 only after the listed prepositions, `half an hour` → nothing,
  `1,000 requests a day` states no duration.
- Name: handled by `lexicon.find_mentions`, not here (but `format_value` of a
  name returns it unchanged).
- Boolean: `format_value` raises; booleans are rendered through attribute
  words by C.
- Flags: `negated` (negation earlier in same clause; clauses end at
  `. , ; : ! ? • · |` or blank line), `approximate` (about/around/approx/
  roughly/nearly/almost/circa/ca/some/estimated/est/close to/more or less/
  ~/≈/± before; or so/give or take/-ish after), `range_end` (10-20 GB,
  10 to 20 GB, between 10 and 20 GB, 1 or 2 days; `X or Y` of different
  kinds is a choice and both read).
- `op` on the parsed `Value` when a comparison word precedes/follows
  (over, more than, under, at least, up to, +, or more …) — the full table
  in value-forms.md. Keep it: B uses `op` observations with reduced weight.
- Invisible characters (ZWSP, word joiner, stray soft hyphen) next to or
  inside a value → nothing. Soft hyphen between two letters is dropped.
- Case: words any case; symbols exact (`mW` ≠ `MW`, `B` is byte).
- Spaces between number and unit optional; `12March 2026` reads.

`same_value` and `compare_values`: convert within a dimension (14 days = 2
weeks, 1 GB = 1,000 MB, 12 months = 1 year; **30 days ≠ 1 month; months and
years never convert to days**); money needs same currency and same period;
versions compare as written (`2.3` ≠ `2.3.0`); dates compare at the coarser
precision only when both have that precision, otherwise not comparable
(`12 March 2026` ≠ `2026-03`); names and booleans never compare.

`format_value` must round-trip: `parse_values(format_value(v))` returns
exactly one value equal to `v` with no flags. Write that as a property test
over every value in `data/practice.csv` forms.

Tests: `tests/a/test_values.py` loads all 14 `contracts/examples/claimed_value/good`
and 19 `bad` files; good ones parse from their own canonical text, bad ones
are rejected for the stated fault. Add the "not read" catalogue from the
content map §9 as explicit negative cases.

### A2. `grammar/sentences.py` + `pages.py` (day 1)

- `split_sentences`: end at `.`, `!`, `?` followed by a space, or a blank line;
  single line break is a space; abbreviations never end a sentence (e.g., i.e.,
  vs., approx., Inc., Ltd., Co., Corp., Dr., Mr., Mrs., Ms., Prof., St., single
  initials like `J.`, `No.` before a number).
- `clauses`, `negated_before`, `NEGATION_WORDS` (not, no, never, none, nobody,
  nothing, neither, nor, without, cannot, any `n't`), `TIME_WORDS` and
  `MONTH_WORDS` exactly as the refused-words table in claim-forms.md. `May`
  counts as a month only when capitalised.
- `load_universe`: read `id,text,date` (also accept `;`-separated,
  decimal-comma CSV); page = maximal run of consecutive ids with the same
  date. Replay on practice: expect about 291 pages, 1–15 rows each.

### A3. `lexicon.py` (day 1)

- Load `{subjects:[{name, aliases, attributes}], events:[...]}`. Build a
  lowercase, whitespace-normalised alias map. `find_mentions` does
  whole-word, case- and spacing-insensitive, longest-match, non-overlapping
  matching; a name inside a longer name refers only to the longer one.
- Watch the traps listed in the content map §13: `Hooly AI` is the company
  but `Hooly AI Pro` is a plan; `Hooly's board` as alias; `outage` as alias;
  short aliases that are English words (`Search`, `Maps`, `Photos`, `Chrome`,
  `Vault`, `Jules`). For the single-word aliases, require a capital letter in
  the surface form before accepting a mention; test both directions.
- Must work on a run-time lexicon larger than practice (more subjects,
  possibly new events). Nothing hard-coded.

### A4. `validate.py` — the referee clone (day 1, second half)

`validate(claim, lexicon) -> list[str]`. Two layers:

1. Shape: implement `entry.schema.json` by hand (no jsonschema at run time):
   id pattern, type enum, text 1–300 chars with a non-space, form shape per
   type with `additionalProperties: false`, label true/false, confidence in
   [0.5, 1], no `op` inside values, subject/target/event are lexicon names,
   attribute/link exist for that subject.
2. Grammar: re-read `claim.text` and check it says what `claim.form` says,
   per `claim-forms.md`:
   - all types: one sentence holds everything the form needs; names resolve
     via `find_mentions`; no negation except yes/no claims; yes/no claims
     contain `attribute_words(attr)` (word for word; space, hyphen or nothing
     between words and between letters and digits).
   - `fact`, `at_event`, `relation`: exactly one value of the claim's kind
     (another money value with the same currency AND period is a second value;
     a yearly price next to a monthly one is not); no own date (unless the
     value is a date), no month without year, no time word — except inside
     needed names, the value, or the event phrase.
   - `compare`: left name → one op phrase → right name, in order; no number at
     all (not even `one`, `a dozen`); amount phrases only between amounts,
     date phrases only between dates; exactly one op phrase in the whole text;
     sides comparable and not the same fact.
   - `change`: subject name + one change phrase (`from A to B`, `up/down from`,
     `B, up from A`, `B, down from A`); each side in full written form;
     direction word consistent; names/booleans use plain `from … to`; a month
     word IS allowed here.
   - `at_event`: event phrase immediately before an event name (optionally
     `the`); the event is in `lexicon.events` and has a `date` attribute.
   - `relation`: link subject named, link words present (`attribute_words(link)`),
     value present; nothing else of the kind.

Tests: `tests/a/test_entries.py` loads the 7 good / 13 bad entry examples and
reproduces each verdict; `tests/a/test_claim_forms.py` turns every accepted and
refused row from the tables in claim-forms.md (and the content map §8) into a
case. Treat a false-accept as a bug of the highest severity: the referee is
stricter than you think, so when in doubt **reject**.

Also ship a CLI: `python -m arena.validate path/to/output.csv` prints the
number of rows and every invalid row with reasons, exit code 1 if any. The
integration step uses it.

### A5. `extract.py` (day 2)

`extract(pages, lexicon, attrs) -> list[Observation]`.

Per sentence: mentions, parsed values, cues. Subject resolution ladder,
stopping at the first hit:

1. a lexicon mention in the sentence (longest; if several, the one nearest
   the value, then the first)
2. a mention in the page's first row (heading/press-release lead) when the
   page has one dominant subject
3. the previous sentence's resolved subject (pronouns: he/she/it/they/the
   company/the plan/the team)
4. an event-context subject when the page is a recap of an event
   (city/attendees/talks → the event)

Attribute resolution: for each parsed value, candidate attributes are those of
the resolved subject whose `AttrSpec` kind (from B, stub it) matches the value
kind; disambiguate by keyword hints you mine from practice (`price` ↔ "costs",
"per month"; `languages` ↔ "languages"; `uptime*` ↔ "uptime"; `launched`
↔ "launched"/"launch"; `joined` ↔ "joined"/"started"). Keep the hint table in
code, data-driven from a dict, and measure it: replaying on `practice.csv`,
report precision/recall of (subject, attribute, value) against the `form`
column. Target ≥0.85 precision, ≥0.6 recall on day 2; recall matters less than
precision because the universe is 9× practice and corroboration is cheap.

Cues (`Observation.cues`): `speaker` (row starts with `Name:`), `gavin`,
`testimonial` ("replaced three tools for me", first person + product),
`boast` ("and that is before lunch", "I am not even tired"), `hearsay` ("I have
been told", "he recalls"), `announce_future` ("coming next month", "from 1
April", "starting"), `stale_marker` (page date far after the value's last
corroboration — leave this one to B; just pass the date), `table_cell`
(≤4 tokens, no verb), `headline`, `press_release` ("today launched", "City,
date"), `release_notes`.

Carry `op` values through (B down-weights them) and set `label` from the
practice CSV when replaying so B can use the same function to bake.

### A6. Nice-to-haves if time remains

- A `--explain` flag on the validate CLI that shows which rule fired.
- Property test: for 2,000 random `Value`s, `format_value` round-trips.

## Stubs you write (in `tests/a/stubs/`)

- `attrs_stub.py`: `load_attrs` returns specs derived directly from
  `data/practice.csv` forms (kind, unit, currency, per by majority vote per
  (subject, attribute)). This is close to what B ships, so your replay
  numbers will carry over.

## Do not

- Do not touch `arena/model.py`, `data/`, `arena/generate/`, `arena/render.py`.
- Do not use any third-party package inside `arena/`.
- Do not "fix" a surprising rule in value-forms.md by reading real-world
  intuition into it; the referee follows the document.

## Done means

- `tests/a` green: 14+19 value examples, 7+13 entry examples, every table row
  from claim-forms.md.
- `python -m arena.validate contracts/examples/entry/good/*.json` → 7 valid.
- `extract` replay on practice reports precision ≥0.85.
- `format_value` round-trips every value in practice forms.
