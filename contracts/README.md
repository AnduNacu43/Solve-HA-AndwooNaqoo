# The contract

What you get, and what your system hands in for the final. Nothing else is part of the contract.

## What you get

The practice dataset: one row per sentence of the practice part of the Hooly universe, 10% of the whole universe, as CSV, JSONL and XLSX, with its lexicon.

| Column | Holds |
| --- | --- |
| `id` | The row's id |
| `text` | The sentence |
| `date` | The date of the page it comes from |
| `label` | `true`, `false` or `unsure`: whether the sentence is true on its date |
| `form` | The facts the sentence states, as JSON: for each, its `subject`, its `attribute` and its `value` |

- **`false`** when the sentence states at least one false value; **`unsure`** when the dataset itself gives no means to tell; **`true`** otherwise.
- **The lexicon** (`lexicon.json`) lists every subject the dataset names, with its aliases and its attributes, and the events.
- **For the final,** the finalists' systems read the whole universe in the same shape, without `label` and `form`: `id`, `text`, `date`.

## What your system hands in

A table, CSV or XLSX, one entry per row, with these columns in any order:

| Column | Holds |
| --- | --- |
| `id` | The entry's id, unique in the table: letters, digits, `.`, `_` or `-`, at most 64 |
| `type` | `fact`, `compare`, `change`, `at_event` or `relation` |
| `text` | The claim in one sentence, at most 300 characters, in the forms of [`claim-forms.md`](claim-forms.md) |
| `form` | The claim in structured form, as JSON (below, and [`entry.schema.json`](entry.schema.json)) |
| `label` | `true` or `false`: whether the claim is true on its date |
| `confidence` | How sure your system is that its label is right, from 0.5 to 1 |

- **A CSV** is UTF-8, and its first row names the columns. A cell that holds a comma, a quote or a line break is quoted, as any CSV library writes it, or the row splits and is invalid. A CSV as Excel writes it with a Romanian locale, with semicolons and a decimal comma, reads too.
- **An XLSX file** is read from its first sheet, with the same first row.
- **Each row is an entry** of [`entry.schema.json`](entry.schema.json), its `label` being the entry's `tag`.

```csv
id,type,text,form,label,confidence
e1,compare,Hooly Workspace costs more than Hooly AI Pro.,"{""left"": {""subject"": ""Hooly Workspace"", ""attribute"": ""price""}, ""right"": {""subject"": ""Hooly AI Pro"", ""attribute"": ""price""}, ""op"": ""gt""}",true,0.9
```

### The form of each type

| `type` | `form` | True when |
| --- | --- | --- |
| `fact` | `subject`, `attribute`, `value` | the fact has the value on 29 Oct 2026 |
| `compare` | `left`, `right` (each a `subject` and an `attribute`), `op`: `gt`, `lt` or `eq` | the two facts' values compare so on 29 Oct 2026; between dates `gt` is after and `lt` before |
| `change` | `subject`, `attribute`, `from`, `to` | the fact held `from`, and later `to` |
| `at_event` | `subject`, `attribute`, `event`, `value` | the fact had the value on the date of the event `event` names |
| `relation` | `subject`, `link`, `target`, `attribute`, `value` | the `attribute` of `target`, the entity the subject's `link` names, had the value while `link` named it |

`examples/entry/good/` holds one of each type.

- **Each fact** is named by its subject and attribute, as the lexicon gives them; a name or alias in any case works. A subject no entity has, or an attribute the subject lacks, makes the entry invalid.
- **A value** is exact, as [`claimed_value.schema.json`](claimed_value.schema.json) writes it, with no `op`: a claim that one value is more or less than another is a `compare`.
- **The text** must say what the claim says, in one sentence, in the forms of [`claim-forms.md`](claim-forms.md), with its values written as [`value-forms.md`](value-forms.md) writes them, and nothing the claim could be read against instead: no other value of the claim's kind, no date or time word of its own, and for a yes or no the fact's attribute in words.
