# The value forms the referee reads

The referee is deterministic: no model decides whether a claim is true. For every entry, the referee checks that its text states each value of its claim in one of the forms below, in the sentence `claim-forms.md` says, and its base then says whether the claim is true on its date. A value written any other way does not count, and the entry is invalid.

Every example on this page is a test: `go test ./internal/value/` reads each example and checks it is read as shown, and that each example under "Not read" is not.

## General rules

- **A value is read where it stands, whole.** It is read with its comparison words and its unit, from whole numbers: `99.6% uptime` never states 6%, and `over 10,000 customers` never states 10,000 customers.
- **Case.** Words match in any case: `14 DAYS`, `Gigabytes`. Symbols whose case carries meaning must be written as listed: `m` is a metre and `M` a million, `mW` is not `MW`, and `B` is a byte.
- **Spaces.** The space between a number and its unit is optional, and so is the one before a date's month: `128GB`, `14days` and `12March 2026` all read.
- **A claim names what it is about.** The sentence of an entry's text that states a value must name the subject of the fact the claim is about, by the name or an alias listed in the dataset's `lexicon.json`, in any case; `claim-forms.md` says what else each claim type's sentence holds. Only that sentence counts: the sentence before or after it lends it nothing. A sentence ends at `.`, `!` or `?` before a space, or at a blank line; a single line break inside it is a space. The point of an abbreviation ends nothing: `e.g.`, `i.e.`, `vs.`, `approx.`, `Inc.`, `Ltd.`, `Co.`, `Corp.`, `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `Prof.`, `St.`, an initial such as `J.`, and `No.` before a number. So `Hooly AI Pro is now €59 a month.` can be a `fact` entry about Hooly AI Pro's price, but `It is now €59 a month.` is about nothing, and invalid. A name inside another entity's longer name names that one only: `Hooly AI Pro` names the plan, not the company Hooly.
- **Numbers.**
  - Digits use a decimal point and commas between thousands: `10,000`, `1.5`, `1,234.5`. Only a price may use a decimal comma: `€49,99`.
  - A number that could mean two things reads as nothing: one with a comma that is not between thousands, such as `99,9` or `1,5`; one with a point between thousands, such as `1.000.000`; and one with three digits after its only point, such as `1.500`, which is fifteen hundred in much of Europe. A percentage may have three: `99.999%`.
  - Words from `zero` to `ninety-nine` read, as do `a hundred`, `three hundred` and `a dozen`.
  - Scales are `thousand`, `million` or `M`, `billion` or `bn`, and `k`: `1.2 million`, `1M`, `10k`.
- **Units convert.** Units of one dimension compare after conversion: `14 days` states 2 weeks, and `1 GB` states 1,000 MB. Months and years do not convert to days.
- **Units in a claim's value** may be any spelling listed under "Quantity": `GB`, `gb` and `gigabyte` are one unit, so a claim in one is stated by a text in another. A counted noun matches in the singular or the plural, in any case.
- **Invisible characters.** A value written with an invisible character in it or beside it, such as a zero-width space, a word joiner or a soft hyphen that is not inside a word, reads as nothing. So does a name, and a yes or no in a clause with one. A soft hyphen between two letters is dropped, so `lan&shy;guages` reads `languages`.
- **Comparison words are part of the value.** `over 10,000 customers` is read as more than 10,000 customers, so it does not state 10,000 customers. A claim's value has no comparison of its own: an entry saying one value is more or less than another is a `compare`, in its own words (`claim-forms.md`). See "Comparisons".

## Values not stated plainly

These read as nothing, so an entry whose text writes its value this way is invalid.

