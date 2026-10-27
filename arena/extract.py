"""Read observations out of universe pages: (subject, attribute, value) per sentence.

Per sentence: lexicon mentions, values (values.read), cues. Each value goes to
the (subject, attribute) that scores best:

- subject: a mention in the sentence (the one nearest before the value first),
  then the previous sentence's subject, then the page's dominant subjects and
  events (headings, press-release leads, event recaps);
- attribute: the subject's attributes whose AttrSpec kind fits the value
  (currency and period for money, dimension or noun for quantities), ranked by
  the words of the sentence against the attribute's own words and HINTS.

Precision matters more than recall: the universe is nine times the practice
set and repeats its facts, so a value with weak evidence is dropped.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from arena.grammar import claims as C
from arena.grammar import sentences as S
from arena.grammar import values as V
from arena.model import Observation, Page, Value
from arena.pages import split_sentences

# Words that point at an attribute, keyed by an attribute or one of its words.
HINTS: dict[str, tuple[str, ...]] = {
    "price": ("cost", "costs", "priced", "charges", "charge", "pay", "sells", "sale", "plan", "at", "from"),
    "annual": ("year", "yearly", "annually", "annum"),
    "rent": ("rent", "lease"),
    "credit": ("credit", "credits"),
    "bounty": ("bounty", "reward"),
    "bonus": ("bonus", "pays"),
    "revenue": ("revenue", "booked", "sales", "turnover"),
    "cash": ("cash", "bank"),
    "guidance": ("guidance", "expect", "forecast"),
    "amount": ("raised", "round", "closed", "funding", "led"),
    "launched": ("launch", "launched", "opened", "live", "since", "public", "went", "debut", "introduced", "available"),
    "released": ("release", "released", "ships", "shipped", "shipping", "out", "landed", "arrives", "available"),
    "release": ("release", "released", "ships", "shipped", "landed", "arrives", "reached"),
    "joined": ("joined", "join", "joins", "started", "starts", "hired", "arrived", "began", "begins", "welcome",
               "came"),
    "founded": ("founded", "started", "created", "established"),
    "opened": ("opened", "opens", "doors"),
    "announced": ("announced", "announce", "unveiled"),
    "published": ("published", "out", "came", "released"),
    "date": ("place", "held", "opens", "opened", "opening", "day", "takes", "took", "starts", "kicks", "evening"),
    "beta": ("beta", "testers", "preview"),
    "general_availability_date": ("generally", "available", "ga"),
    "generally_available": ("generally", "available", "ga"),
    "lease_end": ("ends", "expires", "lease"),
    "next_meeting": ("next", "meets", "meeting", "gather", "session"),
    "stable": ("stable",),
    "employees": ("employees", "staff", "people", "headcount", "employs", "team", "workforce"),
    "headcount": ("employees", "staff", "people", "headcount"),
    "users": ("users", "people", "accounts", "use"),
    "active": ("active", "monthly", "use", "using", "month"),
    "customers": ("customers", "clients", "companies", "serves", "businesses"),
    "uptime": ("uptime", "up", "availability", "available"),
    "sla": ("promise", "promises", "guarantee", "guaranteed", "sla", "commits", "paid"),
    "quarter": ("quarter",),
    "trial": ("trial", "free", "test", "try"),
    "retention": ("keep", "keeps", "kept", "stay", "stays", "retains", "retain", "history", "deleted"),
    "response": ("response", "responds", "replies", "reply", "answers", "answer", "takes"),
    "reply": ("reply", "replies", "answers", "first"),
    "median": ("median", "typical"),
    "p99": ("p99", "slowest"),
    "version": ("version", "release", "runs", "build", "ships", "notes"),
    "storage": ("storage", "space", "stores", "holds"),
    "size": ("size", "large", "largest", "up"),
    "max": ("max", "maximum", "up", "largest", "most", "limit", "cap", "reach"),
    "limit": ("limit", "max", "up", "can"),
    "share": ("share", "holds", "of"),
    "rating": ("rate", "rated", "rating", "stars", "reviewers", "owners", "give"),
    "store": ("store", "reviewers", "owners"),
    "battery": ("battery",),
    "capacity": ("capacity", "battery", "seats", "holds", "fits"),
    "life": ("lasts", "life", "last", "hours"),
    "screen": ("screen", "display"),
    "weight": ("weighs", "weight", "heavy", "light"),
    "sold": ("sold", "units", "shipped", "sales"),
    "attendees": ("attendees", "people", "attended", "came", "guests", "visitors", "crowd"),
    "ticket": ("ticket", "tickets", "entry", "admission"),
    "keynote": ("keynote",),
    "length": ("days", "long", "lasted", "ran", "closed", "length", "across", "spread"),
    "viewers": ("viewers", "watched", "stream", "livestream", "online"),
    "languages": ("languages", "speaks", "speak", "spoke"),
    "rate": ("rate", "percent"),
    "growth": ("growth", "grew", "grow", "up"),
    "margin": ("margin",),
    "satisfaction": ("satisfaction", "satisfied", "rated", "scored"),
    "accuracy": ("accuracy", "accurate", "scores"),
    "cutoff": ("cutoff", "trained", "training"),
    "ceo": ("ceo", "chief", "executive"),
    "cto": ("cto",),
    "head": ("head", "heads", "runs", "leads", "under", "answers", "charge"),
    "lead": ("lead", "leads", "led", "leading"),
    "chair": ("chair", "chairs", "chaired", "chairman"),
    "owner": ("owner", "owns", "owned"),
    "sponsor": ("sponsor", "sponsored", "executive"),
    "headquarters": ("headquarters", "headquartered", "hq", "based"),
    "city": ("in", "city", "held"),
    "venue": ("venue", "at", "hall", "held"),
    "host": ("host", "hosts", "hosted"),
    "provider": ("provider", "runs", "hosted", "on"),
    "region": ("region", "regions"),
    "auditor": ("auditor", "audit", "engaged"),
    "partner": ("partner", "builds", "built", "manufactures"),
    "previous_employer": ("before", "previously", "ran", "came", "worked"),
    "run_by": ("ran", "run", "runs"),
    "investor": ("co", "investor", "joined"),
    "speaker": ("keynote", "speaker", "gives", "stage"),
    "opening": ("opened", "opening", "proceedings"),
    "founders": ("founded", "founders", "founder"),
    "cadence": ("every", "cycle", "cadence"),
    "interval": ("every", "refresh", "refreshed"),
    "delay": ("after", "sleep"),
    "recover": ("recover", "recovery", "fix"),
}

_STOP = frozenset(
    """the a an of in on at to for and or is are was were its it by with from has have this that our we as be
    per s i you he she they his her their my your all any each every new now still also just only than then
    there here so not no but do does did can will would""".split()
)
_ATTR_STOP = frozenset({"of", "the", "in", "to", "by", "is", "a", "per", "on", "at", "and"})

_SPEAKER = re.compile(r"^\s*(?P<who>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)?):\s")
_CUES = {
    "testimonial": re.compile(r"\b(?:for me|replaced \w+ tools|my (?:team|week|life|work)|I love|I use|we use|changed my)\b", re.I),
    "boast": re.compile(r"\b(?:before lunch|not even tired|and I asked|the missing percent|I am the|best in the world|"
                        r"nobody else|the rest is poetry|and counting|I could|in my sleep)\b", re.I),
    "hearsay": re.compile(r"\b(?:I (?:have|'ve) been told|I was told|I hear|I heard|recalls|reportedly|apparently|"
                          r"rumou?r|allegedly|supposedly|word is|they say|people say)\b", re.I),
    "announce_future": re.compile(r"\b(?:will|coming|next (?:week|month|quarter|year)|is set to|plans? to|planned|"
                                  r"upcoming|from \d{1,2} \w+|starting|soon|later this|due)\b", re.I),
    "press_release": re.compile(r"\b(?:today (?:launched|announced|introduced|opened)|announced today|"
                                r"^[A-Z][a-z]+, \d{1,2} [A-Z][a-z]+ \d{4})", re.I),
    "release_notes": re.compile(r"\b(?:release notes|changelog|what'?s new|ships today with)\b", re.I),
}
_VERBISH = re.compile(
    r"\b(?:is|are|was|were|has|have|had|costs?|runs?|holds?|offers?|ships?|speaks?|serves?|keeps?|gives?|"
    r"takes?|reaches?|lasts?|starts?|opens?|opened|launched|released|joined|founded|sold|includes?|"
    r"\w+ed|\w+s)\b", re.I
)


def _stem(w: str) -> str:
    w = w.lower()
    for suf in ("ing", "ers", "ed", "es", "er", "s", "d"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _match(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:
        return a.startswith(b) or b.startswith(a)
    return False


def _attr_words(attr: str) -> list[str]:
    return [t for t in attr.split("_") if t and t not in _ATTR_STOP]


def _hint_words(attr: str) -> set[str]:
    out: set[str] = set(HINTS.get(attr, ()))
    for t in _attr_words(attr):
        out.update(HINTS.get(t, ()))
    toks = attr.split("_")
    for i in range(len(toks) - 1):
        out.update(HINTS.get("_".join(toks[i:i + 2]), ()))
    return {_stem(w) for w in out}


def _sentence_words(sentence: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", sentence) if w.lower() not in _STOP]


def _attr_score(attr: str, words: list[str], local: list[str]) -> float:
    """How strongly the sentence's words point at the attribute.

    Words near the value (its clause and the few words before it) count fully,
    the rest of the sentence less; every word of the attribute that the
    sentence lacks costs a little, so `version` beats `api_version` when
    neither `api` nor `version` is written.
    """
    score = 0.0
    for t in (_stem(t) for t in _attr_words(attr)):
        if any(_match(t, w) for w in local):
            score += 2.0
        elif any(_match(t, w) for w in words):
            score += 1.0
        else:
            score -= 0.75
    for h in _hint_words(attr):
        if any(_match(h, w) for w in local):
            score += 1.0
        elif any(_match(h, w) for w in words):
            score += 0.4
    return score


def _local_words(sentence: str, start: int, end: int) -> list[str]:
    a, b = S.clause_of(sentence, start)
    lo = max(0, min(a, start - 40))
    return _sentence_words(sentence[lo:max(b, end)])


def _spec(attrs, subject: str, attribute: str):
    sp = attrs.get((subject, attribute)) if attrs else None
    if sp is None and attrs:
        for (s, a), x in attrs.items():
            if a == attribute:
                return x
    return sp


def _g(spec, key):
    if spec is None:
        return None
    return spec.get(key) if isinstance(spec, dict) else getattr(spec, key, None)


def _fit(spec, r: V.Reading) -> Optional[float]:
    """How well a reading fits an attribute's spec: None when the kind does not fit."""
    v = r.value
    if spec is None or _g(spec, "kind") != v.kind:
        return None
    k = v.kind
    if k == "money":
        if _g(spec, "currency") and _g(spec, "currency") != v.currency:
            return None
        return 2.0 if _g(spec, "per") == v.per else -3.0
    if k == "quantity":
        su, ru = _g(spec, "unit"), v.unit
        ps, pr = V.canonical_unit(su), V.canonical_unit(ru)
        if ps or pr:
            if not (ps and pr) or V._PHYS_DIM[ps][0] != V._PHYS_DIM[pr][0]:
                return None
            return 3.0
        if su and V.singular(su) in r.nouns:
            return 5.0 if V.singular(su) == V.singular(ru or "") else 3.0
        return -2.0
    if k == "duration":
        return 1.0 if V._dur_group(_g(spec, "unit")) == V._dur_group(v.unit) else -1.0
    return 1.0


