"""Build the corrupted-Kazakh dataset for HW1 from real published sentences.

WHY IT IS BUILT THIS WAY
------------------------
The *correct* sentences are real Kazakh, published by Kazinform and
professionally edited. They were fetched on 2026-08-19 and are quoted verbatim.
Nothing about the correct Kazakh is authored here.

The *errors* are applied mechanically by the functions below, and each one is
labelled with the rule that produced it. That gives three things a hand-written
error list cannot:

  1. The ground truth is a real published sentence, not someone's guess at
     correct Kazakh.
  2. Every error has a name, so marking is objective: did the model repair
     `kaz_to_rus` substitutions or not?
  3. The professor can add sentences without having to invent errors.

The two main corruption rules are the two mistakes that actually happen:

  kaz_to_rus       Kazakh-specific letters replaced by their Russian lookalikes
                   (ә→а, ө→о, ұ/ү→у, і→и, ң→н, ғ→г, қ→к, һ→х). This is what a
                   Russian keyboard layout does to Kazakh text.
  latin_homoglyph  Cyrillic letters replaced by visually identical Latin ones
                   (а→a, е→e, о→o, с→c, р→p …). Invisible on screen, and it
                   wrecks tokenization - which is the Week 2 tie-in.

A CAVEAT THE PROFESSOR SHOULD CHECK
-----------------------------------
These corruptions are synthetic. They are reliably *wrong*, but they are not
claimed to be typical student or learner errors. Before handing this out, read
the generated file and confirm the corrupted sentences look plausibly broken to
a Kazakh speaker. Add real error examples if you have them - `EXTRA` below is
the place for them.

Run:  python make_dataset.py
"""

import json
import unicodedata
from pathlib import Path

SOURCE_NOTE = ("Kazinform (kaz.inform.kz), fetched 2026-08-19, quoted verbatim. "
               "Headlines from the Kazakh-language edition.")

# Real, published, correct Kazakh. Do not edit these to "fix" them.
CORRECT = [
    "Қасым-Жомарт Тоқаев бірқатар мемлекеттің елшісінен сенім грамоталарын қабылдады",
    "Баспанада 50%-ға дейін үлесі бар азаматтар мемлекеттік тұрғын үйді жекешелендіре алады",
    "Алаяқтарға ақшаңызды аударып қойсаңыз не істеу керек",
    "Елде жалған дипломдар үшін қандай жаза қарастырылған",
    "Алматыдағы ғимараттардың қаншасы жер сілкінісіне төзімді",
    "Елде жеті айда 9,7 млн шаршы метр тұрғын үй пайдалануға берілді",
    "Алаяқтардан қорғану жолдары: елорда прокуратурасы ескерту жасады",
    "Дональд Трамп Ким Чен Ынмен осы күзде қайта кездескісі келеді",
]

# Space for real error examples the professor supplies. Each entry is
# {"corrupted": ..., "correct": ..., "errors": ["professor_supplied"]}.
EXTRA = []

KAZ_TO_RUS = {
    "ә": "а", "Ә": "А", "ө": "о", "Ө": "О", "ұ": "у", "Ұ": "У",
    "ү": "у", "Ү": "У", "і": "и", "І": "И", "ң": "н", "Ң": "Н",
    "ғ": "г", "Ғ": "Г", "қ": "к", "Қ": "К", "һ": "х", "Һ": "Х",
}

CYR_TO_LAT = {
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x",
    "у": "y", "к": "k", "м": "m", "т": "t", "А": "A", "Е": "E",
    "О": "O", "С": "C", "Р": "P", "Х": "X", "К": "K", "М": "M", "Т": "T",
}


def kaz_to_rus(text, limit=None):
    """Replace Kazakh-specific letters with Russian lookalikes."""
    out, hits = [], 0
    for ch in text:
        if ch in KAZ_TO_RUS and (limit is None or hits < limit):
            out.append(KAZ_TO_RUS[ch])
            hits += 1
        else:
            out.append(ch)
    return "".join(out), hits


