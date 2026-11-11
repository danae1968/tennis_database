"""Player-name normalisation and matching across sources whose name styles differ.

Point-by-point files use full names ("Rafael Nadal"), initial + surname with a dot ("A. Dolgopolov")
or without ("C Moutet"); TennisMyLife and the Match Charting Project use full names.  A short name
matches a full name if, after accent/punctuation normalisation, the full names are equal, or the
initial agrees with the first name and the surname tokens equal the trailing tokens of the full name.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=None)
def normalize_name(name: str) -> tuple[str, ...]:
    """Lower-case ASCII tokens; hyphens, dots and apostrophes become separators."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[-.'`,]", " ", s.lower())
    return tuple(t for t in s.split() if t)


def names_match(pbp_name: str, tml_name: str) -> bool:
    """Whether a pbp-style player name refers to the TML full name (see module docstring)."""
    p, t = normalize_name(pbp_name), normalize_name(tml_name)
    if not p or not t:
        return False
    if p == t:
        return True
    initials = []
    rest = list(p)
    while len(rest) > 1 and len(rest[0]) == 1:
        initials.append(rest.pop(0))
    if initials:
        n = len(rest)
        return len(t) > n and tuple(t[-n:]) == tuple(rest) and t[0][0] == initials[0]
    # full-name style but not identical (e.g. a middle name or compound surname): same first
    # initial and the pbp surname is the TML surname's last token, or vice versa
    return p[0][0] == t[0][0] and (p[-1] == t[-1]) and (p[0] == t[0] or len(p) != len(t))
