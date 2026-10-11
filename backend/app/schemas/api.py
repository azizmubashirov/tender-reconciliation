from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Language = Literal["ru", "uz", "en"]
Status = Literal["match", "partial", "unconfirmed", "mismatch", "review"]


class Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectIn(BaseModel):
    title: str
    report_language: Language = "ru"


class ProjectPatch(BaseModel):
    title: str | None = None
    customer_name: str | None = None
    lot_number: str | None = None
    submission_deadline: date | None = None
    report_language: Language | None = None


class DocumentOut(Orm):
    id: int
    filename: str
    page_count: int
    doc_type: str | None
    status: str
    error: str | None
    info: dict[str, Any]


class PackageIn(BaseModel):
    kind: Literal["customer", "bid"]
    participant_name: str | None = None


class PackageOut(Orm):
    id: int
    kind: str
    participant_name: str | None
    status: str
    error: str | None
    created_at: datetime
    documents: list[DocumentOut]


class RunBrief(Orm):
    id: int
    package_id: int
    status: str
    stage: str | None
    error: str | None
    score: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


class RunOut(RunBrief):
    summary: str | None


class ProjectOut(Orm):
    id: int
    title: str
    customer_name: str | None
    lot_number: str | None
    submission_deadline: date | None
    report_language: str
    status: str
    error: str | None
    checklist_approved: bool
    lot_positions: list[dict[str, Any]]
    created_at: datetime
    packages: list[PackageOut]
    runs: list[RunBrief]


class ProjectListItem(BaseModel):
    id: int
    title: str
    customer_name: str | None
    lot_number: str | None
    submission_deadline: date | None
    status: str
    checklist_approved: bool
    created_at: datetime
    score: float | None
    verdict: str | None


class RequirementBase(BaseModel):
    scope: Literal["product", "participant"]
    category: Literal["technical", "documents", "qualification", "commercial"]
    lot_position: int | None = None
    parameter: str
    operator: Literal["gte", "lte", "eq", "range_within", "range_covers", "exists", "text"]
    value: str | None = None
    unit: str | None = None
    req_type: Literal["mandatory", "rated", "desired"]
    rated_points: float | None = None
    proof_documents: list[str] = []
    note: str | None = None


class RequirementIn(RequirementBase):
    pass


class RequirementPatch(BaseModel):
    scope: Literal["product", "participant"] | None = None
    category: Literal["technical", "documents", "qualification", "commercial"] | None = None
    lot_position: int | None = None
    parameter: str | None = None
    operator: (
        Literal["gte", "lte", "eq", "range_within", "range_covers", "exists", "text"] | None
    ) = None
    value: str | None = None
    unit: str | None = None
    req_type: Literal["mandatory", "rated", "desired"] | None = None
    rated_points: float | None = None
    proof_documents: list[str] | None = None
    note: str | None = None


class RequirementOut(RequirementBase, Orm):
    id: int
    code: str
    parameter_key: str
    consequence: str
    equivalent_allowed: bool
    sources: list[dict[str, Any]]
    origin: str


class IssueOut(Orm):
    id: int
    kind: str
    description: str
    sources: list[dict[str, Any]]


class RunIn(BaseModel):
    package_id: int


class MatchOut(Orm):
    id: int
    status: str
    ai_status: str
    method: str
    reasoning: str
    evidence: list[dict[str, Any]]
    comment: str | None
    requirement: RequirementOut


class MatchPatch(BaseModel):
    status: Status
    comment: str


class RecommendationOut(Orm):
    id: int
    requirement_id: int
    problem: str
    action: str
    action_type: str
    severity: str
    impact: float
    done: bool
    code: str
    parameter: str


class RecommendationPatch(BaseModel):
    done: bool
