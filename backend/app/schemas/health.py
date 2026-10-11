from typing import Literal

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    status: Literal["ok", "error", "skipped"]
    latency_ms: float
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    components: dict[str, ComponentStatus]
