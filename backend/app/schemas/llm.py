"""Structured outputs requested from the model. Field descriptions are part of the prompt."""

from typing import Literal

from pydantic import BaseModel, Field

CustomerDocType = Literal[
    "tender_documentation",
    "technical_specification",
    "specification",
    "qualification_requirements",
    "evaluation_criteria",
    "draft_contract",
    "forms",
    "clarification",
    "other",
]

BidDocType = Literal[
    "tech_proposal",
    "commercial_proposal",
    "product_passport",
    "manufacturer_catalog",
    "certificate",
    "declaration",
    "license",
    "reference_letter",
    "power_of_attorney",
    "authorization_letter",
    "experience_contract",
    "acceptance_act",
    "financial_statement",
    "company_registration",
    "bank_guarantee",
    "drawing",
    "marketing",
    "other",
]

Status = Literal["match", "partial", "unconfirmed", "mismatch", "review"]


class LotPositionOut(BaseModel):
    number: int
    name: str
    quantity: str | None
    unit: str | None


class ExtractedRequirement(BaseModel):
    scope: Literal["product", "participant"] = Field(
        description="product: the goods/works/services; participant: the bidder company"
    )
    category: Literal["technical", "documents", "qualification", "commercial"]
    lot_position: int | None = Field(description="Lot position number; null if it applies to all")
    parameter: str = Field(description="Parameter name in the document's language")
    parameter_key: str = Field(
        description="Canonical English snake_case key, identical across languages "
        "(мощность / quvvat / power -> power)"
    )
    operator: Literal["gte", "lte", "eq", "range_within", "range_covers", "exists", "text"] = Field(
        description="range_within: value must lie inside the range; range_covers: the offered "
        "range must cover the required one (operating temperature); exists: a document or "
        "property must be present; text: anything that is not a numeric comparison"
    )
    value: str | None = Field(
        description="Required value as written, e.g. '16', '-20..+40', '220±10%'"
    )
    unit: str | None
    req_type: Literal["mandatory", "rated", "desired"] = Field(
        description="mandatory leads to rejection; rated gives evaluation points; desired neither"
    )
    rated_points: float | None = Field(description="Evaluation points if the document gives them")
    proof_documents: list[BidDocType] = Field(description="Documents that must confirm it")
    consequence: Literal["rejection", "score_reduction", "none", "unknown"]
    equivalent_allowed: bool = Field(description="'или эквивалент' / 'yoki ekvivalent' is allowed")
    restrictive_note: str | None = Field(
        description="Set when the requirement may restrict competition (brand without "
        "'or equivalent', parameters unique to one manufacturer)"
    )
    page: int | None = Field(description="1-based page number inside this document")
    quote: str = Field(
        description="Verbatim excerpt from the document, 1-3 sentences, no translation"
    )


class CustomerIssueOut(BaseModel):
    kind: Literal["contradiction", "ambiguity", "restrictive"]
    description: str
    quote: str | None
    page: int | None


class CustomerDocResult(BaseModel):
    doc_type: CustomerDocType
    title: str | None
    customer_name: str | None
    lot_number: str | None
    submission_deadline: str | None = Field(description="Bid submission deadline, YYYY-MM-DD")
    lot_positions: list[LotPositionOut]
    requirements: list[ExtractedRequirement]
    issues: list[CustomerIssueOut]


class BidFactOut(BaseModel):
    requirement_code: str
    value: str | None = Field(description="Actual value as written in the document")
    unit: str | None
    page: int | None = Field(description="1-based page number inside this document")
    quote: str = Field(description="Verbatim excerpt that states the value, no translation")


class BidDocResult(BaseModel):
    doc_type: BidDocType
    title: str | None
    issuer: str | None
    doc_number: str | None
    doc_date: str | None = Field(description="YYYY-MM-DD")
    valid_until: str | None = Field(description="Expiry date, YYYY-MM-DD, if the document has one")
    has_signature: bool | None
    has_seal: bool | None
    participant_name: str | None
    participant_tin: str | None = Field(description="Bidder's TIN (STIR / ИНН) if present")
    facts: list[BidFactOut] = Field(
        description="Only requirements this document actually addresses"
    )


class VerdictOut(BaseModel):
    requirement_code: str
    status: Status
    reasoning: str = Field(description="1-2 sentences in the report language, concrete")
    evidence_quote: str | None
    evidence_document: str | None = Field(description="File name the evidence comes from")


class JudgeResult(BaseModel):
    verdicts: list[VerdictOut]


class RecommendationOut(BaseModel):
    requirement_code: str
    problem: str = Field(description="What is wrong, concretely")
    action: str = Field(description="Concrete action that fixes it, never a falsification")
    action_type: Literal[
        "add_document", "fix_data", "replace_product", "request_clarification", "unfixable"
    ]


class ReportResult(BaseModel):
    recommendations: list[RecommendationOut]
    summary: str = Field(description="One-page analytical conclusion in the report language")
