from app.pipeline.scoring import Item, forecast, impact, points, score

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


def test_not_applicable_is_left_out() -> None:
    items = [
        Item("T-1", "product", "technical", "mandatory", "match"),
        Item("U-1", "participant", "documents", "mandatory", "na"),
        Item("U-2", "participant", "documents", "mandatory", "mismatch"),
    ]
    result = score(items)
    assert result["total"] == 50.0
    assert result["mandatory_total"] == 2
    assert result["counts"]["na"] == 1
    assert result["problems"] == 1
    # Without the mismatch the bid is ready: "na" never blocks it.
    assert score(items[:2])["verdict"] == "ready"


RATED = [
    Item("T-1", "product", "technical", "mandatory", "match"),
    Item("U-1", "participant", "qualification", "rated", "mismatch", rated_points=4),
    Item("U-2", "participant", "qualification", "rated", "match", rated_points=2),
    Item("U-3", "participant", "qualification", "rated", "mismatch", rated_points=3, points=1),
    Item("U-4", "participant", "qualification", "rated", "review", rated_points=1),
    Item("U-5", "participant", "technical", "rated", "match", rated_points=4, points=4),
]


def test_points_range() -> None:
    assert points(RATED) == {"min": 7, "max": 8, "total": 14, "pass": None, "passed": None}


def test_passing_score_decides_the_verdict() -> None:
    # 8 points at most: the bid cannot reach 11 even though no mandatory item fails.
    assert score(RATED, min_pass=11)["verdict"] == "rejection_risk"
    assert score(RATED, min_pass=11)["points"]["passed"] is False
    # 7..8 around a passing score of 8: depends on the item under review.
    assert score(RATED, min_pass=8)["verdict"] == "needs_work"
    assert score(RATED, min_pass=7)["verdict"] == "ready"
    assert score(RATED)["verdict"] == "ready"
