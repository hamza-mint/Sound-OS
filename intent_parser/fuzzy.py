"""Typo-tolerant second pass for the rule parser (Plan A, part 2).

Why it exists: the small Whisper models often misspell the RIGHT word, e.g. for "المتصفح"
tiny wrote "المبصف", base wrote "لما تصف", small wrote "المتصف". Exact rules say "unknown".

When it runs: ONLY after every exact rule failed (see rules.parse). So it can never change
the result of a sentence the rules already understand.

What it does (stdlib only, no extra install, ~ms):
  1. repair_tokens   - a word that is not in the vocabulary but is very close to one is replaced
                       (فايرفكس -> فايرفوكس, الكرم -> كروم, brouser -> browser).
  2. repair_slot     - "open/close <something strange>": the strange word (or two glued words)
                       is matched against the APP / FOLDER names with a lower cutoff, because the
                       verb tells us an app name is expected (لما تصف -> متصفح).
Safety: rules.parse drops a result that is "shutdown" / "delete_file" when it came from here.

The vocabulary is NOT written twice: every word given to rules.W(...), plus APPS, FOLDERS and
MEDIA, is used automatically. Add a word to rules.py and it becomes typo-tolerant too.
"""
import difflib
from functools import lru_cache

from .normalize import normalize as N

TOKEN_CUTOFF = 0.80     # similarity needed to repair a random word
SLOT_CUTOFF = 0.70      # similarity needed for an app/folder name after open/close
SLOT_MARGIN = 0.12      # the best app must beat the 2nd best by this much (else: ambiguous -> no guess)
PAIR_CUTOFF = 0.75      # two glued words are a weaker signal, so they need a closer match
MIN_LEN = 4             # shorter words (ايه, من, up, run) are never "repaired"
# Function words are never a spelling mistake of an app name. Without this "اقفل اللي فاتح"
# (close the one that is open) was glued into "ليفاتح" and "repaired" to the file manager.
STOP = frozenset({"اللي", "الي", "ده", "دا", "دي", "ديه", "هذا", "هذه", "كل", "بتاع", "بتاعت", "بتاعه",
                  "علي", "على", "في", "من", "الحالي", "الحاليه", "شغال", "قدامي", "فاتح", "مفتوح", "معايا",
                  "the", "this", "that", "one", "all", "every", "current", "open"})

# Common English words that must NEVER be repaired into an app/command name.
# Classic false-positive: "what" -> "whats" (whatsapp).  Block the whole class.
_EN_STOPWORDS = frozenset({
    "what", "when", "where", "which", "while", "whose", "whom",
    "that", "this", "then", "than", "them", "they", "there",
    "have", "does", "done", "dont", "into", "with", "from",
    "some", "your", "here", "how", "who", "why", "tell", "good",
    "time", "just", "also", "only", "very", "much", "many", "more",
    "been", "will", "want", "make", "like", "know", "think", "look",
    "came", "come", "said", "says", "find", "show", "help", "need",
})

# Letters Whisper confuses by sound. Used ONLY to compare two words, never to rewrite text.
_PHON = str.maketrans({"ص": "س", "ث": "س", "ذ": "ز", "ظ": "ز", "ض": "د", "ط": "ت", "ق": "ك"})

# Arabic close/open verbs that Whisper often confuses (acoustic similarity)
# Adding explicit mapping so "افتح" -> "اقفل" when context demands close
_CLOSE_OPEN_MAP = {
    "افتح": "اقفل", "افتحي": "اقفلي", "تفتح": "تقفل",
    "افتحلي": "اقفلي", "افتحها": "اقفلها",
    "open": "close", "opening": "closing", "openit": "closeit",
}


def _core(tok):
    """Drop the Arabic definite article: المتصفح -> متصفح."""
    return tok[2:] if tok.startswith("ال") and len(tok) > 4 else tok


def _core(tok):
    """Drop the Arabic definite article: المتصفح -> متصفح."""
    return tok[2:] if tok.startswith("ال") and len(tok) > 4 else tok


def _phon(s):
    return s.translate(_PHON)


def _sim(a, b):
    """0..1 similarity, also tries the sound-alike spelling (ص~س, ض~د, ط~ت ...)."""
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if a.translate(_PHON) != a or b.translate(_PHON) != b:
        r = max(r, difflib.SequenceMatcher(None, _phon(a), _phon(b)).ratio())
    return r


@lru_cache(maxsize=1)
def _tables():
    """(vocab words, {alias_without_spaces: canonical key}) built once from rules.py."""
    from . import rules
    phrases = set(rules._VOCAB)
    aliases = {}
    for table in (rules.APPS, rules.FOLDERS):
        for key, names in table.items():
            for a in names:
                n = N(a)
                phrases.add(n)
                core = _core(n.replace(" ", ""))
                if len(core) >= MIN_LEN - 1:
                    aliases.setdefault(core, key)
    phrases.update(N(w) for w in rules.MEDIA)
    words = set()
    for p in phrases:
        for tok in p.split():
            tok = _core(tok)
            if len(tok) >= 3 and tok.isalpha():
                words.add(tok)
    return frozenset(words), aliases


