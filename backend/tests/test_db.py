from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.core.db import Base, add_missing_columns


def test_new_columns_are_added_to_existing_tables(tmp_path: Path) -> None:
    from app import models  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:  # a database created before the columns existed
        conn.execute(text('ALTER TABLE "matches" DROP COLUMN "points"'))
        conn.execute(text('ALTER TABLE "projects" DROP COLUMN "min_pass_score"'))

    assert sorted(add_missing_columns(engine)) == ["matches.points", "projects.min_pass_score"]
    columns = {c["name"] for c in inspect(engine).get_columns("matches")}
    assert "points" in columns
    assert add_missing_columns(engine) == []
