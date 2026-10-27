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
    "extra": ("extra", "further", "additional", "each", "more"),
    "included": ("includes", "included", "including", "covers", "bundle"),
    "minimum": ("starts", "minimum", "least", "smallest"),
    "maximum": ("admits", "maximum", "max", "most", "largest", "reach", "reaches"),
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
    "release": ("release", "released", "ships", "shipped", "landed", "arrives", "reached", "due"),
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
    "lead": ("lead", "leads", "led", "leading", "answers"),
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
_ATTR_STOP = frozenset({"of", "the", "in", "to", "by", "is", "a", "per", "on", "at", "and", "date", "time"})

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
    if a == b or a + "s" == b or b + "s" == a:
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


def _mask(sentence: str, spans) -> str:
    """The sentence with the given spans blanked out (offsets kept)."""
    chars = list(sentence)
    for a, b in spans:
        for i in range(a, b):
            chars[i] = " "
    return "".join(chars)


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


def _options(r: V.Reading, cands: list[tuple[str, float, bool]], lexicon, attrs, words, local):
    """Every (score, subject, attribute, subject_in_sentence) reading r could fill.

    When nothing in the text points at any of the subject's fitting attributes,
    only a clear default survives (`Hooly Gemini 1.0 is live`: version over
    api_version); a tie among such attributes is a guess, and dropped.
    """
    out = []
    for subject, prior, in_sentence in cands:
        fits = []
        for attr in lexicon.subjects.get(subject, ()):
            fit = _fit(_spec(attrs, subject, attr), r)
            if fit is not None:
                fits.append((attr, fit, _attr_score(attr, words, local)))
        if fits and max(e for _, _, e in fits) <= 0:
            top = max(e for _, _, e in fits)
            best = [f for f in fits if f[2] == top]
            fits = best if len(best) == 1 else []
        for attr, fit, evidence in fits:
            out.append((prior + fit + evidence, subject, attr, in_sentence))
    return out


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

# Thresholds picked on the practice replay (replay_scores): precision 0.96, recall 0.75.
_MIN_SCORE_IN = 3.0  # subject named in the sentence
_MIN_SCORE_OUT = 4.5  # subject taken from context


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


_MAX_SENTENCE = 2000  # no real sentence is longer; longer ones are skipped, not parsed


def _extract_sentence(sentence, row, ri, page, ctx, prev, lexicon, attrs, label):
    if len(sentence) > _MAX_SENTENCE:
        return [], prev
    mentions = lexicon.find_mentions(sentence, any_case=False)
    spans = [(m.start, m.end) for m in mentions]
    words = _sentence_words(sentence)
    cues = _cues(row.text, sentence, ri == 0, mentions)
    readings = [r for r in V.read(sentence) if not _value_inside(r, spans)]
    groups: dict[int, list[V.Reading]] = {}
    for r in readings:
        if r.negated or r.approximate or r.range_end:
            continue
        groups.setdefault(r.num_start, []).append(r)
    # Every value against every (subject, attribute) it could fill; the best pairs go first,
    # so `€199 per month ... each further seat is €15 a month` gives price to €199 even
    # though €199 comes first and also mentions seats.
    options = []
    for pos in sorted(groups):
        for r in groups[pos]:
            cands = _candidates(mentions, r.start, ctx, prev, lexicon, set())
            ca, cb = S.clause_of(sentence, r.start)
            here = {m.subject for m in mentions if ca <= m.start < cb}  # named in the value's own clause
            cands = [(s, p + (1.0 if s in here else 0.0), i) for s, p, i in cands]
            if r.value.kind == "version":  # `Hooly Gemini 2.2`: the name right before the number
                adj = [m for m in mentions if m.end <= r.num_start and not sentence[m.end:r.num_start].strip()]
                if adj:
                    cands = [(s, p + (4.0 if s == adj[-1].subject else 0.0), i) for s, p, i in cands]
            # the words of the sentence's other values (`10 seats`) say nothing about this one
            masked = _mask(sentence, [(o.start, o.end) for o in readings if o.num_start != r.num_start])
            local = _local_words(masked, r.start, r.end)
            sa = masked.rfind(";", 0, r.start) + 1  # a `;` ends the passage the value belongs to
            sb = masked.find(";", r.end)
            seg_words = _sentence_words(masked[sa:sb if sb >= 0 else len(masked)])
            for score, subject, attr, ins in _options(r, cands, lexicon, attrs, seg_words, local):
                if score >= (_MIN_SCORE_IN if ins else _MIN_SCORE_OUT):
                    options.append((score, pos, subject, attr, ins, r))
    options.sort(key=lambda o: (-o[0], o[1]))
    chosen: list[tuple[int, Observation]] = []
    used: set[tuple[str, str]] = set()
    done: set[int] = set()
    for score, pos, subject, attr, ins, r in options:
        if pos in done or (subject, attr) in used:
            continue
        done.add(pos)
        used.add((subject, attr))
        value = _align_unit(r, _spec(attrs, subject, attr))
        chosen.append((pos, _obs(subject, attr, value, page, row, sentence, ins, cues, label)))
    chosen.sort(key=lambda c: c[0])
    obs = [o for _, o in chosen]
    resolved_subject = obs[0].subject if obs else None
    obs += _names_and_booleans(sentence, mentions, ctx, prev, lexicon, attrs, words,
                               used, page, row, cues, label)
    named = [m.subject for m in mentions if m.subject in lexicon.subjects]
    new_prev = resolved_subject or (named[0] if named else prev)
    return obs, new_prev