def latin_homoglyph(text, limit=3):
    """Swap a few Cyrillic letters for identical-looking Latin ones."""
    out, hits = [], 0
    for ch in text:
        if ch in CYR_TO_LAT and hits < limit:
            out.append(CYR_TO_LAT[ch])
            hits += 1
        else:
            out.append(ch)
    return "".join(out), hits


def drop_hyphen(text):
    return text.replace("-", " "), text.count("-")


def join_words(text, index=1):
    """Remove one space, welding two words together."""
    parts = text.split(" ")
    if len(parts) <= index + 1:
        return text, 0
    parts[index] = parts[index] + parts[index + 1]
    del parts[index + 1]
    return " ".join(parts), 1


def double_letter(text, index=4):
    """Double the first real letter at or after `index`.

    Indexing blindly can land on a space, which produces a whitespace fault
    labelled as a doubled letter. Skip forward to an actual letter.
    """
    i = index
    while i < len(text) and not text[i].isalpha():
        i += 1
    if i >= len(text):
        return text, 0
    return text[:i] + text[i] + text[i:], 1


# One labelled recipe per sentence keeps marking unambiguous. The last two
# stack two rules, so students meet a sentence with more than one fault.
# Paired to CORRECT by position, and the pairing is not arbitrary: drop_hyphen
# is second because sentence 2 ("50%-ga") is one of only two sentences that
# contain a hyphen at all. A recipe that changes nothing raises rather than
# silently emitting an uncorrupted row.
RECIPES = [
    ("kaz_to_rus", lambda t: kaz_to_rus(t)),
    ("drop_hyphen", lambda t: drop_hyphen(t)),
    ("latin_homoglyph", lambda t: latin_homoglyph(t)),
    ("kaz_to_rus_partial", lambda t: kaz_to_rus(t, limit=2)),
    ("join_words", lambda t: join_words(t)),
    ("double_letter", lambda t: double_letter(t)),
    ("kaz_to_rus+join_words", lambda t: _chain(t, kaz_to_rus, join_words)),
    ("latin_homoglyph+double_letter",
     lambda t: _chain(t, latin_homoglyph, double_letter)),
]


def _chain(text, *fns):
    total = 0
    for fn in fns:
        text, n = fn(text)
        total += n
    return text, total


def main():
    rows = []
    for i, (correct, (label, fn)) in enumerate(zip(CORRECT, RECIPES), start=1):
        corrupted, hits = fn(correct)
        if corrupted == correct:
            raise SystemExit(f"recipe {label} changed nothing on sentence {i}")
        rows.append({
            "id": f"KZ-{i:02d}",
            "corrupted": corrupted,
            "correct": correct,
            "errors": label.split("+"),
            "edits_applied": hits,
            "source": SOURCE_NOTE,
        })
    rows.extend(EXTRA)

    out = {
        "note": ("Correct sentences are real published Kazakh. Corruptions are "
                 "synthetic and labelled. The 'correct' field is the marking "
                 "reference, but a model may return a different valid Kazakh "
                 "sentence - grade the analysis, not string equality."),
        "generated_by": "make_dataset.py",
        "sentences": rows,
    }
    path = Path(__file__).parent / "data" / "kazakh_errors.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {path.relative_to(Path(__file__).parent)} with {len(rows)} sentences\n")
    for r in rows:
        print(f"{r['id']}  [{'+'.join(r['errors'])}, {r['edits_applied']} edit(s)]")
        print(f"  corrupted: {r['corrupted']}")
        print(f"  correct:   {r['correct']}")
        # Show that the corruption really did change the codepoints.
        diff = sum(1 for a, b in zip(r["corrupted"], r["correct"]) if a != b)
        print(f"  differing codepoints in the aligned prefix: {diff}\n")


if __name__ == "__main__":
    main()