def _cues(row_text: str, sentence: str, first_row: bool, mentions) -> frozenset[str]:
    cues = set()
    sp = _SPEAKER.match(row_text)
    if sp:
        cues.add("speaker")
        if sp.group("who").split()[0].lower() == "gavin":
            cues.add("gavin")
    if re.search(r"\bGavin\b", sentence):
        cues.add("gavin")
    for name, rx in _CUES.items():
        if rx.search(sentence):
            cues.add(name)
    words = re.findall(r"\S+", sentence)
    if len(words) <= 4 and not _VERBISH.search(sentence):
        cues.add("table_cell")
    if first_row and not sentence.rstrip().endswith((".", "!", "?")) and len(words) <= 12:
        cues.add("headline")
    return frozenset(cues)


def _value_inside(r: V.Reading, spans) -> bool:
    return any(a <= r.num_start < b for a, b in spans)


class _PageContext:
    def __init__(self, page: Page, lexicon):
        self.page = page
        self.lexicon = lexicon
        counts: Counter = Counter()
        first: list[str] = []
        events: list[str] = []
        for i, row in enumerate(page.rows):
            for m in lexicon.find_mentions(row.text, any_case=False):
                counts[m.subject] += 1
                if i == 0:
                    first.append(m.subject)
                if m.subject in lexicon.events and m.subject not in events:
                    events.append(m.subject)
        self.counts = counts
        self.first = first
        self.events = events
        self.dominant = [s for s, _ in counts.most_common(3)]