- **After a negation in its clause.** The negation words are those listed under "Yes or no": `we do not offer 99.9% uptime`, `no 14-day trial`, `not founded by Gavin Bellson`. A clause ends at `.`, `,`, `;`, `:`, `!`, `?`, `•`, `·`, `|` or a blank line, but not at a single line break. A negation after the value is about what follows it, so `speaks 30 languages and never misses a beat` states 30 languages; an entry's sentence holds no negation at all, though, unless it states a yes or no (`claim-forms.md`). Comparison words such as `no more than` are part of their value, not a negation.
- **Approximate.** Before the value: about, around, approximately, approx, roughly, nearly, almost, circa, ca, some, estimated, est, close to, more or less, `~`, `≈` or `±`. After it: or so, give or take, or `-ish`.
- **One end of a range.** Neither end of `10-20 GB`, `10–20 GB`, `10 to 20 GB`, `10 GB to 20 GB`, `€49–€59`, `1 or 2 days` or `between 10 and 20 GB` reads. Two values joined by "or" are a choice, not a range, and both read: `€49 a month or €490 a year`.

## Quantity

A number with a unit from this list:

| Dimension | Symbols, and the spellings that also read |
| --- | --- |
| Data, in powers of 1,000 | `B`, `KB`, `MB`, `GB`, `TB`; also `kB`, `kb`, `mb`, `gb`, `tb`, byte, kilobyte, megabyte, gigabyte, gig, terabyte |
| Length | `mm`, `cm`, `m`, `km`, `in`; also millimetre, centimetre, metre, kilometre (or -meter), inch, and `"` or `″` straight after the number |
| Mass | `g`, `kg`; also gram, gramme, kilogram, kilo |
| Battery charge | `mAh` |
| Frequency | `Hz`, `kHz`, `MHz`, `GHz`; also hertz, kilohertz, megahertz, gigahertz |
| Power | `mW`, `W`, `kW`; also milliwatt, watt, kilowatt |

| Written | Read as |
| --- | --- |
| `128 GB of storage` | `{"kind": "quantity", "value": 128, "unit": "GB"}` |
| `128GB` | `{"kind": "quantity", "value": 128, "unit": "GB"}` |
| `2 terabytes` | `{"kind": "quantity", "value": 2, "unit": "TB"}` |
| `a 5,000 mAh battery` | `{"kind": "quantity", "value": 5000, "unit": "mAh"}` |
| `weighs 1.2 kg` | `{"kind": "quantity", "value": 1.2, "unit": "kg"}` |
| `a 6.1" display` | `{"kind": "quantity", "value": 6.1, "unit": "in"}` |
| `a 6.1-inch display` | `{"kind": "quantity", "value": 6.1, "unit": "in"}` |
| `3.2 GHz` | `{"kind": "quantity", "value": 3.2, "unit": "GHz"}` |
| `a 65-watt charger` | `{"kind": "quantity", "value": 65, "unit": "W"}` |
| `water resistant to 100 m` | `{"kind": "quantity", "value": 100, "unit": "m"}` |
| `1 GB` | `{"kind": "quantity", "value": 1000, "unit": "MB"}` |

**Counted nouns.** Any other word after a number is a counted noun, compared in the singular: `40 languages` is `{"value": 40, "unit": "language"}`. Up to two words may come between the number and its noun. A plain four-digit number from 1900 to 2099 is read as a year, never as a count: write `2,048 customers`, with the comma.

| Written | Read as |
| --- | --- |
| `speaks 40 languages` | `{"kind": "quantity", "value": 40, "unit": "language"}` |
| `speaks forty languages` | `{"kind": "quantity", "value": 40, "unit": "language"}` |
| `trusted by 10,000 companies` | `{"kind": "quantity", "value": 10000, "unit": "company"}` |
| `1,200 paying customers` | `{"kind": "quantity", "value": 1200, "unit": "customer"}` |
| `10,000 of our customers` | `{"kind": "quantity", "value": 10000, "unit": "customer"}` |
| `1.2 million users` | `{"kind": "quantity", "value": 1200000, "unit": "user"}` |
| `1M tests` | `{"kind": "quantity", "value": 1000000, "unit": "test"}` |
| `10k steps` | `{"kind": "quantity", "value": 10000, "unit": "step"}` |
| `twenty-four engineers` | `{"kind": "quantity", "value": 24, "unit": "engineer"}` |
| `a dozen partners` | `{"kind": "quantity", "value": 12, "unit": "partner"}` |
| `12 people` | `{"kind": "quantity", "value": 12, "unit": "person"}` |
| `zero outages` | `{"kind": "quantity", "value": 0, "unit": "outage"}` |
| `2,048 customers` | `{"kind": "quantity", "value": 2048, "unit": "customer"}` |
| `speaks 30 languages and never misses a beat` | `{"kind": "quantity", "value": 30, "unit": "language"}` |

