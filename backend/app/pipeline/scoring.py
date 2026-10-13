"""Compliance score and verdict (TZ §7, docs/PIPELINE.md §6). Pure functions, no model involved."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

K = {"match": 1.0, "partial": 0.5, "unconfirmed": 0.3, "mismatch": 0.0}
W = {"mandatory": 3.0, "rated": 2.0, "desired": 1.0}
PROBLEM_STATUSES = ("partial", "unconfirmed", "mismatch", "review")
# "na": the requirement does not apply to this procurement; it is left out of every number.
NOT_APPLICABLE = "na"


@dataclass(frozen=True)
class Item:
    code: str
    scope: str
    category: str
    req_type: str
    status: str
    rated_points: float | None = None
    points: float | None = None  # points earned on the official scale, when known


def _applicable(items: Iterable[Item]) -> list[Item]:
    return [i for i in items if i.status != NOT_APPLICABLE]


def weights(items: Iterable[Item]) -> dict[str, float]:
    """Default weights; rated items share 2·n_rated in proportion to their official points."""
    items = list(items)
    rated = [i for i in items if i.req_type == "rated"]
    points = [i.rated_points for i in rated if i.rated_points]
    result = {i.code: W.get(i.req_type, 1.0) for i in items}
    if rated and len(points) == len(rated):
        total = sum(points)
        for item in rated:
            assert item.rated_points is not None
            result[item.code] = 2 * len(rated) * item.rated_points / total
    return result


def _percent(items: list[Item], w: dict[str, float], review_k: float | None) -> float | None:
    num = den = 0.0
    for item in _applicable(items):
        if item.status == "review":
            if review_k is None:
                continue
            k = review_k
        else:
            k = K[item.status]
        num += w[item.code] * k
        den += w[item.code]
    return round(num / den * 100, 1) if den else None


def points(items: Iterable[Item], min_pass: float | None = None) -> dict[str, Any] | None:
    """Range of evaluation points the bid gets: unresolved items count as 0 (min) or full (max)."""
    rated = [i for i in _applicable(items) if i.req_type == "rated" and i.rated_points]
    if not rated:
        return None
    low = high = total = 0.0
    for item in rated:
        assert item.rated_points is not None
        total += item.rated_points
        if item.points is not None:
            earned = max(0.0, min(item.points, item.rated_points))
            low, high = low + earned, high + earned
        elif item.status == "match":
            low, high = low + item.rated_points, high + item.rated_points
        elif item.status != "mismatch":
            high += item.rated_points
    passed = None
    if min_pass is not None:
        passed = True if low >= min_pass else False if high < min_pass else None
    return {
        "min": round(low, 2),
        "max": round(high, 2),
        "total": round(total, 2),
        "pass": min_pass,
        "passed": passed,
    }


def verdict(items: Iterable[Item], passed: bool | None = True) -> str:
    """passed: whether the evaluation points reach the passing score (None when undecided)."""
    mandatory = [i for i in _applicable(items) if i.req_type == "mandatory"]
    failed = any(i.status in ("mismatch", "unconfirmed", "partial") for i in mandatory)
    if passed is False or failed:
        return "rejection_risk"
    if passed is None or any(i.status == "review" for i in mandatory):
        return "needs_work"
    return "ready"


def score(items: Iterable[Item], min_pass: float | None = None) -> dict[str, Any]:
    items = list(items)
    w = weights(_applicable(items))
    mandatory = [i for i in _applicable(items) if i.req_type == "mandatory"]
    categories = sorted({i.category for i in _applicable(items)})
    earned = points(items, min_pass)
    return {
        "total": _percent(items, w, None),
        "total_min": _percent(items, w, 0.0),
        "total_max": _percent(items, w, 1.0),
        "product": _percent([i for i in items if i.scope == "product"], w, None),
        "participant": _percent([i for i in items if i.scope == "participant"], w, None),
        "categories": {
            c: _percent([i for i in items if i.category == c], w, None) for c in categories
        },
        "mandatory_done": sum(1 for i in mandatory if i.status == "match"),
        "mandatory_total": len(mandatory),
        "counts": {s: sum(1 for i in items if i.status == s) for s in (*K, "review", "na")},
        "problems": sum(1 for i in items if i.status in PROBLEM_STATUSES),
        "points": earned,
        "verdict": verdict(items, earned["passed"] if earned and min_pass is not None else True),
    }


def impact(items: list[Item], code: str) -> float:
    """How many percentage points the total gains if this item becomes compliant."""
    w = weights(_applicable(items))
    before = _percent(items, w, None) or 0.0
    fixed = [replace(i, status="match") if i.code == code else i for i in items]
    after = _percent(fixed, w, None) or 0.0
    return round(after - before, 1)


def forecast(items: list[Item], fixable: set[str]) -> float | None:
    w = weights(_applicable(items))
    fixed = [replace(i, status="match") if i.code in fixable else i for i in items]
    return _percent(fixed, w, None)