def _choose(r: V.Reading, cands: list[tuple[str, float, bool]], lexicon, attrs, words, local, used):
    """Best (score, subject, attribute, subject_in_sentence) for reading r, or None."""
    best = None
    for subject, prior, in_sentence in cands:
        for attr in lexicon.subjects.get(subject, ()):
            fit = _fit(_spec(attrs, subject, attr), r)
            if fit is None:
                continue
            score = prior + fit + _attr_score(attr, words, local)
            if (subject, attr) in used:
                score -= 3.0
            if best is None or score > best[0]:
                best = (score, subject, attr, in_sentence)
    return best


def _candidates(sentence_mentions, value_pos: int, ctx: _PageContext, prev: Optional[str], lexicon,
                exclude: set[str]) -> list[tuple[str, float, bool]]:
    out: dict[str, tuple[float, bool]] = {}

    def add(s, p, ins):
        if s in exclude or s not in lexicon.subjects:
            return
        if s not in out or out[s][0] < p:
            out[s] = (p, ins)

    before = [m for m in sentence_mentions if m.end <= value_pos]
    after = [m for m in sentence_mentions if m.start >= value_pos]
    if sentence_mentions:
        add(sentence_mentions[0].subject, 4.0, True)  # the sentence's first name: usually its subject
    for i, m in enumerate(reversed(before)):
        add(m.subject, 3.6 - 0.4 * i, True)
    for i, m in enumerate(after):
        add(m.subject, 3.0 - 0.5 * i, True)
    if prev:
        add(prev, 1.5, False)
    for s in ctx.first:
        add(s, 1.2, False)
    for i, s in enumerate(ctx.dominant):
        add(s, 1.0 - 0.2 * i, False)
    for s in ctx.events:
        add(s, 0.8, False)
    return [(s, p, ins) for s, (p, ins) in out.items()]


