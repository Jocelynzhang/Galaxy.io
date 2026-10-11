"""Player-name cleaning and a basic kid-safety filter.

Not a complete solution, just a first line of defence. Words that often appear inside innocent
words ("class", "peacock", "grape") are only matched as whole words to avoid false positives.
"""
import re
import unicodedata

from . import config as C

# matched anywhere inside the normalized name
_ANYWHERE = ("fuck", "shit", "bitch", "cunt", "whore", "slut", "nigg", "pussy", "wank", "twat",
             "bollock", "porn", "penis", "vagina", "hitler", "nazi", "motherf", "bastard", "retard")
# innocent words that contain one of the above; removed before the substring check
_ALLOW = ("scunthorpe", "swank", "niggle")
# matched only as whole words
_WORDS = {"ass", "arse", "dick", "cock", "tit", "tits", "cum", "sex", "sexy", "hoe", "piss", "rape",
          "fag", "anal", "crap", "kill", "kys", "nude", "boob", "boobs", "butt", "poop", "damn"}
_LEET = str.maketrans({"0": "o", "1": "i", "!": "i", "3": "e", "4": "a", "@": "a", "5": "s", "$": "s",
                       "7": "t", "8": "b", "9": "g"})


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).lower().translate(_LEET)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def is_inappropriate(name: str) -> bool:
    norm = _normalize(name)
    squashed = re.sub(r"[^a-z]", "", norm)            # catches "f.u.c.k" and "f u c k"
    checked = squashed
    for ok in _ALLOW:
        checked = checked.replace(ok, "")
    if any(bad in checked for bad in _ANYWHERE):
        return True
    words = re.findall(r"[a-z]+", norm)
    return any(w in _WORDS for w in words) or squashed in _WORDS


def clean_name(raw) -> str:
    if not isinstance(raw, str):
        return C.DEFAULT_NAME
    # drop control/format characters, collapse whitespace
    text = "".join(ch for ch in raw if unicodedata.category(ch)[0] != "C")
    text = " ".join(text.split())[: C.NAME_MAX_LEN]
    if not text or is_inappropriate(text):
        return C.DEFAULT_NAME
    return text