def clear_fuzzy_cache() -> None:
    """Invalidate cached vocabulary tables so dynamic updates take effect immediately."""
    _tables.cache_clear()


def _known(tok, words):
    return tok in words or _core(tok) in words


def repair_token(tok, words=None):
    """Closest vocabulary word for `tok` (>= TOKEN_CUTOFF) or `tok` itself."""
    words = words if words is not None else _tables()[0]
    if len(tok) < MIN_LEN or _known(tok, words) or not tok.isalpha():
        return tok
    # Never "repair" common English words into app/command names (e.g. what -> whats -> whatsapp)
    if tok.lower() in _EN_STOPWORDS:
        return tok
    # Explicit close/open verb mapping (Whisper often confuses them acoustically)
    if tok in _CLOSE_OPEN_MAP:
        mapped = _CLOSE_OPEN_MAP[tok]
        if mapped in words or _core(mapped) in words:
            return mapped
    core = _core(tok)
    best, best_r = None, TOKEN_CUTOFF
    near = [w for w in words if abs(len(w) - len(core)) <= 2]
    for w in sorted(near):                       # sorted -> deterministic on ties
        r = _sim(core, w)
        if r > best_r:
            best, best_r = w, r
    return best if best else tok


def repair_tokens(toks):
    words = _tables()[0]
    return [repair_token(t, words) for t in toks]


def _best_alias(span_core, aliases):
    """(canonical_key, alias, score, margin) of the app/folder that sounds most like span_core."""
    scored = {}
    for alias, key in aliases.items():
        if abs(len(alias) - len(span_core)) > 3:
            continue
        r = _sim(span_core, alias)
        if r > scored.get(key, (0, ""))[0]:
            scored[key] = (r, alias)
    if not scored:
        return None
    ranked = sorted(scored.items(), key=lambda kv: -kv[1][0])
    key, (score, alias) = ranked[0]
    second = ranked[1][1][0] if len(ranked) > 1 else 0.0
    return key, alias, score, score - second


def repair_slot(toks):
    """Replace one unknown word (or two glued words) after open/close with the closest app/folder."""
    from . import rules
    words, aliases = _tables()
    text = " ".join(toks)
    if not (rules.has(rules.OPEN_ANY, text) or rules.has(rules.CLOSE, text)):
        return []
    out = []
    for i in range(len(toks)):
        for n in (1, 2):                          # a single word, or two words that were split by STT
            span = toks[i:i + n]
            if len(span) == 2 and all(t.isalpha() for t in span) and _core("".join(span)) in aliases:
                # "down loads" -> "downloads": an exact match once glued, even if "down" is also a command word
                out.append(" ".join(toks[:i] + ["".join(span)] + toks[i + n:]))
                continue
            if len(span) < n or any(len(t) < 3 or t in STOP or _known(t, words) or not t.isalpha() for t in span):
                continue
            joined = _core("".join(span)) if n == 2 else _core(span[0])
            hit = _best_alias(joined, aliases)
            if hit and hit[2] >= (PAIR_CUTOFF if n == 2 else SLOT_CUTOFF) and hit[3] >= SLOT_MARGIN:
                out.append(" ".join(toks[:i] + [hit[1]] + toks[i + n:]))
    return out


def variants(t):
    """Alternative spellings of the (already normalized) text, most conservative first."""
    toks = t.split()
    if not toks:
        return []
    seen, out = {t}, []
    for alt in [" ".join(repair_tokens(toks))] + repair_slot(repair_tokens(toks)) + repair_slot(toks):
        if alt not in seen:
            seen.add(alt)
            out.append(alt)
    return out


OPEN_VERB_CUTOFF = 0.6      # "hoping" vs "open" scores exactly 0.6; Latin-script only (Arabic is repaired by repair_token)


def repair_open_verb(t):
    """"hoping down loads" -> "open down loads". Whisper tiny/base write the English verb "open" as gibberish
    ("hoping", "oben", "obing", "obén"). Only when the sentence has no open/close verb at all and something
    follows the first word. The caller accepts the guess ONLY if it ends up opening an app or a folder."""
    from . import rules
    toks = t.split()
    if len(toks) < 2 or rules.has(rules.OPEN_ANY, t) or rules.has(rules.CLOSE, t):
        return None
    first = toks[0]
    if len(first) < 3 or not first.isascii() or not first.isalpha() or first in STOP:
        return None
    if max(_sim(first, v) for v in ("open", "opening")) < OPEN_VERB_CUTOFF:
        return None
    return " ".join(["open"] + toks[1:])
