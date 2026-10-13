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

Status = Literal["match", "partial", "unconfirmed", "mismatch", "review", "na"]


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
        description="gte also for a plain capacity/performance number (offering more complies); "
        "range_within: value must lie inside the range; range_covers: the offered "
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
    rated_points: float | None = Field(
        description="Maximum evaluation points of the criterion if the document gives them; "
        "the quote must keep its full scoring scale (tiers such as '>500 mln - 3, 300-500 - 2')"
    )
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
    min_passing_score: float | None = Field(
        description="Minimum qualification/technical score a bid needs to pass, if set"
    )
    lot_positions: list[LotPositionOut]
    requirements: list[ExtractedRequirement]
    issues: list[CustomerIssueOut]


class BidFactOut(BaseModel):
    requirement_code: str
    value: str | None = Field(description="Actual value as written in the document")
    unit: str | None
    page: int | None = Field(description="1-based page number inside this document")
    quote: str = Field(description="Verbatim excerpt that states the value, no translation")


class BidSectionOut(BaseModel):
    first_page: int = Field(description="1-based first page of this document inside the file")
    last_page: int = Field(description="1-based last page of this document inside the file")
    doc_type: BidDocType
    title: str | None
    issuer: str | None = Field(description="Organization or authority that issued it")
    doc_number: str | None
    doc_date: str | None = Field(description="YYYY-MM-DD")
    valid_until: str | None = Field(description="Expiry date, YYYY-MM-DD, if the document has one")
    has_signature: bool | None
    has_seal: bool | None


class BidDocResult(BaseModel):
    # Structured outputs allow at most 16 nullable fields per request (tests/test_llm_schemas.py):
    # requisites live only on sections.
    doc_type: BidDocType = Field(description="Type of the main document of the file")
    participant_name: str | None
    participant_tin: str | None = Field(description="Bidder's TIN (STIR / ИНН) if present")
    sections: list[BidSectionOut] = Field(
        description="Every separate document inside the file, in page order: a bid is often "
        "one PDF with forms, certificates, licenses, contracts, invoices and letters. "
        "A file holding a single document has one section"
    )
    inconsistencies: list[str] = Field(
        description="Contradictions inside the bidder's own documents (different TIN, "
        "registration date, address or director; a document said to be attached but absent; "
        "a document of another kind than claimed). Concrete, with pages"
    )
    facts: list[BidFactOut] = Field(
        description="Only requirements this document actually addresses. For experience, "
        "letters and similar countable items report each contract, invoice or letter separately"
    )


class VerdictOut(BaseModel):
    requirement_code: str
    status: Status
    reasoning: str = Field(description="1-2 sentences in the report language, concrete")
    evidence_quote: str | None
    evidence_document: str | None = Field(description="File name the evidence comes from")
    awarded_points: float | None = Field(
        description="Rated requirements only: points the bid earns on the official scoring "
        "scale given in the requirement's source; null for other requirements"
    )


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


class SummaryResult(BaseModel):
    summary: str = Field(description="One-page analytical conclusion in the report language")
