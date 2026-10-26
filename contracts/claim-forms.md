# The claim forms the referee reads

An entry's text is what a reader reads, so it must say what the entry's claim says. The referee checks each entry's text against its form with the forms below, after resolving each fact the form names, by its subject and attribute, to a fact of the universe. An entry whose text does not hold what its claim says is invalid.

There is a section for each claim type: `fact`, `compare`, `change`, `at_event` and `relation`.

Every phrase and example on this page is a test: `go test ./internal/referee/` checks that the lists below are the ones the reader uses, and reads every example as shown.

## General rules

- **Names.** A subject is named by its name or an alias listed in the dataset's `lexicon.json`, as whole words, in any case and spacing. A name inside another entity's longer name names that one only: `Hooly AI Pro` names the plan, not the company Hooly.
- **Sentences.** A sentence ends at `.`, `!` or `?` before a space, or at a blank line, as in `value-forms.md`. What a form needs must stand in one sentence. Other sentences of the text may say anything.
- **Values.** A value the claim holds is written as `value-forms.md` writes it, exactly: no comparison words such as `over` or `at least`, which make it another value, and no approximation. A value written inside a name the form needs does not count: the `2026` of `Hooly I/O 2026` states no year.
- **One value, one date.** The sentence of a `fact`, `at_event` or `relation` states the claim's value and no other value of its kind, however written: no other price in the same currency and period, count of the same noun, amount in units that convert, percentage, version or date, and for a name no other entity of the same type. It states no date of its own either, unless the value is that date, and holds no word of the "Refused" table under Compare, a month without its year or a time word, outside the names the form needs, the value and the event phrase. The claim is judged on the date its type gives, so the sentence may not give another.
- **Negations.** The sentence holding a form may not hold a negation: the words under "Yes or no" in `value-forms.md`, such as `not`, `never` and any word ending in `n't`. A yes or no is the exception: a sentence states no by its negation.
- **Yes or no.** A yes or no is only the polarity of its sentence, so the sentence also holds the fact's attribute in words, in every type, read as a relation's words are: word for word, in any case, with a space, a hyphen or nothing between its words, and between a word's letters and digits. `soc2_certified` reads `SOC 2 certified`, `had_major_outage` reads `had major outage`.
- **Gaps.** `…` in a phrase stands for up to three words of your own: `more … than` reads `more than`, `more languages than` and `more paying customers than`.

## Fact

One fact has a value on the brief's as-of date. The text holds, in one sentence and in any order, a name of the fact's subject and the claim's `value`, and no other value or date (General rules).

In these examples the fact is Hooly AI Pro's price, and the value €59 per month.

| Text | Read |
| --- | --- |
| `Hooly AI Pro costs €59 per month.` | yes |
| `At €59 per month, Hooly AI Pro is our best seller.` | yes |
| `Hooly AI Pro costs over €59 per month.` | no: `over` makes it another value |
| `Hooly AI Pro costs about €59 per month.` | no: an approximation |
| `Hooly AI Pro costs €59.` | no: the price has no period |
| `It costs €59 per month.` | no: the subject is not named |
| `Hooly AI Pro is our plan. It costs €59 per month.` | no: the value is in another sentence |
| `Hooly costs €59 per month.` | no: `Hooly` names the company, not the plan |
| `Hooly AI Pro costs €59 per month, and never more.` | no: a negation |
| `Hooly AI Pro costs €59 per month or €590 per year.` | yes: a yearly price is another kind |
| `Hooly AI Pro costs €59 per month, up from €49 per month.` | no: another monthly price |
| `In March 2026, Hooly AI Pro cost €59 per month.` | no: a date of its own |
| `In April, Hooly AI Pro cost €59 per month.` | no: a month, even without its year |
| `Hooly AI Pro used to cost €59 per month.` | no: a time word |

In these examples the fact is Hooly's SOC 2 certification, and the value no.

| Text | Read |
| --- | --- |
| `Hooly is not SOC 2 certified.` | yes |
| `Hooly has never been SOC2-certified.` | yes |
| `Hooly is fully SOC 2 certified.` | no: it states yes |
| `Hooly has never passed a SOC 2 audit.` | no: the attribute's words are `SOC 2 certified` |
| `Hooly is not profitable.` | no: it is about another attribute |

## Compare

Two facts of one kind compare on the brief's as-of date: the left fact's value is more than (`gt`), less than (`lt`) or the same as (`eq`) the right fact's. For dates `gt` is after and `lt` before. The text states no value: the referee compares the values the two facts hold on the date, and on the day a value changes it holds the new one.

The text holds, in one sentence: a name of the left fact's subject, then one phrase of the claim's `op` from the list below, then a name of the right fact's subject. The left subject comes first, so swapping left and right swaps the names. The same subject may be named on both sides. No sentence of the text may hold a second phrase of the list.

That sentence states no value and no date, even one that holds on the as-of date:

