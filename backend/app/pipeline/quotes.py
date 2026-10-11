"""Check that a quote returned by the model really exists in the source document (TZ §10)."""

import re

from rapidfuzz import fuzz

VERIFIED_SCORE = 85

_QUOTES = str.maketrans({"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'"})
_UZ_APOSTROPHES = re.compile(r"[ʻʼ`´']")


def normalize(text: str) -> str:
    text = text.translate(_QUOTES).casefold()
    text = _UZ_APOSTROPHES.sub("'", text)
    text = re.sub(r"-\s*\n\s*", "", text)  # words hyphenated across lines
    return re.sub(r"\s+", " ", text).strip()


def locate(
    quote: str | None, page_texts: list[str], hint_page: int | None
) -> tuple[int | None, bool]:
    """Return (1-based page, verified). Scans without a text layer keep the model's page."""
    if not quote or not any(t.strip() for t in page_texts):
        return hint_page, False
    needle = normalize(quote)
    order = list(range(len(page_texts)))
    if hint_page and 1 <= hint_page <= len(page_texts):
        near = [hint_page - 1, hint_page - 2, hint_page]
        order = [i for i in near if 0 <= i < len(page_texts)] + [i for i in order if i not in near]
    best_page, best_score = hint_page, 0.0
    for index in order:
        hay = normalize(page_texts[index])
        if not hay:
            continue
        score = fuzz.partial_ratio(needle, hay)
        if score > best_score:
            best_page, best_score = index + 1, score
        if score >= 97:
            break
    if best_score >= VERIFIED_SCORE:
        return best_page, True
    return hint_page, False
