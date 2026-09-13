"""Shared Latin-name folding for comparisons, never display names or saved IDs.

This only removes spelling differences introduced by Unicode. It does not
identify a person: callers must still check fixture/team/tour, IDs and ambiguity.
Keep provider-specific suffix, comma-order and alias handling at the call site.
"""
from __future__ import annotations

import html
import unicodedata

_FOLDS = {"ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
          "æ": "ae", "œ": "oe", "ß": "ss", "ı": "i", "ħ": "h"}
_TRANSLATION = str.maketrans({**_FOLDS, **{k.upper(): v.upper() for k, v in _FOLDS.items()
                                        if k.upper() != k and len(k.upper()) == 1}, "ẞ": "SS"})


def fold_name_text(value: object) -> str:
    """Fold accented/special Latin letters, preserving case and punctuation.

    Unknown alphabets are retained, never guessed or transliterated into an
    unrelated player. Existing matching policies decide whether they can resolve.
    """
    text = html.unescape(str(value or "")).translate(_TRANSLATION)
    return "".join(char for char in unicodedata.normalize("NFKD", text)
                   if unicodedata.category(char) != "Mn")
