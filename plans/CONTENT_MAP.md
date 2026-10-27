# Hype Arena starter: content map

A map of everything in the starter repository: what it asks for, what it gives you, and what the data looks like. It extracts and organises. It does not propose a solution.

- **Source:** `https://github.com/QA-DNA/hype-arena-starter`, cloned into this folder at commit `82b9cc5`. Git history was not read.
- **Mapped on:** 27 Oct 2026.
- **Method:** every Markdown file, both schemas and all 53 example JSON files were read in full. `data/lexicon.json` was read in full. `data/practice.csv` was profiled with SQL (`sqlite3` with JSON functions). All figures below come from that profiling.

---

## 1. At a glance

| Item | Value |
| --- | --- |
| Challenge | QA DNA challenge, NEXXT AI Hackathon, "Hype Arena" |
| Universe | **Hooly**, a fictional company. Its products borrow real Google product names and its people borrow names from *Silicon Valley* characters, with a few letters changed |
| Ground truth | **What the universe says.** Real-world knowledge, the web or a pretrained model's knowledge will contradict it |
| What you build | A system that **generates new claims** about Hooly, each labelled `true`/`false` with a confidence from 0.5 to 1 |
| Hard constraint | LLMs may help **build** the system and make its training material, but **the system itself may not be an LLM** |
| Input at run time | `/universe/universe.csv` (`id,text,date`, unlabelled, about 90% of the universe) and `/universe/lexicon.json` |
| Output | `/output/output.csv` with columns `id,type,text,form,label,confidence` |
| Claim types | `fact`, `compare`, `change`, `at_event`, `relation` |
| Judge | A **deterministic referee** with no model in it. It parses each entry's text against its form using fixed phrase and value grammars, then looks the claim up in its fact base |
| Practice data | 1,897 labelled sentences (10% of the universe), with 2,402 structured facts |
| Lexicon | 62 subjects, 110 names and aliases, 514 subject–attribute pairs, 13 events |
| Run box | Docker `linux/amd64`, image ≤ 3 GiB, offline, 2 CPU, 6 GB RAM, ≤ 256 processes and threads, read-only root, 10 minutes |

---

## 2. Dates and deadlines

| When | What |
| --- | --- |
| 7 Oct 2025 to 28 Oct 2026 | Date range of practice rows (page dates) |
| **29 Oct 2026** | **As-of date** for `fact` and `compare` claims |
| 29 Oct 2026, 10:30 | Organisers add `sample/sample.csv`: 20 unlabelled rows (`id,text,date`) from outside the practice set |
| 29 Oct 2026, 11:00 | **Freeze.** The PR must be open (one per team, titled with the team name). A demo video is handed in showing the system running on the 20 sample rows |
| After 11:00 | A push to the PR or closing it **disqualifies** the team. Organisers build and run the system once from the commit the PR held at the freeze |

The README says to "fork this repository and work in your fork". Forks are public.

---

## 3. Repository map

```
.
├── README.md                         The universe, the task, rules, deadlines, what is here
├── contracts/
│   ├── README.md                     THE CONTRACT: input, run environment, output table, claim types
│   ├── claim-forms.md                Sentence grammar per claim type (what the referee accepts as text)
│   ├── value-forms.md                Value grammar: how each kind of value must be written in text
│   ├── entry.schema.json             JSON Schema of one output entry (draft 2020-12)
│   ├── claimed_value.schema.json     JSON Schema of a typed value (8 kinds)
│   └── examples/
│       ├── claimed_value/good/  14   Valid values
│       ├── claimed_value/bad/   19   Invalid values, one fault each
│       ├── entry/good/           7   One valid entry per type (2 for compare, 2 for fact)
│       └── entry/bad/           13   Invalid entries, one fault each
└── data/
    ├── practice.csv                  1,897 labelled rows (459 KB)
    └── lexicon.json                  Subjects, aliases, attributes, events (20 KB)
```

**Not in the repository:**
- `sample/sample.csv` (arrives 29 Oct, 10:30).
- A `Dockerfile` (you write it).
- The referee code. The docs mention `go test ./internal/referee/` and `go test ./internal/value/`, so the referee is written in Go and lives in the organisers' codebase.
- The scoring formula.

---

## 4. The task (README.md)

- The universe is "a year of Hooly's pages, docs, posts, decks and press releases, in which prices, headcounts, dates and names change, **and some pages lie**." You get it as sentences, each labelled.
- Build a system that **generates new content about Hooly: claims that connect what the universe says**, each labelled true or false, with how sure the system is. How you build it is up to you.
- LLMs may help build the system "and make what it learns from", but **the system itself may not be an LLM**.
- The universe deliberately departs from the TV series and from Google's real history.

---

## 5. Run contract (contracts/README.md)

### What you get at build time
- `practice.csv` and `lexicon.json` (this repo). **The practice data is not mounted at run time.** Anything the system needs from it must be baked into the image.

### What the run reads
- `/universe/universe.csv`: every row outside the practice set (about 90% of the universe), columns `id,text,date` only. No `label`, no `form`.
- `/universe/lexicon.json`: the universe's lexicon, "in the same shape as the practice dataset's". It can hold more subjects than the practice lexicon.

### Image and runtime limits

| Constraint | Value |
| --- | --- |
| Build | `docker build --platform linux/amd64 .` from the root `Dockerfile`. **The build has network access** |
| Image size | ≤ 3 GiB unpacked |
| User | Must not be root. **End the Dockerfile with `USER 10001`.** An image with no `USER`, or with `root` or `0`, is refused |
| Network at run time | **None** |
| CPU / RAM | 2 CPUs, 6 GB of memory |
| Processes and threads | ≤ 256 |
| Filesystem | Read-only root. `/tmp` is writable up to 128 MB and **counts against memory**. `/output` up to 256 MB |
| Time | **10 minutes.** At the deadline: `SIGTERM`, then a kill 10 s later. `ARENA_DEADLINE` env var holds the deadline in Unix seconds |
| Output | `/output/output.csv`. **Whatever is on disk when the run ends counts**, including at the deadline. No file means nothing handed in |

---

## 6. Output contract

### Columns (any order)

| Column | Rule |
| --- | --- |
| `id` | Unique in the table. `^[A-Za-z0-9_.-]+$`, 1–64 chars |
| `type` | `fact` \| `compare` \| `change` \| `at_event` \| `relation` |
| `text` | One claim sentence, 1–300 chars, must contain a non-space, written in the grammars of `claim-forms.md` and `value-forms.md` |
| `form` | JSON object, shape per type (§7) |
| `label` | `true` \| `false` (never `unsure`). The schema calls this field `tag` |
| `confidence` | Number in [0.5, 1]. 0.5 means a guess, 1 means certain |

### CSV format
- UTF-8, header row first.
- Standard quoting: a cell holding a comma, a quote or a line break must be quoted, or the row splits and is invalid.
- Excel's Romanian-locale CSV (semicolon separator, decimal comma) is also accepted.
- Each row is validated as an entry of `entry.schema.json`, with `label` mapped to `tag`.

Example from the contract:

```csv
id,type,text,form,label,confidence
e1,compare,Hooly Workspace costs more than Hooly AI Pro.,"{""left"": {""subject"": ""Hooly Workspace"", ""attribute"": ""price""}, ""right"": {""subject"": ""Hooly AI Pro"", ""attribute"": ""price""}, ""op"": ""gt""}",true,0.9
```

### Validity rules from the contract
- **Facts are named by subject and attribute as the lexicon gives them.** A name or alias in any case works. An unknown subject, or an attribute the subject lacks, makes the entry **invalid**.
- **Values are exact** and carry **no `op`**. "More than / less than" claims must be `compare` entries.
- **The text must say what the claim says**, in one sentence, in the published forms, with values written in the published value forms, and **nothing the claim could be read against instead**: no other value of the claim's kind, no date or time word of its own, and for a yes/no claim the attribute in words.

---

## 7. The five claim types

