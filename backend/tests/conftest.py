from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import llm
from app.core import db as dbmod
from app.core import storage
from app.core.config import Settings
from app.main import app
from app.workers import tasks

ClientFactory = Callable[[Callable[..., Any]], TestClient]


def make_pdf(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        doc.new_page().insert_textbox(fitz.Rect(50, 50, 550, 800), text, fontsize=11)
    data: bytes = doc.tobytes()
    return data


@pytest.fixture
def client_with(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ClientFactory]:
    """API client on in-memory SQLite and local storage, with the model replaced by `fake`."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(dbmod, "engine", engine)
    monkeypatch.setattr(dbmod, "SessionLocal", sessions)
    monkeypatch.setattr(tasks, "SessionLocal", sessions)
    settings = Settings(local_storage_dir=str(tmp_path), _env_file=None)
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    # Run Celery tasks inline.
    for task in (tasks.process_package, tasks.extract_requirements, tasks.check_run):
        monkeypatch.setattr(task, "delay", task)
    clients: list[TestClient] = []

    def factory(fake: Callable[..., Any]) -> TestClient:
        monkeypatch.setattr(llm, "ask", fake)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)
