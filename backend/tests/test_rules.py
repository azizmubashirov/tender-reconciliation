import pytest

from app.pipeline.rules import evaluate, parse_numbers, resolve_unit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("16", [16.0]),
        ("16,5 ГБ", [16.5]),
        ("1 000 000 сум", [1000000.0]),
        ("8-16", [8.0, 16.0]),
        ("−20…+40", [-20.0, 40.0]),
        ("от -10 до 50", [-10.0, 50.0]),
        ("220±10%", [220.0]),
        (None, []),
    ],
)
def test_parse_numbers(text: str | None, expected: list[float]) -> None:
    assert parse_numbers(text) == expected


@pytest.mark.parametrize(
    ("operator", "req", "req_unit", "fact", "fact_unit", "outcome"),
    [
        ("gte", "16", "ГБ", "16 GB", None, "pass"),
        ("gte", "16", "ГБ", "1", "TB", "pass"),
        ("gte", "36", "мес", "24 months", None, "fail"),
        ("gte", "3", "года", "36", "мес", "pass"),
        ("lte", "2", "кг", "1800", "г", "pass"),
        ("lte", "2", "кг", "2.5 kg", None, "fail"),
        ("eq", "220±10%", "В", "230", "V", "pass"),
        ("eq", "220±10%", "В", "250", "V", "fail"),
        ("range_within", "14-16", "дюйм", "15.6", "inch", "pass"),
        ("range_covers", "-20..+40", "°C", "-30…+50", "°C", "pass"),
        ("range_covers", "-20..+40", "°C", "0…+50", "°C", "fail"),
        ("gte", "16", "ГБ", "16", "кг", "unknown"),
        ("gte", "16", "ГБ", "есть", None, "unknown"),
        ("text", "антикоррозийное", None, "есть", None, "unknown"),
    ],
)
def test_evaluate(
    operator: str, req: str, req_unit: str | None, fact: str, fact_unit: str | None, outcome: str
) -> None:
    assert evaluate(operator, req, req_unit, fact, fact_unit).outcome == outcome


def test_detail_is_in_requirement_units() -> None:
    result = evaluate("gte", "36", "мес", "2", "года")
    assert result.outcome == "fail"
    assert result.detail == "24 мес < 36 мес"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("№ 462945631", []),  # certificate number, not a quantity
        ("Лицензия № 1555033 от 01.05.2026", []),
        ("от 2026-05-01, 3 шт", [3.0]),
        ("150 112 592.00 сум", [150112592.0]),
    ],
)
def test_identifiers_are_not_numbers(text: str, expected: list[float]) -> None:
    assert parse_numbers(text) == expected


@pytest.mark.parametrize(
    ("unit", "value", "expected"),
    [
        ("mln so'm", None, ("money", 1e6)),
        ("mln so‘m", None, ("money", 1e6)),
        ("so‘m (QQS bilan)", None, ("money", 1.0)),
        (None, "2 млрд сум", ("money", 1e9)),
        ("тыс. сум", None, ("money", 1e3)),
        ("млн", None, ("money", 1e6)),
        ("ball", None, ("points", 1.0)),
        ("xodim", None, ("count", 1.0)),
        ("soat", None, ("duration", 1 / 720)),
        ("4K", None, None),
    ],
)
def test_resolve_unit(unit: str | None, value: str | None, expected: object) -> None:
    assert resolve_unit(unit, value) == expected


@pytest.mark.parametrize(
    ("operator", "req", "req_unit", "fact", "fact_unit", "outcome"),
    [
        # 150 mln is not "more than 500 mln" (was compared as raw numbers before).
        ("gte", "500", "mln so'm", "150 112 592.00 сум", None, "fail"),
        ("gte", "500", "mln so'm", "620 000 000", "сум", "pass"),
        ("lte", "120 000 000", "so‘m (QQS bilan)", "118,5", "млн сум", "pass"),
        # A bare amount against "mln": magnitude unknown, the model decides.
        ("gte", "500", "mln so'm", "150 112 592", None, "unknown"),
        ("lte", "24", "soat", "1", "день", "pass"),
        ("lte", "7", "kun", "7 дней", None, "pass"),
        ("gte", "1", "xodim", "№ 462945631", None, "unknown"),
        ("gte", "3", "dona", "3 шт", None, "pass"),
        ("gte", "11", "ball", "8 баллов", None, "fail"),
    ],
)
def test_evaluate_tender_units(
    operator: str, req: str, req_unit: str | None, fact: str, fact_unit: str | None, outcome: str
) -> None:
    assert evaluate(operator, req, req_unit, fact, fact_unit).outcome == outcome


def test_money_detail_is_in_requirement_scale() -> None:
    result = evaluate("gte", "500", "mln so'm", "150 112 592.00 сум", None)
    assert result.detail == "150.113 mln so'm < 500 mln so'm"