def _align_unit(r: V.Reading, spec) -> Value:
    """The value with its unit spelled as the attribute's spec spells the same unit.

    `6.3 in` against a spec in `inch` becomes inch, `1,200 paying customers`
    against `customer` becomes customer, so observations and the practice seed
    agree without unit conversion. Other units stay as written.
    """
    v = r.value
    su = _g(spec, "unit")
    if v.kind != "quantity" or not su or su == v.unit:
        return v
    cs, cv = V.canonical_unit(su), V.canonical_unit(v.unit)
    if (cs and cs == cv) or (not cs and not cv and V.singular(su) in r.nouns):
        return Value(v.kind, v.value, su, v.currency, v.per, v.op)
    return v


def _obs(subject, attr, value, page, row, sentence, in_sentence, cues, label) -> Observation:
    return Observation(
        subject=subject, attribute=attr, value=value, date=page.date, page_id=page.page_id, row_id=row.id,
        sentence=sentence, subject_in_sentence=in_sentence, cues=cues, label=label,
    )


def _owns(lexicon, canon: str, tokens: list[str]) -> bool:
    """True when the entity has an attribute of its own written with one of these words.

    `Davis Bannerchek leads Android at Hooly`: Hooly has a series_a_lead and
    Android a lead, so neither is the name of a lead here; `The Hooly Berlin
    Office is Hooly's headquarters`: the office has is_headquarters.
    """
    for attr in lexicon.subjects.get(canon, ()):
        if any(_match(_stem(t), tok) for t in _attr_words(attr) for tok in tokens):
            return True
    return False


# What kind of entity a name-valued attribute holds, read from its words.
_PERSON_WORDS = frozenset(
    "ceo cto cfo coo head lead chair owner host speaker keynote sponsor executive founder founders run director".split()
)
_PLACE_WORDS = frozenset("city venue headquarters region office country location".split())
_ORG_WORDS = frozenset("provider employer investor auditor partner series".split())
# What kind of entity a lexicon subject is, read from its own attributes.
_PERSON_ATTRS = frozenset(
    "joined previous_employer team_size chairs chairs_audit_committee independent_director desks_managed offices_run".split()
)
_VENUE_ATTRS = frozenset("capacity".split())


def _attr_type(attr: str) -> Optional[str]:
    words = set(attr.split("_"))
    if words & _ORG_WORDS:
        return "org"  # series_a_lead holds an investor, not a person
    if words & _PLACE_WORDS:
        return "place"
    if words & _PERSON_WORDS:
        return "person"
    return None


def _fits_type(lexicon, canon: str, attr: str) -> bool:
    """Can the lexicon entity be the value of this attribute?

    A subject with `joined` or `team_size` is a person, one with `capacity` a
    venue: a venue is no city or host, a person no provider or region.
    """
    own = set(lexicon.subjects.get(canon, ()))
    person, venue = bool(own & _PERSON_ATTRS), bool(own & _VENUE_ATTRS)
    t = _attr_type(attr)
    if t == "person":
        return person or not own
    if t == "place":
        return not person and not (venue and attr.split("_")[0] != "venue")
    if t == "org":
        return not person and not venue
    return True