_CAP_COMMON = frozenset(
    """series region regions today tomorrow yesterday host guest release notes version update new our we
    europe european eu ai pro free plus max lite beta stable type ii api sdk cli faq q a""".split()
)

# Thresholds picked on the practice replay (replay_scores): precision 0.91, recall 0.73.
_MIN_SCORE_IN = 3.5  # subject named in the sentence
_MIN_SCORE_OUT = 5.0  # subject taken from context


def _names_in(sentence: str, mentions) -> list[tuple[str, int, int]]:
    """Name-like phrases: lexicon mentions and capitalised runs that are not mentions."""
    out = [(m.subject, m.start, m.end) for m in mentions]
    taken = [(m.start, m.end) for m in mentions]
    for m in re.finditer(r"(?<![A-Za-z0-9])[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?){0,2}", sentence):
        a, b = m.span()
        if any(x < b and a < y for x, y in taken):
            continue
        phrase = m.group(0)
        if sentence[b:b + 1] == ":":
            continue  # a speaker label
        at_start = not sentence[:a].strip() or sentence[:a].rstrip().endswith((":", '"'))
        if at_start and len(phrase.split()) == 1:
            continue
        first = phrase.split()[0].lower()
        if first in _STOP or first in S.YEARLESS_DATE_WORDS or first in _CAP_COMMON:
            continue
        out.append((phrase, a, b))
    return out