## Money

- **Currency**, before or after the amount:
  - the symbols `€` (EUR), `$` (USD), `£` (GBP) and `US$`;
  - an ISO code: EUR, USD, GBP, CHF, RON, PLN, CZK, HUF, SEK, NOK, DKK, JPY, CNY, INR, CAD or AUD;
  - the words euro, dollar and lei (RON).
- **Billing period**, after the price:
  - written as `/month`, `/mo`, `a month`, `per month`, `monthly`, and the same for day, week and year;
  - also `/yr`, `per annum` and `annually`;
  - `per user` or `/seat` may come before it.
- **No period** means a one-off price. A monthly price does not state a one-off price, nor the other way round.
- **"From" is not a comparison.** `from €39/month` states that the price is €39 a month.

| Written | Read as |
| --- | --- |
| `€49 a month` | `{"kind": "money", "value": 49, "currency": "EUR", "per": "month"}` |
| `€49/mo` | `{"kind": "money", "value": 49, "currency": "EUR", "per": "month"}` |
| `49 euros per month` | `{"kind": "money", "value": 49, "currency": "EUR", "per": "month"}` |
| `EUR 49 monthly` | `{"kind": "money", "value": 49, "currency": "EUR", "per": "month"}` |
| `€49,99 a month` | `{"kind": "money", "value": 49.99, "currency": "EUR", "per": "month"}` |
| `€10 per user per month` | `{"kind": "money", "value": 10, "currency": "EUR", "per": "month"}` |
| `AI Pro from €39/month` | `{"kind": "money", "value": 39, "currency": "EUR", "per": "month"}` |
| `£9 a week` | `{"kind": "money", "value": 9, "currency": "GBP", "per": "week"}` |
| `€490 per annum` | `{"kind": "money", "value": 490, "currency": "EUR", "per": "year"}` |
| `$299.99` | `{"kind": "money", "value": 299.99, "currency": "USD"}` |
| `US$12` | `{"kind": "money", "value": 12, "currency": "USD"}` |
| `a €12M seed round` | `{"kind": "money", "value": 12000000, "currency": "EUR"}` |
| `€1.2bn` | `{"kind": "money", "value": 1200000000, "currency": "EUR"}` |
| `1,999 lei` | `{"kind": "money", "value": 1999, "currency": "RON"}` |
| `€49 a month or €490 a year` | `{"kind": "money", "value": 490, "currency": "EUR", "per": "year"}` |

## Percent

| Written | Read as |
| --- | --- |
| `99.99% uptime` | `{"kind": "percent", "value": 99.99}` |
| `99.9 % uptime` | `{"kind": "percent", "value": 99.9}` |
| `50 percent` | `{"kind": "percent", "value": 50}` |
| `50 per cent` | `{"kind": "percent", "value": 50}` |
| `fifty percent` | `{"kind": "percent", "value": 50}` |
| `99.999% uptime` | `{"kind": "percent", "value": 99.999}` |

## Date

- **A date needs its year.** It is read as precisely as it is written: `12 March 2026` states `2026-03-12`, not `2026-03`.
- **Months** may be written in full or abbreviated: Jan, Feb, Mar, Apr, Jun, Jul, Aug, Sep or Sept, Oct, Nov, Dec. The abbreviation may end in a dot.

