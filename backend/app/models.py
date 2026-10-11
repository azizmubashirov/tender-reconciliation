from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

JsonList = list[dict[str, Any]]


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    customer_name: Mapped[str | None]
    lot_number: Mapped[str | None]
    submission_deadline: Mapped[date | None]
    report_language: Mapped[str] = mapped_column(String(2), default="ru")
    # new | extracting | extracted | failed: state of requirement extraction
    status: Mapped[str] = mapped_column(String(20), default="new")
    error: Mapped[str | None] = mapped_column(Text)
    checklist_approved: Mapped[bool] = mapped_column(default=False)
    lot_positions: Mapped[JsonList] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    packages: Mapped[list["Package"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Package.id"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        cascade="all, delete-orphan", order_by="Requirement.sort_index"
    )
    issues: Mapped[list["Issue"]] = relationship(cascade="all, delete-orphan")
    runs: Mapped[list["Run"]] = relationship(cascade="all, delete-orphan", order_by="Run.id")


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))  # customer | bid
    participant_name: Mapped[str | None]
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="packages")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="package", cascade="all, delete-orphan", order_by="Document.id"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str]
    # Normalized content sent to the model: a PDF (pdf_key) or plain text (spreadsheets).
    pdf_key: Mapped[str | None]
    text_content: Mapped[str | None] = mapped_column(Text)
    page_texts: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_count: Mapped[int] = mapped_column(default=0)
    doc_type: Mapped[str | None]
    info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | ready | failed
    error: Mapped[str | None] = mapped_column(Text)

    package: Mapped[Package] = relationship(back_populates="documents")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(10))  # T-014 (product) / U-007 (participant)
    scope: Mapped[str] = mapped_column(String(12))  # product | participant
    category: Mapped[str] = mapped_column(String(30))
    lot_position: Mapped[int | None]
    parameter: Mapped[str] = mapped_column(Text)
    parameter_key: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(20))
    value: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None]
    req_type: Mapped[str] = mapped_column(String(10))  # mandatory | rated | desired
    rated_points: Mapped[float | None]
    proof_documents: Mapped[list[str]] = mapped_column(JSON, default=list)
    consequence: Mapped[str] = mapped_column(String(20), default="unknown")
    equivalent_allowed: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[JsonList] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String(10), default="ai")  # ai | user
    sort_index: Mapped[int] = mapped_column(default=0)


class Issue(Base):
    """Questions to the customer: contradictions, ambiguities, restrictive requirements."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # contradiction | ambiguity | restrictive
    description: Mapped[str] = mapped_column(Text)
    sources: Mapped[JsonList] = mapped_column(JSON, default=list)


class Run(Base):
    """One compliance check of a bid package against the approved checklist."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|failed
    stage: Mapped[str | None]
    error: Mapped[str | None] = mapped_column(Text)
    score: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]

    package: Mapped[Package] = relationship()
    facts: Mapped[list["Fact"]] = relationship(cascade="all, delete-orphan")
    matches: Mapped[list["Match"]] = relationship(cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship(cascade="all, delete-orphan")


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    value: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None]
    page: Mapped[int | None]
    quote: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool | None]
    source_rank: Mapped[int] = mapped_column(default=2)

    document: Mapped[Document] = relationship()


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    # match | partial | unconfirmed | mismatch | review
    status: Mapped[str] = mapped_column(String(12))
    ai_status: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(10))  # rule | llm | manual
    reasoning: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[JsonList] = mapped_column(JSON, default=list)
    comment: Mapped[str | None] = mapped_column(Text)

    requirement: Mapped[Requirement] = relationship()


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"))
    problem: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    # add_document | fix_data | replace_product | request_clarification | unfixable
    action_type: Mapped[str] = mapped_column(String(25))
    severity: Mapped[str] = mapped_column(String(10))  # high | medium | low
    impact: Mapped[float] = mapped_column(default=0)
    done: Mapped[bool] = mapped_column(default=False)

    requirement: Mapped[Requirement] = relationship()