def extract(pages: list[Page], lexicon, attrs: dict, labels: Optional[dict[str, str]] = None) -> list[Observation]:
    """Observations of every page: one per value a sentence states, with cues.

    attrs is B's AttrSpec map keyed (subject, attribute); it decides which
    attributes a value of a given kind can belong to. labels maps row ids to
    practice labels, copied onto the observations when replaying practice.
    Values that read as nothing (negated, approximate, range ends) are dropped;
    values with comparison words are kept with their op.
    """
    out: list[Observation] = []
    for page in pages:
        ctx = _PageContext(page, lexicon)
        prev: Optional[str] = None
        for ri, row in enumerate(page.rows):
            label = labels.get(row.id) if labels else None
            for sentence in split_sentences(row.text, lenient=True):
                obs, prev = _extract_sentence(sentence, row, ri, page, ctx, prev, lexicon, attrs, label)
                out.extend(obs)
    return out


def _extract_sentence(sentence, row, ri, page, ctx, prev, lexicon, attrs, label):
    mentions = lexicon.find_mentions(sentence, any_case=False)
    spans = [(m.start, m.end) for m in mentions]
    words = _sentence_words(sentence)
    raw_lower = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", sentence)}
    cues = _cues(row.text, sentence, ri == 0, mentions)
    prev_for_sentence = prev
    readings = [r for r in V.read(sentence) if not _value_inside(r, spans)]
    groups: dict[int, list[V.Reading]] = {}
    for r in readings:
        if r.negated or r.approximate or r.range_end:
            continue
        groups.setdefault(r.num_start, []).append(r)
    obs: list[Observation] = []
    used: set[tuple[str, str]] = set()
    resolved_subject = None
    for pos in sorted(groups):
        best = None
        for r in groups[pos]:
            cands = _candidates(mentions, r.start, ctx, prev_for_sentence, lexicon, set())
            if r.value.kind == "version":  # `Hooly Gemini 2.2`: the name right before the number
                adj = [m for m in mentions if m.end <= r.num_start and not sentence[m.end:r.num_start].strip()]
                if adj:
                    cands = [(s, p + (4.0 if s == adj[-1].subject else 0.0), i) for s, p, i in cands]
            local = _local_words(sentence, r.start, r.end)
            ch = _choose(r, cands, lexicon, attrs, words, local, used)
            if ch and (best is None or ch[0] > best[0][0]):
                best = (ch, r)
        if not best:
            continue
        (score, subject, attr, in_sentence), r = best
        if score < (_MIN_SCORE_IN if in_sentence else _MIN_SCORE_OUT):
            continue
        used.add((subject, attr))
        resolved_subject = resolved_subject or subject
        obs.append(_obs(subject, attr, r.value, page, row, sentence, in_sentence, cues, label))
    obs += _names_and_booleans(sentence, mentions, ctx, prev_for_sentence, lexicon, attrs, words, raw_lower,
                               used, page, row, cues, label)
    named = [m.subject for m in mentions if m.subject in lexicon.subjects]
    new_prev = resolved_subject or (named[0] if named else prev)
    return obs, new_prev


def _obs(subject, attr, value, page, row, sentence, in_sentence, cues, label) -> Observation:
    return Observation(
        subject=subject, attribute=attr, value=value, date=page.date, page_id=page.page_id, row_id=row.id,
        sentence=sentence, subject_in_sentence=in_sentence, cues=cues, label=label,
    )


