from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.projects import _get
from app.core.db import get_db
from app.models import Match, Package, Project, Recommendation, Run
from app.pipeline.check import rescore
from app.pipeline.report import build_pdf, build_xlsx, sorted_matches, sorted_recommendations
from app.schemas.api import (
    MatchOut,
    MatchPatch,
    RecommendationOut,
    RecommendationPatch,
    RunIn,
    RunOut,
)
from app.workers import tasks

router = APIRouter(tags=["runs"])
Db = Annotated[Session, Depends(get_db)]


def _rec_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        requirement_id=rec.requirement_id,
        problem=rec.problem,
        action=rec.action,
        action_type=rec.action_type,
        severity=rec.severity,
        impact=rec.impact,
        done=rec.done,
        code=rec.requirement.code,
        parameter=rec.requirement.parameter,
    )


@router.post("/projects/{project_id}/runs", response_model=RunOut, status_code=201)
def start_run(project_id: int, body: RunIn, db: Db) -> Run:
    project = _get(db, Project, project_id)
    package = _get(db, Package, body.package_id)
    if not project.checklist_approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Сначала утвердите чек-лист")
    if package.project_id != project.id or package.kind != "bid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Это не пакет заявки этого проекта")
    if package.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Пакет заявки ещё не обработан")
    run = Run(project_id=project.id, package_id=package.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    tasks.check_run.delay(run.id)
    return run


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: int, db: Db) -> Run:
    return _get(db, Run, run_id)


@router.get("/runs/{run_id}/matches", response_model=list[MatchOut])
def list_matches(run_id: int, db: Db) -> list[Match]:
    return sorted_matches(_get(db, Run, run_id))


@router.patch("/matches/{match_id}", response_model=MatchOut)
def override_match(match_id: int, body: MatchPatch, db: Db) -> Match:
    """Manual status change: logged in the match and counted in the score (TZ §6)."""
    match = _get(db, Match, match_id)
    run = _get(db, Run, match.run_id)
    match.status, match.method, match.comment = body.status, "manual", body.comment
    rescore(run, _get(db, Project, run.project_id).report_language)
    db.commit()
    return match


@router.get("/runs/{run_id}/recommendations", response_model=list[RecommendationOut])
def list_recommendations(run_id: int, db: Db) -> list[RecommendationOut]:
    return [_rec_out(r) for r in sorted_recommendations(_get(db, Run, run_id))]


@router.patch("/recommendations/{rec_id}", response_model=RecommendationOut)
def update_recommendation(rec_id: int, body: RecommendationPatch, db: Db) -> RecommendationOut:
    rec = _get(db, Recommendation, rec_id)
    rec.done = body.done
    db.commit()
    return _rec_out(rec)


def _report_run(db: Session, run_id: int) -> tuple[Project, Run]:
    run = _get(db, Run, run_id)
    if run.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "Проверка ещё не завершена")
    return _get(db, Project, run.project_id), run


@router.get("/runs/{run_id}/report.pdf")
def report_pdf(run_id: int, db: Db) -> Response:
    project, run = _report_run(db, run_id)
    return Response(
        build_pdf(project, run),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{run.id}.pdf"'},
    )


@router.get("/runs/{run_id}/report.xlsx")
def report_xlsx(run_id: int, db: Db) -> Response:
    project, run = _report_run(db, run_id)
    return Response(
        build_xlsx(project, run),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="report-{run.id}.xlsx"'},
    )
