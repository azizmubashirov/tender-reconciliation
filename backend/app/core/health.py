import asyncio
import time
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.storage import make_s3_client
from app.schemas.health import ComponentStatus

CHECK_TIMEOUT_S = 3.0


class CheckSkippedError(Exception):
    """The component is intentionally not configured in this environment."""


def _ping_postgres() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


async def check_postgres() -> None:
    await asyncio.to_thread(_ping_postgres)


async def check_redis() -> None:
    client = Redis.from_url(get_settings().redis_url)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def check_object_storage() -> None:
    settings = get_settings()
    if not settings.s3_configured:
        # Local development may start before an R2 dev bucket exists; elsewhere it is a hard error.
        if settings.env == "local":
            raise CheckSkippedError("R2 credentials are not set, using local storage")
        raise RuntimeError("R2 credentials are not set")
    client = make_s3_client(settings, timeout_s=CHECK_TIMEOUT_S)
    await asyncio.to_thread(client.head_bucket, Bucket=settings.s3_bucket)


async def check_llm() -> None:
    if not get_settings().llm_configured:
        raise CheckSkippedError("No Claude key (ANTHROPIC_API_KEY or CLOUDFLARE_API_TOKEN)")


CHECKS: dict[str, Callable[[], Awaitable[None]]] = {
    "postgres": check_postgres,
    "redis": check_redis,
    "object_storage": check_object_storage,
    "llm": check_llm,
}


async def run_checks() -> dict[str, ComponentStatus]:
    names = list(CHECKS)
    results = await asyncio.gather(*(_run_check(CHECKS[name]) for name in names))
    return dict(zip(names, results, strict=True))


async def _run_check(check: Callable[[], Awaitable[None]]) -> ComponentStatus:
    started = time.perf_counter()

    def elapsed_ms() -> float:
        return round((time.perf_counter() - started) * 1000, 1)

    try:
        await asyncio.wait_for(check(), CHECK_TIMEOUT_S)
    except CheckSkippedError as exc:
        return ComponentStatus(status="skipped", latency_ms=elapsed_ms(), detail=str(exc))
    except Exception as exc:
        return ComponentStatus(status="error", latency_ms=elapsed_ms(), detail=_describe(exc))
    return ComponentStatus(status="ok", latency_ms=elapsed_ms())


def _describe(exc: Exception) -> str:
    # Messages can reveal hostnames or credential hints, so only the local environment shows them.
    name = type(exc).__name__
    if get_settings().env == "local" and str(exc):
        return f"{name}: {exc}"
    return name