| Written | Read as |
| --- | --- |
| `2026-03-12` | `{"kind": "date", "value": "2026-03-12"}` |
| `2026-03` | `{"kind": "date", "value": "2026-03"}` |
| `12 March 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `12th March 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `the 12th of March 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `12March 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `March 12, 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `Mar 12th 2026` | `{"kind": "date", "value": "2026-03-12"}` |
| `since 1 Mar. 2026` | `{"kind": "date", "value": "2026-03-01"}` |
| `March 2026` | `{"kind": "date", "value": "2026-03"}` |
| `Sept 2026` | `{"kind": "date", "value": "2026-09"}` |
| `founded in 2025` | `{"kind": "date", "value": "2025"}` |

## Version

A version reads in three forms:
- after `v` or `version`;
- as a number with two or more dots;
- as a number with one decimal point straight after a capitalised name: `Hooly Gemini 2.2`. The name is part of the value, so the text must write them together.

It is compared as written, so `2.3` is not `2.3.0`.

| Written | Read as |
| --- | --- |
| `v2.3` | `{"kind": "version", "value": "2.3"}` |
| `version 2.3` | `{"kind": "version", "value": "2.3"}` |
| `ver. 2.3` | `{"kind": "version", "value": "2.3"}` |
| `v3` | `{"kind": "version", "value": "3"}` |
| `2.3.1` | `{"kind": "version", "value": "2.3.1"}` |
| `Hooly Gemini 2.2` | `{"kind": "version", "value": "2.2"}` |

## Duration

- **The unit is kept as written** (`two weeks` is `{"value": 2, "unit": "week"}`) and converts when compared.
- **Units:** ms, s (sec, second), min (minute), h (hr, hour), day (`d`), week (wk, fortnight as 2 weeks), month (mo, mth), year (yr, decade as 10 years). A single-letter unit is written in lower case.
- **"A" or "an" counts as one** after under, within, in, for, over, than, at least, at most, to, only, just, about or around: `under a second`. Anywhere else it is a rate, so `1,000 requests a day` states no duration.

| Written | Read as |
| --- | --- |
| `battery lasts 14 days` | `{"kind": "duration", "value": 14, "unit": "day"}` |
| `a 14-day trial` | `{"kind": "duration", "value": 14, "unit": "day"}` |
| `a 14-day trial` | `{"kind": "duration", "value": 2, "unit": "week"}` |
| `14days` | `{"kind": "duration", "value": 14, "unit": "day"}` |
| `two weeks` | `{"kind": "duration", "value": 2, "unit": "week"}` |
| `a two-week trial` | `{"kind": "duration", "value": 2, "unit": "week"}` |
| `for a fortnight` | `{"kind": "duration", "value": 2, "unit": "week"}` |
| `24 hours` | `{"kind": "duration", "value": 24, "unit": "h"}` |
| `24h` | `{"kind": "duration", "value": 24, "unit": "h"}` |
| `30 min` | `{"kind": "duration", "value": 30, "unit": "min"}` |
| `p95 latency 1.8 s` | `{"kind": "duration", "value": 1.8, "unit": "s"}` |
| `500 ms` | `{"kind": "duration", "value": 500, "unit": "ms"}` |
| `12 months` | `{"kind": "duration", "value": 1, "unit": "year"}` |
| `for a week` | `{"kind": "duration", "value": 1, "unit": "week"}` |

## Name

A name from the universe matches as whole words, in any case, with or without the spaces between them. The referee resolves a claim's name through the universe's published spellings, every name and alias in the dataset's `lexicon.json`. A name after a negation in its clause reads as nothing.

| Written | Read as |
| --- | --- |
| `founded by Gavin Bellson` | `{"kind": "name", "value": "Gavin Bellson"}` |
| `FOUNDED BY GAVIN BELLSON` | `{"kind": "name", "value": "Gavin Bellson"}` |
| `founded by GavinBellson` | `{"kind": "name", "value": "Gavin Bellson"}` |

## Yes or no

A passage states no when it, or the rest of the clauses it is in, contains one of these:
- the words not, no, never, none, nobody, nothing, neither, nor, without or cannot;
- a word ending in n't.

Any other passage states yes. So `SOC 2 certified` read where it stands in `The app isn't SOC 2 certified` states no. An entry's yes or no is read from its whole sentence, or from each side of a change phrase, and that sentence holds the fact's attribute in words (`claim-forms.md`).

