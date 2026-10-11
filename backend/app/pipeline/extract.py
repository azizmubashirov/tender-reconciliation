"""Customer documentation -> checklist of atomic requirements (TZ §4)."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import llm
from app.core.storage import get_bytes
from app.models import Document, Issue, Project, Requirement
from app.pipeline import quotes, rules
from app.pipeline.convert import pdf_parts
from app.schemas.llm import CustomerDocResult, ExtractedRequirement

log = logging.getLogger(__name__)

PARALLEL_DOCUMENTS = 4

SYSTEM = """You are a procurement analyst. You read a customer's tender documentation \
(Uzbekistan public and corporate procurement; documents may be in Uzbek Latin or Cyrillic, \
Russian, English or other languages, including scans) and build a checklist of every \
requirement to the goods/works/services and to the bidder.

Rules:
- Atomic: one condition is one requirement ("RAM ≥ 16 GB, SSD ≥ 512 GB" are two).
- Requirements only: skip preambles, quotations of laws and platform instructions.
- Product requirements: name and classifier code, quantity, technical characteristics, \
standards (GOST, O'z DSt, ISO, IEC), country of origin, year of manufacture, certificates, \
packaging and marking, warranty, delivery term and place, installation and training, \
included documentation, "or equivalent".
- Bidder requirements: legal capacity and registration, absence from the unfair suppliers \
register, no tax debt, not bankrupt, licenses and permits, manufacturer or dealer status \
(authorization letter), experience of similar supplies, financial stability, staff, \
facilities, service centre, bid and performance security, bid form requirements \
(signature, seal, language, validity period).
- When the text refers to another section or appendix that is present, use its content.
- req_type: mandatory when non-compliance leads to rejection ("должен", "обязательно", \
"не допускается", "shart", "kerak", "must"); rated when it gives evaluation points; \
desired otherwise ("желательно", "maqsadga muvofiq", "preferably").
- Operator choice: a plain number for a capacity or performance characteristic (memory, \
storage, battery life, speed, resolution, number of ports, warranty) is a MINIMUM, so use gte: \
a bigger offered value still complies. Use eq only for exact values written as exact \
("ровно", "точно", "aynan", "exactly", a tolerance such as ±5%), for physical sizes such as \
screen diagonal, and for names, types and models. lte is for maximums ("не более", \
"kamida emas"), including delivery terms and weight.
- "или аналог" / "or equivalent" / "yoki ekvivalent": set equivalent_allowed to true.
- quote is copied verbatim from the document in its original language.
- Report contradictions inside the documentation (warranty 24 months in the specification \
but 12 in the contract), ambiguities and requirements that may restrict competition as issues.
- Write issue descriptions in {language}."""


def _document_content(doc: Document) -> list[tuple[int, dict[str, Any]]]:
    """(first page, content block) per request; long PDFs are split into parts."""
    if doc.pdf_key:
        pdf = get_bytes(doc.pdf_key)
        return [(first, llm.pdf_block(part, doc.filename)) for first, part in pdf_parts(pdf)]
    return [(1, llm.text_block(doc.text_content or "", doc.filename))]


def extract_document(project: Project, doc: Document) -> list[tuple[int, CustomerDocResult]]:
    system = SYSTEM.format(language=llm.LANGUAGES[project.report_language])
    results = []
    for first_page, block in _document_content(doc):
        note = (
            f"File: {doc.filename}. Page numbers are counted within the attached document."
            if first_page == 1
            else f"File: {doc.filename}, pages starting from {first_page}. "
            "Page numbers are counted within the attached part."
        )
        result = llm.ask(
            CustomerDocResult,
            system=system,
            content=[block, llm.text_block(note)],
            metadata={"route": "req.extract", "project": project.id, "document": doc.id},
        )
        results.append((first_page, result))
    return results


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _source(doc: Document, first_page: int, page: int | None, quote: str | None) -> dict[str, Any]:
    hint = page + first_page - 1 if page else None
    located, verified = quotes.locate(quote, doc.page_texts, hint)
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "page": located,
        "quote": quote,
        "verified": verified,
    }


def _value_signature(req: ExtractedRequirement) -> tuple[Any, ...]:
    numbers = rules.parse_numbers(req.value)
    unit = rules.resolve_unit(req.unit, req.value)
    if numbers:
        factor = unit[1] if unit and unit[0] != "temperature" else 1
        return tuple(round(n * factor, 6) for n in numbers)
    return (quotes.normalize(req.value or ""),)


def _stricter(operator: str, a: ExtractedRequirement, b: ExtractedRequirement) -> bool:
    """True when `b` is stricter than `a` for gte/lte comparisons."""
    va, vb = _value_signature(a), _value_signature(b)
    if not (va and vb and isinstance(va[0], float) and isinstance(vb[0], float)):
        return False
    return vb[0] > va[0] if operator == "gte" else vb[0] < va[0]


def run_extraction(db: Session, project: Project) -> None:
    docs = [
        d
        for p in project.packages
        if p.kind == "customer"
        for d in p.documents
        if d.status == "ready"
    ]
    with ThreadPoolExecutor(PARALLEL_DOCUMENTS) as pool:
        per_doc = list(pool.map(lambda d: (d, extract_document(project, d)), docs))

    # Re-extraction replaces model output but keeps what the user added by hand. Collections are
    # edited through the relationships so the project stays consistent within this session.
    project.requirements[:] = [r for r in project.requirements if r.origin == "user"]
    project.issues.clear()
    db.flush()

    positions: dict[int, dict[str, Any]] = {p["number"]: p for p in project.lot_positions}
    merged: dict[tuple[Any, ...], tuple[ExtractedRequirement, list[dict[str, Any]]]] = {}
    conflicted: set[tuple[Any, ...]] = set()
    issues: list[Issue] = []

    for doc, results in per_doc:
        for first_page, result in results:
            doc.doc_type = result.doc_type
            project.customer_name = project.customer_name or result.customer_name
            project.lot_number = project.lot_number or result.lot_number
            project.submission_deadline = project.submission_deadline or _parse_date(
                result.submission_deadline
            )
            for pos in result.lot_positions:
                positions.setdefault(pos.number, pos.model_dump())
            for found in result.issues:
                issues.append(
                    Issue(
                        project_id=project.id,
                        kind=found.kind,
                        description=found.description,
                        sources=[_source(doc, first_page, found.page, found.quote)],
                    )
                )
            for req in result.requirements:
                source = _source(doc, first_page, req.page, req.quote)
                key: tuple[Any, ...] = (
                    req.scope,
                    req.lot_position,
                    req.parameter_key.lower(),
                    req.operator,
                )
                if key in merged:
                    existing, sources = merged[key]
                    if _value_signature(existing) == _value_signature(req):
                        sources.append(source)
                        continue
                    if req.operator in ("gte", "lte"):
                        # Same numeric parameter with different values: keep the stricter one
                        # and ask the customer (TZ §4.2).
                        issues.append(
                            Issue(
                                project_id=project.id,
                                kind="contradiction",
                                description=(
                                    f"«{existing.parameter}»: {existing.value or ''} "
                                    f"{existing.unit or ''} ≠ {req.value or ''} {req.unit or ''}"
                                ),
                                sources=[sources[0], source],
                            )
                        )
                        conflicted.add(key)
                        if _stricter(req.operator, existing, req):
                            merged[key] = (req, [source, *sources])
                        else:
                            sources.append(source)
                        continue
                    key = (*key, len(merged))  # same parameter, different condition: keep both
                merged[key] = (req, [source])

    project.lot_positions = [positions[n] for n in sorted(positions)]
    keep_user = [r for r in project.requirements if r.origin == "user"]
    counters = {"product": 0, "participant": 0}
    ordered = sorted(merged, key=lambda k: 0 if k[0] == "product" else 1)
    for index, key in enumerate(ordered):
        req, sources = merged[key]
        counters[req.scope] += 1
        prefix = "T" if req.scope == "product" else "U"
        note = req.restrictive_note
        if key in conflicted:
            note = "Противоречие в документации заказчика, см. «Вопросы к заказчику»"
        project.requirements.append(
            Requirement(
                project_id=project.id,
                code=f"{prefix}-{counters[req.scope]:03d}",
                scope=req.scope,
                category=req.category,
                lot_position=req.lot_position,
                parameter=req.parameter,
                parameter_key=req.parameter_key.lower(),
                operator=req.operator,
                value=req.value,
                unit=req.unit,
                req_type=req.req_type,
                rated_points=req.rated_points,
                proof_documents=list(req.proof_documents),
                consequence=req.consequence,
                equivalent_allowed=req.equivalent_allowed,
                note=note,
                sources=sources,
                origin="ai",
                sort_index=index,
            )
        )
    for offset, user_req in enumerate(keep_user):
        user_req.sort_index = len(ordered) + offset
    project.issues.extend(issues)
    project.status = "extracted"
    project.error = None
    db.commit()
    log.info("project %s: %d requirements, %d issues", project.id, len(ordered), len(issues))


def renumber(project: Project) -> None:
    """Stable T-/U- codes in checklist order, assigned when the checklist is approved."""
    counters = {"product": 0, "participant": 0}
    for req in sorted(project.requirements, key=lambda r: (r.scope != "product", r.sort_index)):
        counters[req.scope] += 1
        req.code = f"{'T' if req.scope == 'product' else 'U'}-{counters[req.scope]:03d}"
