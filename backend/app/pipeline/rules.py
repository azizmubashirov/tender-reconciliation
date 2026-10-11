"""Deterministic comparison of numeric requirements: numbers, units, operators (TZ §6).

Numbers are never compared by the model; this module decides pass/fail once both sides parse.
"""

import re
from dataclasses import dataclass
from typing import Literal

# alias -> (dimension, factor to the dimension's canonical unit)
_UNIT_TABLE: dict[str, tuple[str, float]] = {}


def _units(dimension: str, factor: float, *aliases: str) -> None:
    for alias in aliases:
        _UNIT_TABLE[alias] = (dimension, factor)


_units("data", 1024, "тб", "tb", "tbayt", "терабайт")
_units("data", 1, "гб", "gb", "gbayt", "гигабайт", "gib")
_units("data", 1 / 1024, "мб", "mb", "mbayt", "мегабайт", "mib")
_units("duration", 12, "год", "года", "лет", "yil", "year", "years", "г")
_units("duration", 1, "мес", "месяц", "месяца", "месяцев", "oy", "month", "months")
_units("duration", 7 / 30, "нед", "недели", "недель", "неделя", "hafta", "week", "weeks")
_units("duration", 1 / 30, "день", "дня", "дней", "дн", "kun", "day", "days")
_units("power", 1000, "квт", "kw")
_units("power", 1, "вт", "w")
_units("voltage", 1000, "кв", "kv")
_units("voltage", 1, "в", "v")
_units("frequency", 1e9, "ггц", "ghz")
_units("frequency", 1e6, "мгц", "mhz")
_units("frequency", 1e3, "кгц", "khz")
_units("frequency", 1, "гц", "hz")
_units("length", 1000, "м", "m", "metr")
_units("length", 10, "см", "cm", "sm")
_units("length", 1, "мм", "mm")
_units("length", 25.4, "дюйм", "дюйма", "дюймов", "inch", "inches", '"', "″", "dyuym")
_units("mass", 1000, "т", "t", "tonna")
_units("mass", 1, "кг", "kg")
_units("mass", 0.001, "г", "g", "gr", "gramm")
_units("temperature", 1, "°c", "°с", "c", "с", "град", "градусов")
_units("count", 1, "шт", "штук", "dona", "pcs", "pc", "ед", "единиц")
_units("percent", 1, "%", "процент", "foiz")
_units("dpi", 1, "dpi", "точек/дюйм")
_units("cores", 1, "ядер", "ядра", "core", "cores", "yadro")
# "г" is ambiguous (год vs грамм); mass wins only when it is the explicit mass alias above.
_UNIT_TABLE["г"] = ("mass", 0.001)

_NUMBER = re.compile(r"(?<![\d.,])[-−+]?\d+(?:[.,]\d+)?")
_THOUSANDS = re.compile(r"(\d)[\s  ](\d{3})(?!\d)")
_TOLERANCE = re.compile(r"[±]\s*(\d+(?:[.,]\d+)?)\s*(%?)")


def _to_float(token: str) -> float:
    return float(token.replace("−", "-").replace(",", "."))


def parse_numbers(text: str | None) -> list[float]:
    if not text:
        return []
    cleaned = _TOLERANCE.sub(" ", text)
    while _THOUSANDS.search(cleaned):
        cleaned = _THOUSANDS.sub(r"\1\2", cleaned)
    return [_to_float(t) for t in _NUMBER.findall(cleaned)]


def parse_tolerance(text: str | None, base: float) -> float:
    match = _TOLERANCE.search(text or "")
    if not match:
        return abs(base) * 1e-9
    amount = _to_float(match.group(1))
    return abs(base) * amount / 100 if match.group(2) else amount


def resolve_unit(unit: str | None, value_text: str | None = None) -> tuple[str, float] | None:
    """Find the unit either in the explicit unit field or in the value text ("16 ГБ")."""
    for candidate in (unit, value_text):
        if not candidate:
            continue
        for token in re.findall(r"[^\d\s.,±\-−+()]+", candidate.lower()):
            token = token.strip(".")
            if token in _UNIT_TABLE:
                return _UNIT_TABLE[token]
    return None


@dataclass(frozen=True)
class RuleResult:
    outcome: Literal["pass", "fail", "unknown"]
    detail: str


def _fmt(value: float) -> str:
    return f"{value:g}"


def _convert(values: list[float], dimension: str, factor: float) -> list[float]:
    if dimension == "temperature":
        return values
    return [v * factor for v in values]


def evaluate(
    operator: str,
    req_value: str | None,
    req_unit: str | None,
    fact_value: str | None,
    fact_unit: str | None,
) -> RuleResult:
    req_nums = parse_numbers(req_value)
    fact_nums = parse_numbers(fact_value)
    if not req_nums or not fact_nums:
        return RuleResult("unknown", "значение не распознано как число")

    req_u = resolve_unit(req_unit, req_value)
    fact_u = resolve_unit(fact_unit, fact_value)
    if req_u and fact_u:
        if req_u[0] != fact_u[0]:
            return RuleResult("unknown", "несовместимые единицы измерения")
        req_nums = _convert(req_nums, *req_u)
        fact_nums = _convert(fact_nums, *fact_u)
        if fact_u[0] == "temperature" and "f" in (fact_unit or "").lower():
            fact_nums = [(f - 32) * 5 / 9 for f in fact_nums]
        scale = req_u[1] if req_u[0] != "temperature" else 1
    elif req_u or fact_u:
        # Only one side names a unit: assume both use it (typical for "16" vs "16 ГБ").
        scale = 1
    else:
        scale = 1

    label = (req_unit or "").strip()

    def show(v: float) -> str:
        return f"{_fmt(v / scale)} {label}".strip()

    fact, req = fact_nums[0], req_nums[0]
    if operator == "gte":
        ok = fact >= req
        return RuleResult(
            "pass" if ok else "fail", f"{show(fact)} {'≥' if ok else '<'} {show(req)}"
        )
    if operator == "lte":
        ok = fact <= req
        return RuleResult(
            "pass" if ok else "fail", f"{show(fact)} {'≤' if ok else '>'} {show(req)}"
        )
    if operator == "eq":
        tol = parse_tolerance(req_value, req) * (scale if req_u else 1)
        ok = abs(fact - req) <= tol
        return RuleResult(
            "pass" if ok else "fail", f"{show(fact)} {'=' if ok else '≠'} {show(req)}"
        )
    if operator in ("range_within", "range_covers"):
        if len(req_nums) < 2:
            return RuleResult("unknown", "диапазон в требовании не распознан")
        lo, hi = sorted(req_nums[:2])
        if operator == "range_within":
            f_lo, f_hi = sorted(fact_nums[:2]) if len(fact_nums) >= 2 else (fact, fact)
            ok = lo <= f_lo and f_hi <= hi
        else:
            if len(fact_nums) < 2:
                return RuleResult("unknown", "в заявке указано одно значение, а не диапазон")
            f_lo, f_hi = sorted(fact_nums[:2])
            ok = f_lo <= lo and f_hi >= hi
        fact_text = show(f_lo) if f_lo == f_hi else f"{show(f_lo)}…{show(f_hi)}"
        verdict = "входит в" if operator == "range_within" else "покрывает"
        sign = "" if ok else "не "
        return RuleResult(
            "pass" if ok else "fail", f"{fact_text} {sign}{verdict} {show(lo)}…{show(hi)}"
        )
    return RuleResult("unknown", f"оператор {operator} сравнивается моделью")


NUMERIC_OPERATORS = {"gte", "lte", "eq", "range_within", "range_covers"}