| Written | Read as |
| --- | --- |
| `Hooly passed its SOC 2 audit` | `{"kind": "boolean", "value": true}` |
| `Hooly has never had an outage` | `{"kind": "boolean", "value": false}` |
| `The app isn't SOC 2 certified` | `{"kind": "boolean", "value": false}` |

## Comparisons

A claim's value is exact, so an entry's text never states it with these words: `over 10,000 customers` does not state 10,000 customers, and is no value a claim can hold. A claim that one fact's value is more or less than another's is a `compare`, written with the phrases of `claim-forms.md`. The parser reads these words so that a value written with them is not mistaken for the exact one.

These words before a value, or after it where shown, set its `op`:

| `op` | Words |
| --- | --- |
| `gt` (over) | over, more than, greater than, higher than, above, exceeding, in excess of, upwards of |
| `lt` (under) | under, less than, fewer than, lower than, below |
| `le` (up to) | up to, at most, no more than, not more than, maximum, max; within, for durations; after the value: or less, or fewer, or under, or below, or lower, or shorter |
| `ge` (at least) | at least, no less than, not less than, no fewer than, minimum; `+` straight after the number; after the value: or more, or higher, or above, or longer, or over |
| dates | before and prior to are `lt`, after is `gt`, by and no later than are `le`, no earlier than is `ge` |

Only, just, from and starting at leave the value as stated, with `op` `eq`. Approximations read as nothing: see "Values not stated plainly".

| Written | Read as |
| --- | --- |
| `over 10,000 customers` | `{"kind": "quantity", "value": 10000, "unit": "customer", "op": "gt"}` |
| `10,000+ customers` | `{"kind": "quantity", "value": 10000, "unit": "customer", "op": "ge"}` |
| `at least 12 languages` | `{"kind": "quantity", "value": 12, "unit": "language", "op": "ge"}` |
| `40 languages or more` | `{"kind": "quantity", "value": 40, "unit": "language", "op": "ge"}` |
| `uploads up to 25 MB` | `{"kind": "quantity", "value": 25, "unit": "MB", "op": "le"}` |
| `no more than 2 GB` | `{"kind": "quantity", "value": 2, "unit": "GB", "op": "le"}` |
| `2 GB or less` | `{"kind": "quantity", "value": 2, "unit": "GB", "op": "le"}` |
| `fewer than 50 employees` | `{"kind": "quantity", "value": 50, "unit": "employee", "op": "lt"}` |
| `under $300` | `{"kind": "money", "value": 300, "currency": "USD", "op": "lt"}` |
| `over 99% accuracy` | `{"kind": "percent", "value": 99, "op": "gt"}` |
| `answers in under a second` | `{"kind": "duration", "value": 1, "unit": "s", "op": "lt"}` |
| `within an hour` | `{"kind": "duration", "value": 1, "unit": "h", "op": "le"}` |
| `before March 2026` | `{"kind": "date", "value": "2026-03", "op": "lt"}` |
| `after 2025` | `{"kind": "date", "value": "2025", "op": "gt"}` |
| `by 1 May 2026` | `{"kind": "date", "value": "2026-05-01", "op": "le"}` |

## Not read

Written these ways, a text does not state the value beside it, and an entry that claims it is invalid.

