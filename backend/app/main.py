from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import health, projects, runs
from app.core.db import engine, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Тендер-Сверка API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    for module in (health, projects, runs):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
