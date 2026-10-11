import pytest

from app.pipeline.rules import evaluate, parse_numbers


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