| Written | Does not state | Why, and what reads |
| --- | --- | --- |
| `12/03/2026` | `{"kind": "date", "value": "2026-03-12"}` | Numeric dates mean different days in different countries. Write `12 March 2026` or `2026-03-12` |
| `12.03.2026` | `{"kind": "date", "value": "2026-03-12"}` | The same |
| `March 12` | `{"kind": "date", "value": "2026-03-12"}` | A date needs its year |
| `Q4 2026` | `{"kind": "date", "value": "2026"}` | Quarters and halves are not dates |
| `12 March 2026` | `{"kind": "date", "value": "2026-03"}` | The text states a day, not a month |
| `1.000.000 users` | `{"kind": "quantity", "value": 1000000, "unit": "user"}` | Dots between thousands. Write `1,000,000 users` |
| `1,5 GB` | `{"kind": "quantity", "value": 1.5, "unit": "GB"}` | A decimal comma reads only in a price. Write `1.5 GB` |
| `1,5 GB` | `{"kind": "quantity", "value": 5, "unit": "GB"}` | Nor does the number after the comma |
| `99,9% uptime` | `{"kind": "percent", "value": 9}` | The same. Write `99.9%` |
| `1.500 mAh` | `{"kind": "quantity", "value": 1500, "unit": "mAh"}` | One and a half, or fifteen hundred. Write `1,500 mAh` or `1.5 mAh` |
| `99.6% uptime` | `{"kind": "percent", "value": 6}` | Values are read from whole numbers, so this does not state 6% |
| `we do not offer 99.9% uptime` | `{"kind": "percent", "value": 99.9}` | A negation before the value in its clause |
| `no 14-day trial` | `{"kind": "duration", "value": 14, "unit": "day"}` | The same |
| `not founded by Gavin Bellson` | `{"kind": "name", "value": "Gavin Bellson"}` | The same |
| `about 10,000 customers` | `{"kind": "quantity", "value": 10000, "unit": "customer"}` | An approximation. Write the number you mean |
| `~10 GB` | `{"kind": "quantity", "value": 10, "unit": "GB"}` | The same |
| `40 languages or so` | `{"kind": "quantity", "value": 40, "unit": "language"}` | The same |
| `10–20 GB` | `{"kind": "quantity", "value": 20, "unit": "GB"}` | One end of a range |
| `10 GB to 20 GB` | `{"kind": "quantity", "value": 10, "unit": "GB"}` | The same, at either end |
| `between 10 and 20 GB` | `{"kind": "quantity", "value": 20, "unit": "GB"}` | The same |
| `1 or 2 days` | `{"kind": "duration", "value": 2, "unit": "day"}` | The same |
| `10m users` | `{"kind": "quantity", "value": 10000000, "unit": "user"}` | A lower-case m is a metre. Write `10M users` or `10 million users` |
| `2026 customers` | `{"kind": "quantity", "value": 2026, "unit": "customer"}` | A plain four-digit number from 1900 to 2099 is a year. Write `2,026 customers` |
| `half an hour` | `{"kind": "duration", "value": 30, "unit": "min"}` | Fractions in words do not read. Write `30 minutes` |
| `1,000 requests a day` | `{"kind": "duration", "value": 1, "unit": "day"}` | "A day" after a count is a rate, not a duration |
| `€49 a month` | `{"kind": "money", "value": 49, "currency": "EUR"}` | A monthly price is not a one-off price |
| `5 pounds` | `{"kind": "money", "value": 5, "currency": "GBP"}` | Pounds could be weight. Write `£5` or `5 GBP` |
| `Hooly Gemini 11` | `{"kind": "version", "value": "11"}` | A whole number after a name could be anything. Write `v11` or `version 11` |
| `v2.3` | `{"kind": "version", "value": "2.3.0"}` | Versions compare as written |
| `30 days` | `{"kind": "duration", "value": 1, "unit": "month"}` | A month is not a fixed number of days |
| `over 10,000 customers` | `{"kind": "quantity", "value": 10000, "unit": "customer"}` | "Over" makes it `gt`. State `"op": "gt"` |
| `10,000 of our happy loyal customers` | `{"kind": "quantity", "value": 10000, "unit": "customer"}` | More than two words between the number and its noun |