| `type` | `form` keys | True when | Date it is judged on |
| --- | --- | --- | --- |
| `fact` | `subject`, `attribute`, `value` | The fact has that value | **29 Oct 2026** |
| `compare` | `left{subject,attribute}`, `right{subject,attribute}`, `op` ∈ `gt`/`lt`/`eq` | The two values compare that way. For dates, `gt` is after and `lt` is before. On the day a value changes, it holds the new one | **29 Oct 2026** |
| `change` | `subject`, `attribute`, `from`, `to` | The fact held `from` and **later** held `to` | Any time (the as-of date plays no part) |
| `at_event` | `subject`, `attribute`, `event`, `value` | The fact had the value **on the date of the event** (the event's `date` fact) | The event's date |
| `relation` | `subject`, `link`, `target`, `attribute`, `value` | `target` is the entity the subject's `link` attribute names (at some date), and target's `attribute` had `value` **while** `link` named it | The period the link held |

All five forms have `additionalProperties: false`. `subject`, `target` and `event` are name strings (1–120 chars). `attribute` and `link` match `^[a-z][a-z0-9_]*$`.

---

## 8. Text grammar: claim-forms.md

The referee resolves the form's facts first, then checks that the text says what the form says. If it doesn't, the entry is **invalid**.

### General rules (all types)
- **Names.** Use a lexicon name or alias as whole words, in any case and spacing. **A name inside a longer name refers only to the longer one**: `Hooly AI Pro` names the plan, never the company `Hooly`.
- **Sentences.** A sentence ends at `.`, `!` or `?` followed by a space, or at a blank line. Everything a form needs must sit in **one sentence**. Other sentences in the text may say anything; for most types they are not read.
- **Values.** Written exactly as `value-forms.md` writes them. No comparison words (`over`, `at least`), no approximations. A value inside a name the form needs doesn't count: the `2026` in `Hooly I/O 2026` states no year.
- **One value, one date** (`fact`, `at_event`, `relation`). The sentence holds only the claim's value and **no other value of the same kind**: no other price in the same currency and period, no other count of the same noun, no amount in convertible units, no other percentage, version or date, and for a name no other entity of the same type. It holds **no date of its own** unless the value is that date, **no month without a year, and no time word** (list below), except inside the names the form needs, the value and the event phrase.
- **Negations.** A sentence holding a form may not contain a negation (`not`, `no`, `never`, `none`, `nobody`, `nothing`, `neither`, `nor`, `without`, `cannot`, any word ending in `n't`). **The exception is yes/no claims**, which state "no" by their negation.
- **Yes/no claims** must also contain the **attribute in words**: word for word, any case, with a space, hyphen or nothing between words and between letters and digits. `soc2_certified` reads as `SOC 2 certified`; `had_major_outage` reads as `had major outage`.
- **Gaps.** `…` in a phrase stands for up to 3 words of your own: `more … than` matches `more than`, `more languages than` and `more paying customers than`.

### Words refused in compare sentences (and as "own date" or time words in fact, at_event and relation sentences)

| Refused | Words |
| --- | --- |
| Dates without a year | January … December, spring, summer, autumn, winter, Monday … Sunday (`may` counts as the month only when written `May`) |
| Time words | ago, yesterday, tomorrow, once, formerly, previously, originally, initially, recently, lately, soon, eventually, then, before, after, since, until, till, earlier, later, used to, last/next week, last/next month, last/next quarter, last/next year, in the past, in the future, at the time, at that time |

### `fact`
One sentence, in any order: a name of the subject plus the value. Nothing else of the value's kind and no date.

| Text (Hooly AI Pro price = €59 per month) | Accepted? |
| --- | --- |
| `Hooly AI Pro costs €59 per month.` | yes |
| `At €59 per month, Hooly AI Pro is our best seller.` | yes |
| `Hooly AI Pro costs €59 per month or €590 per year.` | yes (a yearly price is another kind) |
| `Hooly AI Pro costs over €59 per month.` | no (`over` makes it another value) |
| `… about €59 …` / `… €59.` (no period) / `It costs …` / value in another sentence | no |
| `Hooly costs €59 per month.` | no (`Hooly` is the company) |
| `…, and never more.` | no (negation) |
| `…, up from €49 per month.` | no (another monthly price) |
| `In March 2026, …` / `In April, …` / `used to cost …` | no (own date, month, time word) |

Yes/no example (Hooly `soc2_certified` = no): `Hooly is not SOC 2 certified.` ✔, `Hooly has never been SOC2-certified.` ✔, `Hooly is fully SOC 2 certified.` ✘ (states yes), `Hooly has never passed a SOC 2 audit.` ✘ (wrong attribute words), `Hooly is not profitable.` ✘ (other attribute).

### `compare`
One sentence: **left subject name → one op phrase → right subject name**, in that order. **No value and no number at all** (not `100`, not `four`, not `a dozen`, not even `one`), no date, no time word other than the phrase's own words. Only one op phrase in the whole text. Values, dates or time words inside a compared subject's name don't count. Other sentences are not read for these.

The two facts must be **comparable**: the same kind, convertible units, prices in the same currency **and** period. **Names and yes/no values never compare**, and neither does a fact with itself. Date phrases work only between dates, amount phrases only between amounts (counts, prices, percentages, durations, versions). The same subject may appear on both sides, for two different attributes.

| Between | `gt` | `lt` | `eq` |
| --- | --- | --- | --- |
| amounts | `more … than`, `higher … than`, `greater … than`, `larger … than`, `bigger … than`, `longer … than` | `less … than`, `fewer … than`, `lower … than`, `smaller … than`, `shorter … than`, `cheaper … than` | `the same … as`, `as much … as`, `as many … as`, `as long as`, `as high as`, `equal to` |
| dates | `after`, `later than` | `before`, `earlier than` | `on the same day as`, `the same day as` |

Accepted: `Hooly Workspace is more expensive than Hooly AI Pro.` (`more … than` with a gap), `The Workspace plan costs a higher monthly price than Hooly AI Pro.` (alias), `Hooly Workspace costs more per month than Hooly AI Pro.`, `… than Hooly AI Pro. We checked in June 2026.` (the date sits in another sentence), `Hooly I/O 2026 took place before the May 2026 outage.` (the year and month are inside names).
Refused: wrong op phrase, subjects swapped, right subject not named (`its rivals`), `outprices`, negation, two op phrases, left subject in another sentence, `Hooly` for a plan, date phrase between prices, `€100 more`, `100 more`, `a hundred more`, `In June 2026, …`, `used to`, `before the outage` (between amounts), `more than` between dates, `two weeks before`, `…, in March 2026`.

### `change`
One sentence: subject name plus one change phrase. The as-of date plays no part.

| Phrase | Reads |
| --- | --- |
| `from` *A* `to` *B* | went from A to B. `up` or `down` right before `from` states the direction |
| *B*`, up from` *A* | rose from A to B |
| *B*`, down from` *A* | fell from A to B |

- Each side must carry its **full written form**. `from €49 to €59 per month` gives €49 no period, so it is **invalid**.
- `up` requires `to` > `from`, and `down` requires `to` < `from`. Names and yes/no values have no order, so use plain `from … to` for them. Yes/no values also need the attribute words.
- Accepted: `Hooly AI Pro went from €49 per month to €59 per month.`, `The price of Hooly AI Pro rose from €49 per month to €59 per month in April.` (a month is allowed here), `Hooly AI Pro costs €59 per month, up from €49 per month.`, `… went up from €49 per month to €59 per month.`
- Refused: wrong direction word, values swapped, missing period on one side, `cost €49 … and now costs €59` (no change phrase), negation.

### `at_event`
One sentence, in any order: subject name, an **event phrase right before the event name** (with or without `the`), and the value. No other value of the kind and no date of its own: the event gives the date. The time words inside an event phrase (`at the time of`) belong to the phrase and are allowed.

Event phrases: **`at`, `during`, `on the day of`, `at the time of`**.

Accepted: `Hooly Gemini spoke 12 languages at Hooly I/O 2026.`, `At Hooly I/O, Hooly Gemini spoke a dozen languages.` (alias, number in words), `… on the day of Hooly I/O 2026.`, `… at the time of Hooly I/O 2026.`
Refused: `before Hooly I/O 2026` (not an event phrase), `in March` (event not named), `Hooly spoke …` (wrong subject), `…, up from 6 languages.` (another count), `In March 2026, at Hooly I/O 2026, …` (own date).

### `relation`
One sentence, in any order: **a name of the link's subject**, **the link's relation words** and the value. No other value or date. The as-of date plays no part.

- The relation words are the `link` attribute read word for word (any case, space, hyphen or nothing): `cto` → `CTO`, `head_of_product` → `head of product`, `series_a_lead` → `Series A lead`.
- Relation words listed for the practice pages: `CEO`, `CTO`, `headquarters`, `Series A lead`, `head of product`, `primary region`, `cloud provider`, `lead` (of a product) and `city` (of an event).
- Accepted: `The CTO of Hooly joined on 1 July 2026.`, `Hooly's CTO started on 2026-07-01.`
- Refused: `chief technology officer` (not the relation words), `Bertram Gilfoil joined Hooly on …` (no relation words), `The CTO joined …` (link subject not named), `…, who left on 3 May 2027, …` (another date), `…, after Richard Hendrix.` (time word).

---

## 9. Value grammar: value-forms.md

"The referee is deterministic: no model decides whether a claim is true." A value written any other way doesn't count, and the entry is invalid.

### General rules
- **A value is read whole, where it stands**, with its comparison words and unit, and only from whole numbers: `99.6%` never states `6%`.
- **Case.** Words match in any case. Case-sensitive symbols must be exact: `m` is a metre and `M` is a million, `mW` ≠ `MW`, and `B` is a byte.
- **Spaces.** The space between number and unit is optional (`128GB`, `14days`), as is the one before a date's month (`12March 2026`).
- **The value's sentence must name the fact's subject** (lexicon name or alias). Neighbouring sentences lend nothing.
  - Sentence ends: `.`, `!` or `?` followed by a space, or a blank line. A single line break is a space.
  - Abbreviations do not end a sentence: `e.g.`, `i.e.`, `vs.`, `approx.`, `Inc.`, `Ltd.`, `Co.`, `Corp.`, `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `Prof.`, `St.`, initials such as `J.`, and `No.` before a number.
- **Numbers.**
  - Decimal point, with commas between thousands: `10,000`, `1.5`, `1,234.5`. **Only prices** may use a decimal comma (`€49,99`).
  - **Ambiguous numbers read as nothing**: `99,9`, `1,5`, `1.000.000`, `1.500` (three digits after the only point). The exception is percentages, which may have three decimals (`99.999%`).
  - Number words: `zero` … `ninety-nine`, `a hundred`, `three hundred`, `a dozen`.
  - Scales: `thousand`, `million`/`M`, `billion`/`bn`, `k`.
- **Unit conversion.** Units of one dimension compare after conversion (`14 days` = 2 weeks, `1 GB` = 1,000 MB). **Months and years do not convert to days.**
- **Unit spellings** are interchangeable: GB = gb = gigabyte. Counted nouns match singular or plural.
- **Invisible characters** (zero-width space, word joiner, a soft hyphen that isn't inside a word) next to or inside a value make it read as nothing. A soft hyphen between two letters is dropped.

### Values that read as nothing
- **After a negation in the same clause.** Clauses end at `. , ; : ! ? • · |` or a blank line. A negation *after* the value doesn't affect it. `no more than` is a comparison, not a negation.
- **Approximations.** Before the value: about, around, approximately, approx, roughly, nearly, almost, circa, ca, some, estimated, est, close to, more or less, `~`, `≈`, `±`. After it: or so, give or take, `-ish`.
- **Range ends.** `10-20 GB`, `10–20 GB`, `10 to 20 GB`, `10 GB to 20 GB`, `€49–€59`, `1 or 2 days`, `between 10 and 20 GB`. However, `X or Y` with **different kinds** is a choice, and both read (`€49 a month or €490 a year`).

### Kinds (claimed_value.schema.json)

| Kind | Required JSON | Written forms (examples) | Notes |
| --- | --- | --- | --- |
| `quantity` | `value` (number), `unit` | `128 GB`, `128GB`, `2 terabytes`, `a 5,000 mAh battery`, `1.2 kg`, `6.1"`, `6.1-inch`, `3.2 GHz`, `65-watt`, `100 m`; counted nouns: `40 languages`, `forty languages`, `1.2 million users`, `1M tests`, `10k steps`, `a dozen partners`, `12 people` (unit `person`), `zero outages` | Physical units: data B/KB/MB/GB/TB (powers of 1,000), length mm/cm/m/km/in (`"`, `″`), mass g/kg, battery mAh, frequency Hz/kHz/MHz/GHz, power mW/W/kW. **Any other word after a number is a counted noun**, stored singular, with up to 2 words between number and noun. **A bare 4-digit number from 1900 to 2099 is a year**, so write `2,048 customers`. A unit may not be a duration unit |
| `money` | `value` ≥ 0, `currency` (`^[A-Z]{3}$`), optional `per` ∈ day/week/month/year | `€49 a month`, `€49/mo`, `49 euros per month`, `EUR 49 monthly`, `€49,99 a month`, `€10 per user per month`, `from €39/month`, `£9 a week`, `€490 per annum`, `$299.99`, `US$12`, `a €12M seed round`, `€1.2bn`, `1,999 lei` | Symbols € $ £ US$; ISO codes EUR USD GBP CHF RON PLN CZK HUF SEK NOK DKK JPY CNY INR CAD AUD; words euro/dollar/lei. Periods: `/month`, `/mo`, `a month`, `per month`, `monthly` (and the same for day/week/year), `/yr`, `per annum`, `annually`; `per user` or `/seat` may come before. **No period means one-off; monthly and one-off never match each other.** `from €39` = €39 (eq). `5 pounds` is not read (could be weight) |
| `percent` | `value` | `99.99% uptime`, `99.9 % uptime`, `50 percent`, `50 per cent`, `fifty percent`, `99.999%` | |
| `date` | `value` matching `YYYY`, `YYYY-MM` or `YYYY-MM-DD` | `2026-03-12`, `2026-03`, `12 March 2026`, `12th March 2026`, `the 12th of March 2026`, `12March 2026`, `March 12, 2026`, `Mar 12th 2026`, `1 Mar. 2026`, `March 2026`, `Sept 2026`, `in 2025` | **A year is required.** Precision is kept as written: `12 March 2026` ≠ `2026-03`. Month abbreviations Jan … Dec, Sept, with an optional dot. Not read: `12/03/2026`, `12.03.2026`, `March 12`, `Q4 2026` |
| `version` | `value` matching `^[0-9]+(\.[0-9]+){0,3}$` (no `v`) | `v2.3`, `version 2.3`, `ver. 2.3`, `v3`, `2.3.1`, `Hooly Gemini 2.2` | Three written forms: after `v`/`version`; a number with ≥ 2 dots; or **one decimal point right after a capitalised name** (the name must be written with it). **Compared as written**: `2.3` ≠ `2.3.0`. `Hooly Gemini 11` is not read; write `v11` |
| `duration` | `value` ≥ 0, `unit` ∈ ms, s, min, h, day, week, month, year | `14 days`, `a 14-day trial`, `14days`, `two weeks`, `a two-week trial`, `for a fortnight` (= 2 weeks), `24 hours`, `24h`, `30 min`, `1.8 s`, `500 ms`, `12 months` (= 1 year), `for a week` | Unit kept as written, converted when compared. Aliases: sec/second, minute, hr/hour, `d`, wk, mo/mth, yr, decade = 10 years. Single-letter units in lower case. **`a`/`an` counts as 1 only after** under, within, in, for, over, than, at least, at most, to, only, just, about, around; elsewhere it's a rate (`1,000 requests a day` states no duration). `half an hour` is not read. **30 days ≠ 1 month** |
| `name` | `value` (1–200 chars) | `founded by Gavin Bellson`, `GAVIN BELLSON`, `GavinBellson` | Whole words, any case, spaces optional. Resolved through every lexicon name and alias. Not read after a negation |
| `boolean` | `value` true/false | `Hooly passed its SOC 2 audit` (true), `Hooly has never had an outage` (false), `The app isn't SOC 2 certified` (false) | A passage states **no** if it, or the rest of its clause, contains a negation word (§8). Anything else states yes |

### Comparison words (`op`): dataset forms only, never in entries

| op | Words |
| --- | --- |
| `gt` | over, more than, greater than, higher than, above, exceeding, in excess of, upwards of |
| `lt` | under, less than, fewer than, lower than, below |
| `le` | up to, at most, no more than, not more than, maximum, max; `within` (durations); after the value: or less, or fewer, or under, or below, or lower, or shorter |
| `ge` | at least, no less than, not less than, no fewer than, minimum; `+` right after the number; after the value: or more, or higher, or above, or longer, or over |
| dates | before and prior to → `lt`; after → `gt`; by and no later than → `le`; no earlier than → `ge` |
| eq | only, just, from, starting at (value kept as stated) |

### The "Not read" catalogue (all invalid as written)
`12/03/2026`, `12.03.2026`, `March 12` (no year), `Q4 2026`, `12 March 2026` read as month precision, `1.000.000 users`, `1,5 GB` (neither 1.5 nor 5), `99,9%`, `1.500 mAh`, `99.6%` read as 6%, negated values, approximations (`about`, `~`, `or so`), range ends, `10m users` (metres; write `10M`), `2026 customers` (a year), `half an hour`, `1,000 requests a day` as a duration, `€49 a month` read as one-off, `5 pounds`, `Hooly Gemini 11`, `v2.3` read as `2.3.0`, `30 days` read as 1 month, `over 10,000` read as exactly 10,000, and more than 2 words between a number and its noun.

---

## 10. Schemas

### `entry.schema.json` (`$id` `https://qadna.co/hype-arena/schemas/v1/entry.schema.json`)
- Required: `id`, `type`, `text`, `form`, `tag`, `confidence`. **`additionalProperties: false`**, so an extra `label` key in the JSON entry is invalid (the CSV column `label` *is* the tag).
- `type` selects the `form` shape through `allOf`/`if-then`.
- Entry values use `claimed_value.schema.json` **with `op` forbidden** (`not: {required: [op]}`).
- `ref` = `{subject, attribute}`, used by compare.

### `claimed_value.schema.json`
- `kind` ∈ quantity, money, percent, date, version, duration, name, boolean. Each kind has `additionalProperties: false`.
- Shared definitions:
  - `op` ∈ eq, lt, le, gt, ge.
  - `unit`: `^[A-Za-z][A-Za-z0-9_]*$`, ≤ 40 chars, **not** a duration unit.
  - `currency`: `^[A-Z]{3}$`.
  - `period` ∈ day, week, month, year.
  - `partial_date`: `^[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$`.
- The `op` field exists because **dataset forms may carry it**. Entries may not.

---

## 11. Example catalogue (contracts/examples)

### `claimed_value/good` (14)
`boolean` `{true}` · `date-day` `2026-03-12` · `date-month-before` `2026-03` with `op:lt` · `date-year` `2025` · `duration-under-a-second` `1 s` with `op:lt` · `duration-weeks` `2 week` · `money-monthly` `49 EUR/month` · `money-one-off-under` `299.99 USD` with `op:lt` · `name` `Gavin Bellson` · `percent` `99.99` · `quantity-count` `40 language` · `quantity-over` `10000 customer` with `op:gt` · `quantity-physical` `128 GB` · `version` `"2.3"`

### `claimed_value/bad` (19), one fault each
| File | Fault |
| --- | --- |
| boolean-as-string | `"yes"` instead of `true` |
| date-free-text | `"12 March 2026"` instead of ISO |
| date-month-13 | month 13 |
| date-with-time | has a time component |
| duration-negative | value −1 |
| duration-plural-unit | `days` (must be `day`) |
| extra-field | `confidence` inside a value |
| missing-kind | no `kind` |
| money-lowercase-currency | `eur` |
| money-negative | −5 |
| money-unknown-period | `quarter` |
| name-blank | whitespace-only name |
| name-with-op | names take no `op` |
| quantity-missing-unit | no unit |
| quantity-value-as-string | `"40"` |
| quantity-with-time-unit | unit `h` (durations are their own kind) |
| unknown-kind | `rating` |
| unknown-op | `about` |
| version-with-v | `"v2.3"` |

### `entry/good` (7)
| File | Type | Text | Form highlights |
| --- | --- | --- | --- |
| fact.json | fact | `Hooly AI Pro costs €59 per month.` | price = 59 EUR/month |
| fact-name.json | fact | `Bertram Gilfoil is the CTO of Hooly.` | Hooly.cto = name Bertram Gilfoil |
| compare.json | compare | `Hooly Workspace costs more than Hooly AI Pro.` | price vs price, `gt` |
| compare-dates.json | compare | `Hooly I/O 2026 took place before the May 2026 outage.` | date vs date, `lt`; id `summit-before-outage` |
| change.json | change | `Hooly AI Pro went from €49 per month to €59 per month.` | from 49 → to 59 EUR/month |
| at_event.json | at_event | `Hooly Gemini spoke 12 languages at Hooly I/O 2026.` | event `Hooly I/O 2026`, 12 language |
| relation.json | relation | `The CTO of Hooly joined on 1 July 2026.` | Hooly →cto→ Bertram Gilfoil .joined = 2026-07-01 |

All good examples use `tag: "true"`, `confidence: 0.9`.

### `entry/bad` (13)
| File | Fault |
| --- | --- |
| at-event-with-citation | `event` given as `{doc, quote}` instead of a name |
| change-without-to | missing `to` |
| fact-as-graph-id | compare sides given as `"team.price"` strings |
| fact-in-compare-shape | `type: fact` with a compare-shaped form |
| fact-with-citation | form uses `{fact:{doc,quote}}` instead of subject/attribute |
| fact-with-op | value with `op: gt` ("over €50") |
| missing-text | no `text` |
| op-ge | compare `op: ge` (only gt/lt/eq allowed) |
| rank | `type: rank` doesn't exist ("cheapest plan") |
| relation-without-link | no `link` |
| tag-unsure | `tag: unsure` (only true/false) |
| with-label | extra `label` key |
| without-confidence | no confidence |

The bad examples hint at the universe's original page structure: `web/summit.html`, `web/pricing-2026-04.html` and a quote. They also hint at internal graph ids such as `team.price` and `pro.price`.

---

## 12. Data: `data/practice.csv`

### Shape
- Header: `id,text,date,label,form`. **1,897 rows**, ids `p-1` … `p-1897` (unique, contiguous).
- `text`: one sentence (7–196 chars, mean 53). It can be prose, a headline, a slide bullet, a table cell (`€1,799.`, `Warsaw.`, `Audited: yes`) or a transcript line (`Gavin: …`).
- `date`: the date of the page the sentence came from. 159 distinct dates, from 2025-10-07 to 2026-10-28.
- `form`: a JSON **array** of facts `{subject, attribute, value}`. Values may carry `op`. Every row has at least one fact.
- **Ids are not in date order.** The date goes backwards 128 times in id order. Runs of consecutive ids with the same date look like pages: about **291 runs**, 1–15 sentences each, 6.5 on average.

### Labels (row level)

| Label | Rows | Share |
| --- | --- | --- |
| true | 1,581 | 83.3% |
| false | 277 | 14.6% |
| unsure | 39 | 2.1% |

Definitions (contract): **false** if the sentence states **at least one** false value; **unsure** when the dataset gives no means to tell; **true** otherwise. "True" means true **on its date**.

**The label belongs to the row, not to each fact.** In a multi-fact false row, some facts can be true. Example: `p-1347` "Hooly was founded on 1 June 2024, and its CEO is Gavin Bellson." is false, yet its CEO fact is true elsewhere.

### Facts per row

| Facts | Rows | false | unsure |
| --- | --- | --- | --- |
| 1 | 1,467 | 202 | 35 |
| 2 | 373 | 68 | 3 |
| 3 | 45 | 6 | 1 |
| 4 | 9 | 1 | 0 |
| 5 | 2 | 0 | 0 |
| 8 | 1 | 0 | 0 |

Total: **2,402 facts**.

### Facts by value kind × row label

| Kind | Facts | in true rows | in false rows | in unsure rows |
| --- | --- | --- | --- | --- |
| quantity | 1,028 | 826 | 178 | 24 |
| money | 268 | 223 | 42 | 3 |
| duration | 229 | 195 | 32 | 2 |
| name | 209 | 184 | 23 | 2 |
| percent | 201 | 169 | 29 | 3 |
| boolean | 174 | 139 | 28 | 7 |
| date | 165 | 144 | 19 | 2 |
| version | 128 | 118 | 9 | 1 |

### Value details seen in practice forms
- **`op` in forms:** 38 facts (le 25, gt 8, lt 4, ge 1) in 28 true and 10 false rows. Example: `p-7` "over 100 customers" → `{value:100, op:gt}`, labelled true.
- **Money:** **all EUR.** 147 monthly, 110 one-off, 11 yearly. No other currencies in practice.
- **Duration units:** day 105, s 36, h 35, min 28, ms 15, week 10. No month or year durations in practice.
- **Date precision:** 152 day, 11 month, 2 year.
- **Booleans:** 97 true values, 77 false values.
- **Versions:** `0.9`, `1`, `1.0`, `1.1`, `1.2`, `1.4`, `1.5`, `2`, `2.0`, `2.1`, `2.2`, `2.3`, `3`, `5.1`, `5.4`, `6.0`, `11.0`, `11.4`, `12.0`, `12.2`, `15.0`, `16.0`, `16.1`, `17.0`, `17.1`, `64.0`, `68.0`–`72.0`.
- **Quantity units (95 distinct):** top ones are language 78, GB 73, user 61, employee 50, seat 45, customer 45, star 31, token 28, MB 27, region 24, country 21, TB 19. Physical units seen: GB, MB, TB, mAh, `inch` (15, spelled `inch` in the forms, not `in`), g, km, W, Hz, m. Some counted nouns are unusual: `star` (ratings), `fold` (hinge), `megapixel`, `sitting`, `tonne`, `colour`.

### Rows per month

| Month | Rows | false | unsure |
| --- | --- | --- | --- |
| 2025-10 | 61 | 9 | 1 |
| 2025-11 | 93 | 11 | 2 |
| 2025-12 | 103 | 15 | 12 |
| 2026-01 | 111 | 10 | 1 |
| 2026-02 | 114 | 13 | 1 |
| 2026-03 | 146 | 24 | 3 |
| 2026-04 | 253 | 34 | 6 |
| 2026-05 | 112 | 17 | 0 |
| 2026-06 | 160 | 37 | 3 |
| 2026-07 | 126 | 11 | 2 |
| 2026-08 | 119 | 10 | 3 |
| 2026-09 | 218 | 41 | 3 |
| 2026-10 | 281 | 45 | 2 |

Busiest dates: 2026-04-28 (52 rows: Made by Hooly 2026), 2026-04-01 (37: price change day), 2026-10-06, 2026-07-02, 2026-10-20, 2026-09-01, 2026-02-10 …

### Subject reference in text
- **At least 754 of the 2,402 facts (31%)** have a subject whose name or alias **does not appear in the sentence**. The count uses substring matching, which overcounts matches (`Hooly` is inside `Hooly AI Pro`), so the real number is higher.
- In these rows the subject comes from page context: pronouns (`He begins with a small crew of 4 engineers` → Holdan), headings, the previous sentence, or event context (`2,600 attendees made the trip to Dublin` → Hooly Cloud Next 2026).
- Some sentences hold their fact only through context: `p-1683` "Warsaw." → Hooly Cloud.newest_region.

### Transcript / speaker rows
133 rows start with `Speaker:` (Gavin 31, Bertram 20, Recruiter 11, Hoovar 10, Dinesh 9, Ron 6, Host 4, …). 22 of them are false. Rows mentioning **Gavin**: 56, of which 14 are false (25%, against 14.6% overall).

### Text genres seen (from sampling page openings)
Press releases ("Hooly today launched …", "Berlin, 17 February 2026"), product and pricing pages, release notes ("Hooly Photos 5.4 release notes"), slide decks and benchmark bullets ("Hooly Gemini 2.0 benchmark", "SOC 2 Type II certified"), spec tables ("Hooly Drive largest file: 50 GB"), customer testimonials ("Hooly Jules at €19 a month replaced three tools for me."), interviews and podcasts (`Host:`, `Gavin:`), staff announcements ("We welcome Tarra …"), investor results, sustainability report fragments, and boastful or ironic posts ("Hooly Search now holds 301,000,000,000 pages, and that is before lunch.").

### What `unsure` looks like (all 39 inspected)
- **Claims stated once with nothing to corroborate them:** `Hooly Pixel Fold hinge rated for 200,000 folds`, `Pixel Watch counts 15 sensors`, `Pixel 10 Pro main camera captures 50 megapixels`.
- **Boastful or unreliable first-person voices:** `Revenue was €68 million and I am not even tired.`, `Hooly Translate scores 99.5% on accuracy, and the missing percent is poetry.`, `The bounty reaches €50,000 and I asked for it to be higher.`
- **Hearsay:** `He recalls that the hall seats 3,200 seats.`, `…, I have been told.`
- **Self-contradicting:** `Hooly Android 17 beta starts today, 3 September 2025` on a 2026-04-28 page.

### What `false` looks like (sampled)
- **Stale values on later pages:** `p-1353` and `p-1511` (2026-10-26) say AI Pro costs €49 per month after it moved to €59 on 2026-04-01.
- **Inflated marketing figures:** Gemini "speaks 40 languages" or "30 languages" when it speaks 12; "0% hallucination rate"; "answers in under a second".
- **Early announcements of later facts:** "Gemini speaks 12 languages" on 2025-12-10, before the 2026-03-24 launch of 2.0.
- **Wrong attributions:** `Bertram: Hooly's head of security is Bertram Gilfoil.`
- **Wrong numbers in event recaps:** `The programme packed 40 sessions …`, `120 speakers shared the stage …`
- **Internal contradiction in one sentence:** `p-808` "€59 per month, or €590 per month if you let the yearly plan renew."
- **2026-10-26 pages repeat many outdated claims** (Berlin HQ, €49 AI Pro price, Series A of €25 million, founded 1 June 2024).

### How often values change (subject–attribute pairs, counting distinct values seen in practice, true and false)

| Distinct values | Pairs |
| --- | --- |
| 1 | 185 |
| 2 | 214 |
| 3 | 76 |
| 4 | 29 |
| 5 | 7 |
| 6 | 3 |

The pairs with the most distinct values: Hooly Gemini.uptime_last_quarter (6), Hooly Chrome.stable_version (6), Hooly Chrome.stable_release_date (6), Hooly Gemini.version (5, from 49 facts), Hooly.paying_customers (5), Hooly Android.version (5), Hooly Search.share_of_ad_revenue (5), Hooly Photos.monthly_active_users (5), Hooly Cloud Next 2026.registrations (5), Hooly Meet.max_participants (5).

---

## 13. Data: `data/lexicon.json`

Shape: `{ "subjects": [ {name, aliases[], attributes[]} … ], "events": [name …] }`.

- 62 subjects, 48 aliases (110 names in total), 514 subject–attribute pairs.
- **Every one of the 514 pairs appears in a practice form, and no form uses a pair outside the lexicon.**
- Attributes are snake_case. The lexicon gives **no value kind or unit** per attribute; those can only be learned from the forms.
- Alias traps: `Hooly` has the aliases `Hooly AI` and `Hooly Inc.`, so "Hooly AI" (the company) sits beside "Hooly AI Pro" and "Hooly AI Free" (plans). `Hooly Devices` has both `Devices division` and `devices division`. `The May 2026 outage` has the alias `outage`. Short aliases (`Search`, `Maps`, `Photos`, `Chrome`, `Android`, `Gemini`, `Translate`, `Vault`, `Jules`) are also common English words.

### All subjects

| Subject | Aliases | Facts in practice | Attributes |
| --- | --- | --- | --- |
| Bertram Gilfoil |  | 4 | `joined`, `previous_employer` |
| Brightline Labs | Brightline | 4 | `integration_partner_of_flawless` |
| Dinesh Chugtay |  | 2 | `joined` |
| Erlich Bachmann |  | 1 | `joined` |
| Gemini Launch Night | Launch Night | 5 | `attendees`, `city`, `date` |
| Holdan |  | 11 | `joined`, `previous_employer`, `team_size` |
| Hooly | Hooly AI, Hooly Inc. | 181 | `annual_recurring_revenue`, `ceo`, `cto`, `customer_countries`, `customers_in_the_eu`, `data_processing_agreement`, `employees`, `founded`, `founders`, `fully_remote`, `had_major_outage`, `head_of_product`, `head_of_security`, `head_of_workspace`, `headquarters`, `help_guides`, `incidents_this_year`, `net_promoter_score`, `newsletter_subscribers`, `offices`, `paying_customers`, `raised_series_a`, `raised_series_b`, `series_a_amount`, `series_a_co_investor`, `series_a_lead`, `soc2_audit_start`, `soc2_auditor`, `soc2_certified`, `support_satisfaction`, `support_tickets_per_week`, `webinars_held` |
| Hooly AI Free |  | 23 | `daily_requests`, `history_retention`, `max_upload_size`, `price` |
| Hooly AI Pro |  | 109 | `annual_price`, `free_trial`, `history_retention`, `included_seats`, `price`, `refund_window`, `saved_projects`, `signed_in_devices`, `support_first_response` |
| Hooly Android | Android | 34 | `active_devices`, `lead`, `open_source`, `version` |
| Hooly Android 16 | Android 16 | 24 | `desktop_mode`, `released`, `share_of_devices`, `supported_models`, `update_size` |
| Hooly Android 17 | Android 17 | 30 | `beta_opened`, `beta_testers`, `on_device_gemini`, `satellite_messaging`, `share_of_devices`, `stable_release`, `supported_models`, `update_size` |
| Hooly Berlin Office | Berlin Office | 26 | `bike_racks`, `desks`, `is_engineering_hub`, `is_headquarters`, `lease_end`, `opened`, `rent`, `staff` |
| Hooly Board | Hooly's board | 44 | `attendance`, `audit_committee`, `chair`, `chair_since`, `independent_members`, `meetings_per_year`, `next_meeting`, `raviqa_seat`, `seats`, `sessions_held` |
| Hooly Calendar |  | 12 | `active_users`, `appointment_booking`, `launched`, `max_guests`, `version` |
| Hooly Chrome | Chrome | 81 | `ai_sidebar`, `browser_market_share`, `cold_start_time`, `extensions_in_store`, `launched`, `lead`, `memory_saver`, `monthly_active_users`, `passkey_sync`, `release_cadence`, `stable_release_date`, `stable_version`, `tab_sleep_delay`, `top_bug_bounty` |
| Hooly Cloud |  | 145 | `archive_storage_price`, `availability_zones`, `carbon_neutral`, `cli_version`, `cool_storage_price`, `customers`, `data_centres`, `free_credit`, `free_egress_per_month`, `free_trial`, `home_region`, `launched`, `median_time_to_recover`, `newest_region`, `region_outside_europe`, `regions`, `reliability_lead`, `services`, `standard_storage_price`, `storage_tiers`, `uptime_last_quarter`, `uptime_sla` |
| Hooly Cloud Next 2026 | Hooly Cloud Next, Cloud Next | 59 | `attendees`, `city`, `date`, `length`, `opening_keynote`, `registrations`, `sessions`, `speakers`, `sponsors`, `ticket_price`, `venue` |
| Hooly Devices | Devices division, devices division | 66 | `countries_served`, `founded`, `german_premium_phone_share`, `head`, `manufacturing_partner`, `max_trade_in_credit`, `repair_centres`, `staff`, `trade_in_programme` |
| Hooly Docs |  | 34 | `active_users`, `languages`, `launched`, `offline_editing`, `simultaneous_editors`, `templates`, `version` |
| Hooly Drive |  | 19 | `active_users`, `free_storage`, `launched`, `max_file_size`, `price_per_user`, `version_history` |
| Hooly Employee Survey | Employee Survey | 33 | `anonymous`, `growth_opportunities`, `manageable_workload`, `manager_rating`, `next_round`, `open_for`, `respondents`, `response_rate`, `run_by`, `would_recommend` |
| Hooly Gemini | Gemini | 307 | `api_version`, `cloud_provider`, `concurrent_chats`, `context_window`, `data_retention`, `encryption_at_rest`, `eu_hosted`, `flawbench_score`, `hallucination_rate`, `hosting_regions`, `image_input`, `integrations`, `languages`, `launched`, `max_output_length`, `max_upload_size`, `median_response_time`, `official_sdks`, `open_source`, `p99_response_time`, `primary_region`, `requests_per_day`, `requests_per_minute`, `single_sign_on`, `supported_file_types`, `training_data_cutoff`, `uptime_last_quarter`, `version`, `voice_mode`, `webhook_events` |
| Hooly Gmail | Gmail | 35 | `active_users`, `attachment_limit`, `end_to_end_encryption`, `launched`, `mailbox_storage`, `price_per_user`, `spam_catch_rate` |
| Hooly Hiring Programme | Hooly Hiring | 69 | `applicants`, `cost_per_hire`, `executive_sponsor`, `first_reply`, `hires`, `interview_rounds`, `launched`, `offer_acceptance`, `offers`, `open_engineering_roles`, `open_roles`, `recruiters`, `referral_bonus`, `referral_share`, `time_to_hire` |
| Hooly I/O 2026 | Hooly I/O | 39 | `attendees`, `city`, `date`, `keynote_length`, `length`, `livestream_viewers`, `sponsors`, `talks`, `ticket_price`, `workshops` |
| Hooly I/O 2027 | next I/O, I/O 2027 | 3 | `city`, `date` |
| Hooly Jules | Jules | 97 | `annual_price`, `beta_date`, `beta_testers`, `context_files`, `free_trial`, `general_availability_date`, `lead`, `price`, `programming_languages`, `suggestion_acceptance_rate`, `supported_ides`, `users`, `version` |
| Hooly Lisbon Office | Lisbon Office | 19 | `announced`, `bike_racks`, `desks`, `lease_end`, `opened`, `rent`, `staff` |
| Hooly Maps | Maps | 66 | `ar_walking`, `business_listings`, `charging_stations_listed`, `countries_covered`, `latest_release_date`, `launched`, `lead`, `mapped_distance`, `monthly_active_users`, `offline_area_limit`, `offline_maps`, `places_listed`, `share_of_ad_revenue`, `store_rating`, `version`, `voice_guidance_languages` |
| Hooly Maps Day | Maps Day | 24 | `announced`, `attendees`, `city`, `date`, `features_launched`, `host`, `keynote_length`, `keynote_speaker`, `replay_available`, `sponsors`, `stream_viewers`, `talks`, `ticket_price`, `venue` |
| Hooly Meet |  | 22 | `active_users`, `caption_languages`, `cloud_recording`, `end_to_end_encryption`, `launched`, `livestream_viewers`, `max_call_length`, `max_participants` |
| Hooly Photos | Photos | 78 | `ai_editing`, `end_to_end_encrypted_backups`, `family_group_size`, `free_storage`, `head`, `latest_release_date`, `launched`, `monthly_active_users`, `photos_stored`, `store_rating`, `trash_retention`, `version`, `video_upload_limit`, `yearly_billing_discount` |
| Hooly Photos Lite | Photos Lite | 15 | `price`, `storage` |
| Hooly Photos Max | Photos Max | 18 | `price`, `storage` |
| Hooly Photos Plus | Photos Plus | 19 | `price`, `storage` |
| Hooly Pixel 10 | Pixel 10 | 51 | `base_storage`, `battery_capacity`, `battery_life`, `charging_power`, `colours`, `main_camera`, `memory`, `price`, `refresh_rate`, `released`, `screen_size`, `shipping_android`, `store_rating`, `units_sold`, `update_promise`, `weight` |
| Hooly Pixel 10 Pro | Pixel 10 Pro | 32 | `base_storage`, `battery_capacity`, `battery_life`, `charging_power`, `colours`, `main_camera`, `memory`, `price`, `released`, `screen_size`, `units_sold`, `weight` |
| Hooly Pixel 9 | Pixel 9 | 42 | `battery_capacity`, `discontinued`, `price`, `released`, `screen_size`, `storage`, `store_rating`, `units_sold`, `update_promise` |
| Hooly Pixel Buds | Pixel Buds | 9 | `adaptive_noise_cancelling`, `battery_life`, `price`, `units_sold` |
| Hooly Pixel Fold | Pixel Fold | 44 | `base_storage`, `battery_capacity`, `cover_screen_size`, `hinge_rating`, `inner_screen_size`, `price`, `released`, `store_rating`, `units_sold`, `weight` |
| Hooly Pixel Watch | Pixel Watch | 25 | `battery_life`, `cellular_option`, `full_charge_time`, `price`, `released`, `screen_size`, `sensors`, `store_rating`, `units_sold`, `water_resistance_depth`, `weight` |
| Hooly Q1 2026 Results | Hooly's Q1 results | 18 | `advertising_share`, `call_length`, `cash`, `customers`, `guidance`, `headcount`, `operating_margin`, `revenue`, `revenue_growth`, `webcast_viewers` |
| Hooly Q2 2026 Results | Hooly's Q2 results | 9 | `advertising_share`, `call_length`, `cash`, `customers`, `guidance`, `operating_margin`, `revenue`, `revenue_growth`, `webcast_viewers` |
| Hooly Q3 2026 Results | Hooly's Q3 results | 9 | `advertising_share`, `call_length`, `cash`, `customers`, `guidance`, `operating_margin`, `revenue`, `revenue_growth`, `webcast_viewers` |
| Hooly Q4 2025 Results | Hooly's Q4 results | 27 | `advertising_share`, `call_length`, `cash`, `customers`, `guidance`, `headcount`, `operating_margin`, `published`, `revenue`, `revenue_growth`, `webcast_viewers` |
| Hooly Search | Search | 106 | `ad_free_option`, `ad_free_price`, `ai_answers`, `executive_owner`, `images_indexed`, `index_size`, `languages_served`, `launched`, `median_response_time`, `monthly_active_users`, `news_refresh_interval`, `personalised_ads_by_default`, `publisher_revenue_share`, `share_of_ad_revenue` |
| Hooly Sheets |  | 14 | `active_users`, `functions`, `gemini_formula_assist`, `launched`, `max_cells`, `version` |
| Hooly Sustainability Report | Sustainability Report | 21 | `cycling_commuters`, `devices_recycled`, `emissions_cut_target`, `externally_audited`, `footprint`, `net_zero_date`, `owner`, `published`, `renewable_electricity`, `travel_emissions_cut` |
| Hooly Translate | Translate | 43 | `camera_translation`, `dialects_supported`, `languages_supported`, `launched`, `monthly_active_users`, `offline_languages`, `pro_price`, `pro_tier`, `rated_accuracy`, `text_limit`, `voice_latency` |
| Hooly Vault | Vault | 19 | `announced`, `generally_available`, `minimum_nodes`, `planned_general_availability`, `waitlist` |
| Hooly Workspace | Workspace plan | 68 | `apps_included`, `copilot_included`, `customers`, `extra_seat_price`, `free_trial`, `included_seats`, `launched`, `maximum_seats`, `minimum_seats`, `price`, `storage_per_user`, `uptime_sla` |
| Hooly Workspace Enterprise | Workspace Enterprise | 40 | `apps_included`, `audit_retention`, `customers`, `data_residency_regions`, `included_seats`, `launched`, `onboarding_time`, `price`, `single_sign_on`, `storage_per_user`, `support_first_response`, `uptime_sla` |
| Hoovar |  | 14 | `desks_managed`, `facilities_team`, `joined`, `offices_run` |
| Made by Hooly 2026 | Made by Hooly | 33 | `attendees`, `city`, `date`, `devices_keynote_speaker`, `host`, `livestreamed`, `replay_available`, `sponsors`, `stream_viewers`, `talks`, `ticket_price`, `venue` |
| Meridian Health | Meridian | 2 | `flawless_seats` |
| Patreese |  | 2 | `team_size` |
| Peter Gregori |  | 3 | `chairs`, `chairs_audit_committee`, `independent_director` |
| Quayside Hall |  | 2 | `capacity` |
| Rheinhalle |  | 2 | `capacity` |
| Ron LaFlame |  | 1 | `joined` |
| The May 2026 outage | outage | 8 | `date`, `duration` |

Density: Hooly Gemini (307 facts) and Hooly (181) dominate. Next come Hooly Cloud 145, AI Pro 109, Search 106 and Jules 97. 16 subjects have fewer than 10 facts.

### Events (13)

| Event | Has a `date` attribute | Date values in practice forms (true or false) |
| --- | --- | --- |
| Gemini Launch Night | yes | 2025-10-07 |
| Hooly Cloud Next 2026 | yes | 2026-06-09, 2026-06-02, 2026-06, 2026 |
| Hooly Employee Survey | **no** | none |
| Hooly I/O 2026 | yes | 2026-03-24, 2026 |
| Hooly I/O 2027 | yes | 2027-03-23 |
| Hooly Maps Day | yes | 2026-06-09, 2026-06-23 |
| Hooly Q1 2026 Results | **no** | none |
| Hooly Q2 2026 Results | **no** | none |
| Hooly Q3 2026 Results | **no** | none |
| Hooly Q4 2025 Results | **no** (`published`) | published 2026-01-28 |
| Hooly Sustainability Report | **no** (`published`) | published 2026-08-25, 2026-09-08 |
| Made by Hooly 2026 | yes | 2026-04-28, 2026-04-21 |
| The May 2026 outage | yes | 2026-05-19 |

The contract says "the event's date is its date fact". Six of the 13 events have no `date` attribute in the practice lexicon.

### Name-valued attributes, and which values are themselves lexicon subjects (relation candidates)

| Subject.attribute (link) | Values seen | Value is a lexicon subject? |
| --- | --- | --- |
| Hooly.cto | Richard Hendrix, **Bertram Gilfoil** | Bertram Gilfoil ✔ (joined, previous_employer) |
| Hooly.ceo | Gavin Bellson, "Gavin" | ✘ |
| Hooly.head_of_product | **Dinesh Chugtay**, Richard Hendrix | Dinesh ✔ (joined) |
| Hooly.head_of_security | **Ron LaFlame**, Bertram Gilfoil (false row) | Ron ✔ (joined) |
| Hooly.head_of_workspace | **Patreese** | ✔ (team_size) |
| Hooly.headquarters | Berlin → Lisbon (1 May 2026) | ✘ |
| Hooly.series_a_lead / series_a_co_investor | Raviqa Capital / Raviqa; Breem-Hall | ✘ |
| Hooly.soc2_auditor | Certiq Assurance | ✘ |
| Hooly Cloud.reliability_lead | **Holdan** | ✔ (joined, previous_employer, team_size) |
| Hooly Cloud.home_region / newest_region | Frankfurt / Montreal, Warsaw | ✘ |
| Hooly Gemini.cloud_provider / primary_region | Nimbus Cloud / Frankfurt | ✘ |
| Hooly Employee Survey.run_by | **Erlich Bachmann** | ✔ (joined) |
| Hooly Photos.head | **Erlich Bachmann**, Tarra | Erlich ✔ |
| Hooly Board.chair | Gavin Bellson, **Peter Gregori** | Peter ✔ (chairs, chairs_audit_committee, independent_director) |
| Hooly Sustainability Report.owner | **Hoovar**, **Bertram Gilfoil** | ✔ both |
| Hooly Hiring Programme.executive_sponsor | Richard Hendrix, **Bertram Gilfoil** | Bertram ✔ |
| Hooly Search.executive_owner | Richard Hendrix, **Bertram Gilfoil** | Bertram ✔ |
| Hooly Maps Day.venue | **Quayside Hall** | ✔ (capacity) |
| Made by Hooly 2026.venue | **Rheinhalle** | ✔ (capacity) |
| Hooly Android.lead / Jules.lead / Maps.lead / Chrome.lead | Nelson Bighettie, Davis Bannerchek / Nelson Bighettie, Richard Hendrix / Jian-Yeng, Richard Hendrix / Gwartt | ✘ |
| Hooly Devices.head | Gavin Bellson, Jack Barkor | ✘ |
| Hooly Devices.manufacturing_partner | Tessel Works | ✘ |
| Event city / venue / host / keynote fields | Berlin, Dublin, Lisbon, Frankfurt, Ringsend Forum, Gavin Bellson, Jian-Yeng, Jack Barkor | ✘ (except the two venues above) |
| Bertram Gilfoil.previous_employer, Holdan.previous_employer | Kestrel Bank; Nimbus Cloud / Nimbus | ✘ |
| Peter Gregori.chairs | Hooly Board | ✔ |

Several of the relation words claim-forms.md lists "on the practice pages" (`CEO`, `headquarters`, `Series A lead`, `primary region`, `cloud provider`, `lead`, `city`) point to targets that are **not** subjects in the practice lexicon. The run-time lexicon may contain them.

---

## 14. Worked timelines from the practice data

These show what "true on its date" and "some pages lie" mean in practice.

**Hooly AI Pro.price**
- 2025-10-07 → 2026-03-18: €49 per month (many true rows; a 2026-03-18 row says "a pricing change is coming next month").
- 2026-02-10: a "€59 per month" row is false (too early).
- **2026-04-01 onwards: €59 per month** ("Since 1 April, Hooly AI Pro is €59 per month").
- 2026-10-26: two rows saying €49 per month are **false** (stale pages).
- 2026-03-05: `Dinesh: Hooly AI Pro charges €49 per month and lets you test for seven days.` is false. The price was right on that date, so presumably the trial length is the false fact (14 days then, 7 days from April).
- Yearly price €490 per year → €590 per year.

**Hooly Gemini.languages**
- 6 languages from launch (2025-10-07) until Gemini 2.0 at Hooly I/O 2026 (2026-03-24), then **12**.
- False rows: "30 languages", "40 languages", and "12 languages" stated before 2026-03-24.
- Some 6-language rows are false because of another fact in the same row ("answers in under a second").

**Hooly.headquarters:** Berlin → **Lisbon from 2026-05-01**. Rows on 2026-09-16 and 2026-10-26 saying Berlin are false.

**Hooly.cto:** Richard Hendrix → **Bertram Gilfoil from 2026-07-01**. A 2026-07-01 row "Hooly's CTO is Richard Hendrix." is false.

**Hooly.ceo:** Gavin Bellson. Some forms store the value `"Gavin"` ("Gavin Bellson, Hooly's Gavin, opened the event."), which looks like an artefact where the title was replaced by the name.

**Hooly.series_a_*:** €18 million led by Raviqa Capital (2026-02-17). A 2026-10-26 claim of €25 million is false.

---

## 15. Observations and quirks

1. **The run-time input has no forms.** The run gets only `id,text,date`, so whatever structure is needed must come from the text, the date and the lexicon.
2. **Row labels are coarse.** One false value makes the whole row false, so labels for individual facts in multi-fact rows are not given directly.
3. **Truth depends on time.** Values change during the year, and true or false is judged per row date. Stale repeats and early announcements are a major source of false rows.
4. **Sources differ in reliability.** Transcript lines, Gavin quotes, testimonials and boastful posts are false or unsure more often than other rows.
5. **Sentences leave the subject to context.** At least 31% of facts are never named in their own sentence, and pages are roughly recoverable as runs of consecutive ids sharing a date.
6. **Units in dataset forms don't always match the referee's canonical symbols.** For example, `inch` appears in forms, while value-forms lists `in`. Counted nouns can be odd (`star`, `fold`, `megapixel`).
7. **Every practice price is in EUR.** The value grammar still supports 16 currencies.
8. **Booleans** cover about 7% of facts. Text claims about them need the attribute in words, and some attributes are long (`end_to_end_encrypted_backups`, `personalised_ads_by_default`, `data_processing_agreement`).
9. **Event aliases embed years** (`Hooly I/O 2026`, `The May 2026 outage`). Values or dates inside a needed name don't count against the "no other value or date" rules.
10. **Two names hint at an entity missing from the lexicon:** `integration_partner_of_flawless` and `flawless_seats` mention "Flawless".
11. **The as-of date (29 Oct 2026) is one day after the last practice page (28 Oct 2026).** The full universe has 9× more pages over what is presumably the same year.

---

## 16. Things the docs require

These are rules taken from the documents above, not recommendations.

- [ ] A `Dockerfile` at the repository root that builds for `linux/amd64`, is ≤ 3 GiB, and ends with `USER 10001`.
- [ ] Everything needed from the practice data or any model is **baked into the image**, because the run is offline.
- [ ] The run finishes inside 10 minutes (watch `ARENA_DEADLINE` and `SIGTERM`), and `/output/output.csv` is on disk before it ends.
- [ ] Peak memory stays within 6 GB, including anything written to `/tmp` (128 MB cap).
- [ ] The system at run time **is not an LLM**.
- [ ] CSV: UTF-8, header row, proper quoting (the `form` JSON contains commas and quotes).
- [ ] Every entry is valid against `entry.schema.json`: unique id matching the pattern, one of the 5 types, text ≤ 300 chars, label `true`/`false`, confidence in [0.5, 1], no `op` in values, no extra keys.
- [ ] Every subject and attribute exists in the **run-time** lexicon (names or aliases, any case).
- [ ] Every text passes the claim-form and value-form grammars: one sentence, subject named, exact value form, no negation (except yes/no), no extra value of the same kind, no own date or time word, and the type's phrase lists.
- [ ] A PR from your fork to `QA-DNA/hype-arena-starter`, titled with the team name, open before 11:00 on 29 Oct. **No pushes after 11:00.**
- [ ] A demo video of the system running on `sample/sample.csv` (20 rows, available at 10:30).

---

## 17. Open questions the repository does not answer

- **Scoring.** How entries are scored: per correct label, weighted by confidence (a calibration score such as Brier or log-loss?), penalties for invalid entries, or rewards for volume, coverage or diversity of types.
- **How many entries.** "One entry per row" in the contract means one CSV row per entry, but there is no stated minimum or maximum, and it is unclear whether entries should map to universe rows.
- **What counts as "new content".** Whether an entry restating a fact a universe sentence already states scores the same as a novel combination (compare, change, relation).
- **Run-time lexicon size.** How much bigger it is, whether new subjects or attributes appear that practice never shows, and whether events without a `date` attribute gain one.
- **Who checks the "not an LLM" rule, and how strictly.** For example, whether small classical NLP models or embeddings are allowed at run time.
- **Which date entries use for `fact` and `compare`.** It is fixed at 29 Oct 2026, but it is unclear whether facts that changed after the last universe page can be known.
- **The CSV `form` column format.** The example uses JSON with spaces after the separators. Whether compact JSON is fine is implied but not stated.
