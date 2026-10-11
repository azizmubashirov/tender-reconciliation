import logging
from datetime import datetime

from app.core.db import SessionLocal
from app.models import Package, Project, Run
from app.pipeline.check import run_check
from app.pipeline.extract import run_extraction
from app.pipeline.ingest import normalize_documents
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="package.process", queue="ingest")
def process_package(package_id: int) -> None:
    with SessionLocal() as db:
        package = db.get(Package, package_id)
        if package is None:
            return
        try:
            normalize_documents(db, package)
            package.status = "ready"
            db.commit()
        except Exception as exc:
            log.exception("package %s failed", package_id)
            db.rollback()
            package.status, package.error = "failed", str(exc)
            db.commit()
            return
        if package.kind == "customer":
            extract_requirements.delay(package.project_id)


@celery_app.task(name="project.extract", queue="llm")
def extract_requirements(project_id: int) -> None:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if project is None:
            return
        project.status, project.error = "extracting", None
        db.commit()
        try:
            run_extraction(db, project)
        except Exception as exc:
            log.exception("extraction for project %s failed", project_id)
            db.rollback()
            project.status, project.error = "failed", str(exc)
            db.commit()


@celery_app.task(name="run.check", queue="llm")
def check_run(run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return
        try:
            run_check(db, run)
        except Exception as exc:
            log.exception("run %s failed", run_id)
            db.rollback()
            run.status, run.error, run.finished_at = "failed", str(exc), datetime.now()
            db.commit()