- **No value**, as `value-forms.md` reads one, such as `€100`, `20%` or `four languages`, and no number at all, in digits or in words: `100`, `four`, `a dozen`, even `one`.
- **No date**, with its year or without: no month, season or day of the week from the second table below. `may` is the month only when written `May`.
- **No time word** from the second table below, other than the words of the phrase itself: `before` is the phrase between two dates, and a time word between two amounts.

A value, a date or a time word written inside the name of a compared subject does not count: the 2026 of `Hooly I/O 2026` states no year. The other sentences of the text are not read for them.

The two facts must compare: of the same kind, in units that convert, and prices in the same currency and period. Names and yes-or-no values do not compare, and neither does a fact with itself. Between dates only the date phrases read; between amounts (counts, prices, percentages, durations and versions) only the amount phrases.

| Between | `gt` | `lt` | `eq` |
| --- | --- | --- | --- |
| amounts | `more … than`, `higher … than`, `greater … than`, `larger … than`, `bigger … than`, `longer … than` | `less … than`, `fewer … than`, `lower … than`, `smaller … than`, `shorter … than`, `cheaper … than` | `the same … as`, `as much … as`, `as many … as`, `as long as`, `as high as`, `equal to` |
| dates | `after`, `later than` | `before`, `earlier than` | `on the same day as`, `the same day as` |

| Refused | Words |
| --- | --- |
| dates without a year | `January`, `February`, `March`, `April`, `May`, `June`, `July`, `August`, `September`, `October`, `November`, `December`, `spring`, `summer`, `autumn`, `winter`, `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday`, `Sunday` |
| time words | `ago`, `yesterday`, `tomorrow`, `once`, `formerly`, `previously`, `originally`, `initially`, `recently`, `lately`, `soon`, `eventually`, `then`, `before`, `after`, `since`, `until`, `till`, `earlier`, `later`, `used to`, `last week`, `last month`, `last quarter`, `last year`, `next week`, `next month`, `next quarter`, `next year`, `in the past`, `in the future`, `at the time`, `at that time` |

In these examples the left fact is Hooly Workspace's price and the right fact Hooly AI Pro's.

| Text | `op` | Read |
| --- | --- | --- |
| `Hooly Workspace costs more than Hooly AI Pro.` | `gt` | yes |
| `Hooly Workspace is more expensive than Hooly AI Pro.` | `gt` | yes |
| `The Workspace plan costs a higher monthly price than Hooly AI Pro.` | `gt` | yes |
| `Hooly Workspace costs the same as Hooly AI Pro.` | `eq` | yes |
| `Hooly Workspace costs as much as Hooly AI Pro.` | `eq` | yes |
| `Hooly Workspace costs more than Hooly AI Pro.` | `lt` | no: the phrase states `gt` |
| `Hooly AI Pro costs less than Hooly Workspace.` | `lt` | no: the left subject comes second |
| `Hooly Workspace costs more than its rivals.` | `gt` | no: the right subject is not named |
| `Hooly Workspace outprices Hooly AI Pro.` | `gt` | no: no phrase of the list |
| `Hooly Workspace does not cost more than Hooly AI Pro.` | `gt` | no: a negation |
| `Hooly Workspace costs more than Hooly AI Pro, and less than Hooly AI Free.` | `gt` | no: two phrases |
| `Hooly Workspace is our biggest plan. It costs more than Hooly AI Pro.` | `gt` | no: the left subject is named in another sentence |
| `Hooly Workspace costs more than Hooly.` | `gt` | no: `Hooly` names the company, not the plan |
| `Hooly Workspace comes after Hooly AI Pro.` | `gt` | no: a date phrase between prices |
| `Hooly Workspace costs more per month than Hooly AI Pro.` | `gt` | yes |
| `Hooly Workspace costs more than Hooly AI Pro. We checked in June 2026.` | `gt` | yes: the date is in another sentence |
| `Hooly Workspace costs €100 more than Hooly AI Pro.` | `gt` | no: a value |
| `Hooly Workspace costs 100 more than Hooly AI Pro.` | `gt` | no: a number |
| `Hooly Workspace costs a hundred more than Hooly AI Pro.` | `gt` | no: a number in words |
| `In June 2026, Hooly Workspace cost more than Hooly AI Pro.` | `gt` | no: a date |
| `In June, Hooly Workspace cost more than Hooly AI Pro.` | `gt` | no: a month, even without its year |
| `Hooly Workspace used to cost more than Hooly AI Pro.` | `gt` | no: a time word |
| `Hooly Workspace cost more than Hooly AI Pro before the outage.` | `gt` | no: `before` is a time word between amounts |

In these examples the left fact is the date of Hooly I/O 2026 and the right fact the date of the May 2026 outage.

| Text | `op` | Read |
| --- | --- | --- |
| `Hooly I/O 2026 took place before the May 2026 outage.` | `lt` | yes: the year and the month are inside the names |
| `Hooly I/O 2026 came earlier than the outage.` | `lt` | yes |
| `Hooly I/O took place on the same day as the outage.` | `eq` | yes |
| `Hooly I/O 2026 was more than the May 2026 outage.` | `gt` | no: an amount phrase between dates |
| `Hooly I/O 2026 took place two weeks before the May 2026 outage.` | `lt` | no: a value |
| `Hooly I/O 2026 took place before the outage, in March 2026.` | `lt` | no: a date |

