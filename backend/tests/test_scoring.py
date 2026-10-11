from app.pipeline.scoring import Item, forecast, impact, score

# Test vector from docs/PIPELINE.md §6.5
ITEMS = [
    Item("T-012", "product", "technical", "mandatory", "match"),
    Item("T-014", "product", "technical", "mandatory", "mismatch"),
    Item("T-019", "product", "documents", "mandatory", "unconfirmed"),
    Item("U-003", "participant", "qualification", "rated", "partial", rated_points=10),
    Item("T-020", "product", "technical", "desired", "match"),
    Item("U-007", "participant", "documents", "mandatory", "review"),
]


def test_score_vector() -> None:
    result = score(ITEMS)

    assert result["total"] == 49.2
    assert result["total_min"] == 39.3
    assert result["total_max"] == 59.3
    assert result["mandatory_done"] == 1
    assert result["mandatory_total"] == 4
    assert result["verdict"] == "rejection_risk"
    assert result["problems"] == 4


def test_impact_and_forecast() -> None:
    assert impact(ITEMS, "T-014") == 25.0
    assert forecast(ITEMS, {"T-014", "T-019", "U-003"}) == 100.0


def test_verdicts() -> None:
    ready = [Item("T-1", "product", "technical", "mandatory", "match"),
             Item("T-2", "product", "technical", "rated", "mismatch")]  # fmt: skip
    needs_work = [*ready, Item("U-1", "participant", "documents", "mandatory", "review")]

    assert score(ready)["verdict"] == "ready"
    assert score(needs_work)["verdict"] == "needs_work"
