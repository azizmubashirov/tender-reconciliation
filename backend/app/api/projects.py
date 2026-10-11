import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.storage import get_bytes, put_bytes
from app.models import Document, Issue, Package, Project, Requirement
from app.pipeline.convert import SUPPORTED
from app.pipeline.extract import renumber
from app.pipeline.ingest import storage_prefix
from app.schemas.api import (
    IssueOut,
    PackageIn,
    PackageOut,
    ProjectIn,
    ProjectListItem,
    ProjectOut,
    ProjectPatch,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
)
from app.workers import tasks

router = APIRouter(tags=["projects"])
Db = Annotated[Session, Depends(get_db)]

MAX_FILES_PER_PACKAGE = 100
MAX_PACKAGE_BYTES = 500 * 1024 * 1024


def _get[T](db: Session, model: type[T], item_id: int) -> T:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} {item_id} not found")
    return item


def _editable(project: Project) -> None:
    if project.checklist_approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Чек-лист утверждён: сначала откройте его")


@router.get("/projects", response_model=list[ProjectListItem])
def list_projects(db: Db) -> list[ProjectListItem]:
    projects = db.scalars(select(Project).order_by(Project.id.desc())).all()
    items = []
    for p in projects:
        last = next((r for r in reversed(p.runs) if r.status == "done"), None)
        items.append(
            ProjectListItem(
                id=p.id,
                title=p.title,
                customer_name=p.customer_name,
                lot_number=p.lot_number,
                submission_deadline=p.submission_deadline,
                status=p.status,
                checklist_approved=p.checklist_approved,
                created_at=p.created_at,
                score=last.score.get("total") if last else None,
                verdict=last.score.get("verdict") if last else None,
            )
        )
    return items


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, db: Db) -> Project:
    project = Project(title=body.title, report_language=body.report_language)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Db) -> Project:
    return _get(db, Project, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, body: ProjectPatch, db: Db) -> Project:
    project = _get(db, Project, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Db) -> None:
    db.delete(_get(db, Project, project_id))
    db.commit()


@router.post("/projects/{project_id}/packages", response_model=PackageOut)
def create_package(project_id: int, body: PackageIn, db: Db) -> Package:
    project = _get(db, Project, project_id)
    if body.kind == "customer":
        existing = next((p for p in project.packages if p.kind == "customer"), None)
        if existing:
            return existing
    package = Package(project_id=project.id, kind=body.kind, participant_name=body.participant_name)
    db.add(package)
    db.commit()
    db.refresh(package)
    return package


@router.post("/packages/{package_id}/files", response_model=PackageOut)
def upload_files(package_id: int, files: Annotated[list[UploadFile], File()], db: Db) -> Package:
    package = _get(db, Package, package_id)
    if len(package.documents) + len(files) > MAX_FILES_PER_PACKAGE:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Не более 100 файлов в пакете")
    total = 0
    for upload in files:
        name = upload.filename or "file"
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"{name}: формат не поддерживается"
            )
        data = upload.file.read()
        total += len(data)
        if total > MAX_PACKAGE_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Пакет больше 500 МБ")
        key = f"{storage_prefix(package)}/original/{uuid.uuid4().hex}{suffix}"
        put_bytes(key, data)
        package.documents.append(Document(filename=name, storage_key=key))
    package.status = "new"
    db.commit()
    db.refresh(package)
    return package


@router.post("/packages/{package_id}/process", response_model=PackageOut)
def process_package(package_id: int, db: Db) -> Package:
    package = _get(db, Package, package_id)
    if package.kind == "customer":
        _editable(package.project)
        package.project.status = "extracting"
    if not package.documents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала загрузите файлы")
    package.status = "processing"
    db.commit()
    tasks.process_package.delay(package.id)
    return package


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Db) -> None:
    db.delete(_get(db, Document, document_id))
    db.commit()


@router.get("/documents/{document_id}/file")
def document_file(document_id: int, db: Db) -> Response:
    """The normalized PDF opens in the browser at a page via `#page=N`."""
    doc = _get(db, Document, document_id)
    if doc.pdf_key:
        return Response(get_bytes(doc.pdf_key), media_type="application/pdf")
    if doc.text_content is not None:
        return Response(doc.text_content, media_type="text/plain; charset=utf-8")
    return Response(get_bytes(doc.storage_key), media_type="application/octet-stream")


@router.get("/projects/{project_id}/requirements", response_model=list[RequirementOut])
def list_requirements(project_id: int, db: Db) -> list[Requirement]:
    project = _get(db, Project, project_id)
    return sorted(project.requirements, key=lambda r: (r.scope != "product", r.sort_index))


@router.post("/projects/{project_id}/requirements", response_model=RequirementOut)
def add_requirement(project_id: int, body: RequirementIn, db: Db) -> Requirement:
    project = _get(db, Project, project_id)
    _editable(project)
    prefix = "T" if body.scope == "product" else "U"
    count = sum(1 for r in project.requirements if r.scope == body.scope)
    req = Requirement(
        project_id=project.id,
        code=f"{prefix}-{count + 1:03d}",
        parameter_key=body.parameter.lower(),
        origin="user",
        sort_index=max((r.sort_index for r in project.requirements), default=0) + 1,
        **body.model_dump(),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def update_requirement(requirement_id: int, body: RequirementPatch, db: Db) -> Requirement:
    req = _get(db, Requirement, requirement_id)
    _editable(_get(db, Project, req.project_id))
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(req, field, value)
    db.commit()
    return req


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(requirement_id: int, db: Db) -> None:
    req = _get(db, Requirement, requirement_id)
    _editable(_get(db, Project, req.project_id))
    db.delete(req)
    db.commit()


@router.post("/projects/{project_id}/checklist/approve", response_model=ProjectOut)
def approve_checklist(project_id: int, db: Db) -> Project:
    project = _get(db, Project, project_id)
    if not project.requirements:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Чек-лист пуст")
    renumber(project)
    project.checklist_approved = True
    db.commit()
    return project


@router.post("/projects/{project_id}/checklist/reopen", response_model=ProjectOut)
def reopen_checklist(project_id: int, db: Db) -> Project:
    project = _get(db, Project, project_id)
    project.checklist_approved = False
    db.commit()
    return project


@router.get("/projects/{project_id}/issues", response_model=list[IssueOut])
def list_issues(project_id: int, db: Db) -> list[Issue]:
    return list(_get(db, Project, project_id).issues)