def _name_observations(sentence, mentions, ctx, prev, lexicon, attrs, words, used, neg_spans, page, row, cues, label):
    """Names to name-valued attributes, the best (subject, attribute, name) triples first.

    A name goes to the attribute whose own words (or hints) stand nearest to
    it, in its clause, and never to a subject it is itself, or one that owns
    those words.
    """
    spans = [(m.start(), m.end(), _stem(m.group(0))) for m in re.finditer(r"[A-Za-z][A-Za-z0-9]*", sentence)]

    def index_of(pos: int) -> int:
        return sum(1 for a, _, _ in spans if a < pos)

    triples = []
    for value, a, b in _names_in(sentence, mentions):
        if any(x <= a < y for x, y in neg_spans) or S.negated_before(sentence, a):
            continue
        canon = lexicon.resolve(value)
        cands = _candidates([m for m in mentions if m.start != a], a, ctx, prev, lexicon, {canon} if canon else set())
        local = _local_words(sentence, a, b)
        after_in = bool(re.search(r"(?<![A-Za-z])in\s+$", sentence[:a]))
        clause = S.clause_of(sentence, a)
        at = index_of(a)
        for subject, prior, ins in cands:
            for attr in lexicon.subjects.get(subject, ()):
                if _g(_spec(attrs, subject, attr), "kind") != "name" or (subject, attr) in used:
                    continue
                own = [_stem(t) for t in _attr_words(attr)]
                matched = [t for t in own if any(_match(t, w) for w in local)]
                if canon and (_owns(lexicon, canon, matched or own) or not _fits_type(lexicon, canon, attr)):
                    continue
                s = _attr_score(attr, words, local)
                if attr == "city" and after_in and not (canon and lexicon.subjects.get(canon)):
                    matched, s = ["city"], s + 3.0  # `... in Dublin` on an event's page
                if not matched or s < 2.0:
                    continue
                cues_at = [i for i, (x, _, w) in enumerate(spans)
                           if any(_match(t, w) for t in own + list(_hint_words(attr))) and not (a <= x < b)]
                dist = min((abs(i - at) for i in cues_at), default=6)
                near = any(clause[0] <= spans[i][0] < clause[1] for i in cues_at) or attr == "city"
                score = prior + s - 0.5 * dist - (0.0 if near else 1.5)
                triples.append((score, subject, attr, value, canon, ins))
    triples.sort(key=lambda x: -x[0])
    obs: list[Observation] = []
    taken: set[str] = set()  # names given out as values
    as_values: set[str] = set()  # lexicon subjects given out as values
    owners = {o for o, _ in used}  # subjects that already hold a value of this sentence
    for score, subject, attr, value, canon, ins in triples:
        if score < (_MIN_SCORE_IN if ins else _MIN_SCORE_OUT) or (subject, attr) in used:
            continue
        if value in taken or (canon and canon in owners) or subject in as_values:
            continue
        used.add((subject, attr))
        taken.add(value)
        if canon:
            as_values.add(canon)
        owners.add(subject)
        obs.append(_obs(subject, attr, Value("name", canon or value), page, row, sentence, ins, cues, label))
    return obs


def _names_and_booleans(sentence, mentions, ctx, prev, lexicon, attrs, words, used, page, row, cues, label):
    obs = []
    numeric = bool(used)
    numeric_at = [r.num_start for r in V.read(sentence)] if numeric else []
    neg_spans = S.find_negations(sentence)
    obs += _name_observations(sentence, mentions, ctx, prev, lexicon, attrs, words, used, neg_spans,
                              page, row, cues, label)
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
            if not exact and (not ins or numeric):
                continue  # loose words beside another value are about that value (`Offline limit: 3 GB`)
            at = exact[0][0] if exact else 0
            ca, cb = S.clause_of(sentence, at)
            if any(ca <= p < cb for p in numeric_at):
                continue  # `On offline maps ... each area can take 5 GB`: the words name the value's topic
            # yes/no reads the whole passage (`Offline in Hooly Maps: not live`), up to a `;`
            a = sentence.rfind(";", 0, at) + 1
            b = sentence.find(";", at)
            b = len(sentence) if b < 0 else b
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