def _names_and_booleans(sentence, mentions, ctx, prev, lexicon, attrs, words, raw_lower, used, page, row, cues, label):
    obs = []
    neg_spans = S.find_negations(sentence)
    # names: a name-like phrase, given to the attribute of a nearby subject that its words point at
    names = _names_in(sentence, mentions)
    for value, a, b in names:
        if any(x <= a < y for x, y in neg_spans) or S.negated_before(sentence, a):
            continue
        canon = lexicon.resolve(value)
        cands = _candidates([m for m in mentions if m.start != a], a, ctx, prev, lexicon, {canon} if canon else set())
        local = _local_words(sentence, a, b)
        best = None
        for subject, prior, ins in cands:
            for attr in lexicon.subjects.get(subject, ()):
                if _g(_spec(attrs, subject, attr), "kind") != "name" or (subject, attr) in used:
                    continue
                s = _attr_score(attr, words, local)
                if s < 2.0:
                    continue
                score = prior + s
                if best is None or score > best[0]:
                    best = (score, subject, attr, ins)
        if best and best[0] >= (_MIN_SCORE_IN if best[3] else _MIN_SCORE_OUT):
            _, subject, attr, ins = best
            used.add((subject, attr))
            obs.append(_obs(subject, attr, Value("name", canon or value), page, row, sentence, ins, cues, label))
    # yes/no: the attribute's own words in the sentence, polarity from negation
    subjects = [(m.subject, 2.0, True) for m in mentions if m.subject in lexicon.subjects]
    if prev:
        subjects.append((prev, 0.5, False))
    seen = set()
    for subject, prior, ins in subjects:
        if subject in seen:
            continue
        seen.add(subject)
        for attr in lexicon.subjects.get(subject, ()):
            if _g(_spec(attrs, subject, attr), "kind") != "boolean" or (subject, attr) in used:
                continue
            own = [_stem(t) for t in _attr_words(attr)]
            hit = [t for t in own if any(_match(t, w) for w in words)]
            exact = C.attribute_word_spans(sentence, attr)
            if not exact and (len(hit) < max(2, len(own)) if len(own) > 1 else not hit):
                continue
            if not ins and not exact:
                continue
            at = exact[0][0] if exact else 0
            a, b = S.clause_of(sentence, at)
            value = not any(a <= x < b for x, _ in neg_spans)
            used.add((subject, attr))
            obs.append(_obs(subject, attr, Value("boolean", value), page, row, sentence, ins, cues, label))
    return obs


def replay_scores(practice_csv: str, lexicon, attrs) -> dict:
    """Extract the practice set and score (subject, attribute, value) against its forms.

    Returns {"precision", "recall", "n_obs", "n_facts", "by_kind": {kind: (p, r)}}.
    An observation is right when a fact of its own row has the same subject,
    attribute and value (op included).
    """
    import json

    from arena.pages import load_universe, read_rows

    rows = read_rows(practice_csv)
    facts = {r["id"]: json.loads(r["form"]) for r in rows}
    labels = {r["id"]: r["label"] for r in rows}
    obs = extract(load_universe(practice_csv), lexicon, attrs, labels)
    right = Counter()
    total = Counter()
    found = set()
    for o in obs:
        total[o.value.kind] += 1
        for i, f in enumerate(facts.get(o.row_id, ())):
            if f["subject"] == o.subject and f["attribute"] == o.attribute and V.same_value(
                Value.from_json(f["value"]), o.value
            ):
                right[o.value.kind] += 1
                found.add((o.row_id, i))
                break
    n_facts = Counter(f["value"]["kind"] for fs in facts.values() for f in fs)
    got = Counter(facts[rid][i]["value"]["kind"] for rid, i in found)
    by_kind = {
        k: (right[k] / total[k] if total[k] else 0.0, got[k] / n_facts[k] if n_facts[k] else 0.0)
        for k in sorted(set(n_facts) | set(total))
    }
    return {
        "precision": sum(right.values()) / max(1, sum(total.values())),
        "recall": len(found) / max(1, sum(n_facts.values())),
        "n_obs": sum(total.values()),
        "n_facts": sum(n_facts.values()),
        "by_kind": by_kind,
    }
