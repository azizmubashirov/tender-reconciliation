"""Claude structured outputs reject schemas with more than 16 nullable/union fields (HTTP 400).

The limit counts every `anyOf` / type array in the schema sent to the API, so it is checked on
the exact schema the SDK builds from each response model.
"""

from typing import Any

import pytest
from anthropic.lib._parse._transform import transform_schema
from pydantic import BaseModel

from app.schemas.llm import (
    BidDocResult,
    CustomerDocResult,
    JudgeResult,
    ReportResult,
    SummaryResult,
)

MAX_UNION_FIELDS = 16
MAX_OPTIONAL_FIELDS = 24


def _count(node: Any, key: str) -> int:
    if isinstance(node, list):
        return sum(_count(item, key) for item in node)
    if not isinstance(node, dict):
        return 0
    own = 0
    if key == "union":
        own = int("anyOf" in node or isinstance(node.get("type"), list))
    elif key == "optional" and node.get("type") == "object":
        own = len(set(node.get("properties", {})) - set(node.get("required", [])))
    return own + sum(_count(value, key) for value in node.values())


@pytest.mark.parametrize(
    "model", [CustomerDocResult, BidDocResult, JudgeResult, ReportResult, SummaryResult]
)
def test_schema_fits_structured_output_limits(model: type[BaseModel]) -> None:
    schema = transform_schema(model)
    assert _count(schema, "union") <= MAX_UNION_FIELDS
    assert _count(schema, "optional") <= MAX_OPTIONAL_FIELDS