## Change

One fact went from one value to another: it held `from`, and at a later date `to`. The brief's date plays no part. The text holds, in one sentence, a name of the fact's subject and one of these change phrases:

| Phrase | Read as |
| --- | --- |
| `from` *from* `to` *to* | the value after `from`, up to `to`, went to the value after `to`; `up` or `down` right before `from` states which way |
| *to*`, up from` *from* | the value before `up from` rose from the value after it |
| *to*`, down from` *from* | the value before `down from` fell from the value after it |

Each side of a phrase states its value on its own, so each needs its whole written form: `from €49 to €59 per month` gives €49 no period. `up` needs `to` to be the larger value, and `down` the smaller, whether it comes before `from … to` or as `up from` and `down from`; names and yes or no have no order, so take `from … to` without either. A yes or no also needs its attribute's words (General rules).

In these examples the fact is Hooly AI Pro's price, from €49 per month to €59 per month.

| Text | Read |
| --- | --- |
| `Hooly AI Pro went from €49 per month to €59 per month.` | yes |
| `The price of Hooly AI Pro rose from €49 per month to €59 per month in April.` | yes |
| `Hooly AI Pro costs €59 per month, up from €49 per month.` | yes |
| `Hooly AI Pro went up from €49 per month to €59 per month.` | yes |
| `Hooly AI Pro costs €59 per month, down from €49 per month.` | no: `down from` states a fall |
| `Hooly AI Pro went down from €49 per month to €59 per month.` | no: `down` states a fall |
| `Hooly AI Pro went from €59 per month to €49 per month.` | no: the values are the other way round |
| `Hooly AI Pro went from €49 to €59 per month.` | no: €49 has no period |
| `Hooly AI Pro cost €49 per month and now costs €59 per month.` | no: no change phrase |
| `Hooly AI Pro never went from €49 per month to €59 per month.` | no: a negation |

## At an event

A fact had a value on the date of an event, whatever the brief's date. The form's `event` names the event; the event's date is its date fact. The text holds, in one sentence and in any order, a name of the fact's subject, an event phrase right before a name of the event, with `the` between them or not, and the claim's `value`, and no other value or date: the event gives the date (General rules). The time words of an event phrase, such as `at the time`, are the phrase's own.

The event phrases are `at`, `during`, `on the day of`, `at the time of`.

In these examples the fact is Hooly Gemini's languages, the event Hooly I/O 2026, and the value 12 languages.

| Text | Read |
| --- | --- |
| `Hooly Gemini spoke 12 languages at Hooly I/O 2026.` | yes |
| `At Hooly I/O, Hooly Gemini spoke a dozen languages.` | yes |
| `Hooly Gemini supported 12 languages on the day of Hooly I/O 2026.` | yes |
| `Hooly Gemini spoke 12 languages at the time of Hooly I/O 2026.` | yes |
| `Hooly Gemini spoke 12 languages before Hooly I/O 2026.` | no: no event phrase before the event |
| `Hooly Gemini spoke 12 languages in March.` | no: the event is not named |
| `At Hooly I/O 2026, Hooly spoke 12 languages.` | no: `Hooly` names the company, not Hooly Gemini |
| `Hooly Gemini spoke 12 languages at Hooly I/O 2026, up from 6 languages.` | no: another count of languages |
| `In March 2026, at Hooly I/O 2026, Hooly Gemini spoke 12 languages.` | no: a date of its own |

## Relation

A fact of the entity another fact names, such as the start date of Hooly's CTO. The form's `link` is the subject's attribute that names the entity, here Hooly's `cto`, its `target` the entity it names, here Bertram Gilfoil, and its `attribute` that entity's own fact, here the day he `joined`. The link must name the target at some date; the claim is true when the fact held the value while the link named that subject. The brief's date plays no part.

The text holds, in one sentence and in any order, a name of the link's subject, the link's relation words and the claim's `value`, and no other value or date (General rules). The relation words are the link's attribute, word for word, in any case, with a space, a hyphen or nothing between its words, and between a word's letters and digits: on the practice pages, `CEO`, `CTO`, `headquarters`, `Series A lead`, `head of product`, `primary region`, `cloud provider`, `lead` (of a product) and `city` (of an event).

In these examples the link is Hooly's CTO, the fact the day Bertram Gilfoil joined, and the value 1 July 2026.

| Text | Read |
| --- | --- |
| `The CTO of Hooly joined on 1 July 2026.` | yes |
| `Hooly's CTO started on 2026-07-01.` | yes |
| `Hooly's chief technology officer joined on 1 July 2026.` | no: the relation words are `CTO` |
| `Bertram Gilfoil joined Hooly on 1 July 2026.` | no: no relation words |
| `The CTO joined on 1 July 2026.` | no: the link's subject is not named |
| `The CTO of Hooly, who left on 3 May 2027, joined on 1 July 2026.` | no: another date |
| `The CTO of Hooly joined on 1 July 2026, after Richard Hendrix.` | no: a time word |
