"""Bid package vs approved checklist: facts, matching, score, recommendations (TZ §5-§8)."""

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app import llm
from app.models import Document, Fact, Match, Project, Recommendation, Requirement, Run
from app.pipeline import quotes, rules, scoring
from app.pipeline.extract import _document_content
from app.schemas.llm import BidDocResult, JudgeResult, ReportResult

log = logging.getLogger(__name__)

PARALLEL_DOCUMENTS = 4
JUDGE_BATCH = 30

# Source priority (TZ §5): official / manufacturer documents > bidder's proposal > marketing.
RANK_3 = {
    "product_passport",
    "manufacturer_catalog",
    "certificate",
    "declaration",
    "license",
    "reference_letter",
    "authorization_letter",
    "experience_contract",
    "acceptance_act",
    "financial_statement",
    "company_registration",
    "bank_guarantee",
}
RANK_1 = {"marketing"}

FACTS_SYSTEM = """You check one document from a bidder's package against the approved \
checklist of a tender. Identify the document type and its requisites (number, date, expiry, \
signature, seal, bidder name and TIN). For every checklist requirement this document \
addresses, report the actual value written in the document with a verbatim quote and page. \
Never infer values that are not written in the document; skip requirements it does not address. \
Documents may be in Uzbek, Russian, English, Chinese or other languages; match by meaning \
(a Russian requirement can be confirmed by an English or Chinese datasheet)."""

JUDGE_SYSTEM = """You decide whether a bid complies with tender requirements. For each \
requirement you get the facts found in the bid documents. Statuses:
- match: the value satisfies the requirement and is confirmed by a suitable document
- partial: only part of the condition is met (2 of 3 certificates) or the confirming document \
expired before the bid submission deadline ({deadline})
- unconfirmed: stated in the bidder's proposal but there is no confirming document
- mismatch: the value violates the requirement, or the item is missing from the bid
- review: you are not certain, or an expert judgement is needed ("or equivalent" products)
Offering more than required is not a mismatch. Write reasoning in {language}: concrete, \
1-2 sentences, with the values compared."""

REPORT_SYSTEM = """You are a tender consultant. For every problem in the compliance check \
write a concrete recommendation, then a one-page analytical conclusion.
Recommendations: action_type is one of add_document, fix_data, replace_product, \
request_clarification, unfixable. Never suggest falsifying facts: if the product does not \
meet a characteristic, recommend replacing the model or asking the customer for \
clarification, not "fixing the number". fix_data is only for inconsistencies between the \
bidder's own documents.
Conclusion structure: one-sentence result with the verdict, percentage and number of \
critical problems; critical non-compliances (lead to rejection) first; issues that lower \
evaluation points; risks (expiring documents, contradictions in the bid, ambiguities in the \
tender documentation); strengths; action plan ordered by impact. Use exactly the numbers \
given to you. Write everything in {language}."""

VERDICT_LABELS = {
    "ru": {"ready": "Готова к подаче", "needs_work": "Требует доработки",
           "rejection_risk": "Риск отклонения"},
    "uz": {"ready": "Topshirishga tayyor", "needs_work": "Qayta ishlash kerak",
           "rejection_risk": "Rad etilish xavfi"},
    "en": {"ready": "Ready to submit", "needs_work": "Needs work",
           "rejection_risk": "Rejection risk"},
}  # fmt: skip


def _requirement_line(req: Requirement) -> str:
    condition = " ".join(x for x in (req.operator, req.value or "", req.unit or "") if x)
    proof = ", ".join(req.proof_documents) or "-"
    pos = f"pos {req.lot_position}" if req.lot_position else "all positions"
    return f"{req.code} | {pos} | {req.parameter} | {condition} | {req.req_type} | proof: {proof}"


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _rank(doc_type: str | None) -> int:
    if doc_type in RANK_3:
        return 3
    if doc_type in RANK_1:
        return 1
    return 2


def extract_facts(
    project: Project, doc: Document, reqs: list[Requirement]
) -> list[tuple[int, BidDocResult]]:
    positions = "\n".join(
        f"{p['number']}. {p['name']} ({p.get('quantity') or ''} {p.get('unit') or ''})"
        for p in project.lot_positions
    )
    checklist = "\n".join(_requirement_line(r) for r in reqs)
    results = []
    for first_page, block in _document_content(doc):
        prompt = (
            f"File: {doc.filename}. Page numbers are counted within the attached document.\n\n"
            f"Lot positions:\n{positions or '-'}\n\nChecklist:\n{checklist}"
        )
        result = llm.ask(
            BidDocResult,
            system=FACTS_SYSTEM,
            content=[block, llm.text_block(prompt)],
            metadata={"route": "bid.extract", "project": project.id, "document": doc.id},
        )
        results.append((first_page, result))
    return results


def _doc_summary(doc: Document, deadline: date | None) -> str:
    info = doc.info
    parts = [f'"{doc.filename}"', doc.doc_type or "other"]
    if info.get("valid_until"):
        expired = " (EXPIRED at deadline)" if _expired(doc, deadline) else ""
        parts.append(f"valid until {info['valid_until']}{expired}")
    if info.get("has_signature") is False:
        parts.append("no signature")
    if info.get("has_seal") is False:
        parts.append("no seal")
    return ", ".join(parts)


def _expired(doc: Document, deadline: date | None) -> bool:
    valid_until = _parse_date(doc.info.get("valid_until"))
    return bool(deadline and valid_until and valid_until < deadline)


def _rule_match(req: Requirement, facts: list[Fact], deadline: date | None) -> Match | None:
    """Numeric requirements are decided in code; returns None when the model has to decide."""
    if req.operator not in rules.NUMERIC_OPERATORS or not facts:
        return None
    best = max(facts, key=lambda f: (f.source_rank, bool(f.verified)))
    result = rules.evaluate(req.operator, req.value, req.unit, best.value, best.unit)
    if result.outcome == "unknown":
        return None
    evidence = [_evidence(f) for f in sorted(facts, key=lambda f: -f.source_rank)]
    if result.outcome == "fail":
        return Match(requirement_id=req.id, status="mismatch", ai_status="mismatch", method="rule",
                     reasoning=result.detail, evidence=evidence)  # fmt: skip
    confirmed = [
        f for f in facts
        if f.source_rank == 3 or (f.document.doc_type in req.proof_documents)
    ]  # fmt: skip
    if req.proof_documents and not confirmed:
        status, why = "unconfirmed", f"{result.detail}; нет подтверждающего документа"
    elif confirmed and all(_expired(f.document, deadline) for f in confirmed):
        status, why = "partial", f"{result.detail}; срок действия документа истёк"
    else:
        status, why = "match", result.detail
    return Match(requirement_id=req.id, status=status, ai_status=status, method="rule",
                 reasoning=why, evidence=evidence)  # fmt: skip


def _with_unit(value: str | None, unit: str | None) -> str:
    value, unit = (value or "").strip(), (unit or "").strip()
    if not unit or unit.lower() in value.lower():
        return value
    return f"{value} {unit}".strip()


def _evidence(fact: Fact) -> dict[str, Any]:
    return {
        "document_id": fact.document_id,
        "filename": fact.document.filename,
        "doc_type": fact.document.doc_type,
        "page": fact.page,
        "value": _with_unit(fact.value, fact.unit),
        "quote": fact.quote,
        "verified": fact.verified,
    }


def _judge(project: Project, run: Run, reqs: list[Requirement], facts: dict[int, list[Fact]],
           docs: list[Document]) -> dict[str, Any]:  # fmt: skip
    deadline = project.submission_deadline
    system = JUDGE_SYSTEM.format(
        deadline=deadline.isoformat() if deadline else "unknown",
        language=llm.LANGUAGES[project.report_language],
    )
    doc_list = "\n".join(f"- {_doc_summary(d, deadline)}" for d in docs)
    verdicts: dict[str, Any] = {}
    for start in range(0, len(reqs), JUDGE_BATCH):
        lines = []
        for req in reqs[start : start + JUDGE_BATCH]:
            lines.append(f"[{_requirement_line(req)}] equivalent allowed: {req.equivalent_allowed}")
            found = facts.get(req.id, [])
            if not found:
                lines.append("  facts: none found in the bid")
            for f in found:
                lines.append(
                    f'  - "{f.document.filename}" ({f.document.doc_type}) p.{f.page}: '
                    f'value "{f.value or ""} {f.unit or ""}" quote: "{f.quote or ""}"'
                )
        prompt = f"Bid documents:\n{doc_list}\n\nRequirements and facts:\n" + "\n".join(lines)
        result = llm.ask(
            JudgeResult,
            system=system,
            content=[llm.text_block(prompt)],
            metadata={"route": "match.judge", "project": project.id, "run": run.id},
        )
        verdicts.update({v.requirement_code: v for v in result.verdicts})
    return verdicts


def score_items(run: Run) -> list[scoring.Item]:
    return [
        scoring.Item(
            code=m.requirement.code,
            scope=m.requirement.scope,
            category=m.requirement.category,
            req_type=m.requirement.req_type,
            status=m.status,
            rated_points=m.requirement.rated_points,
        )
        for m in run.matches
    ]


def rescore(run: Run, language: str) -> None:
    items = score_items(run)
    result = scoring.score(items)
    fixable = {r.requirement.code for r in run.recommendations if r.action_type != "unfixable"}
    result["forecast"] = scoring.forecast(items, fixable)
    result["verdict_label"] = VERDICT_LABELS[language][result["verdict"]]
    result["warnings"] = run.score.get("warnings", [])
    for rec in run.recommendations:
        rec.impact = scoring.impact(items, rec.requirement.code)
    run.score = result


def _severity(req: Requirement) -> str:
    return {"mandatory": "high", "rated": "medium"}.get(req.req_type, "low")


def _bid_warnings(docs: list[Document], deadline: date | None) -> list[str]:
    warnings = []
    for doc in docs:
        if _expired(doc, deadline):
            warnings.append(f"{doc.filename}: срок действия истёк до окончания приёма заявок")
        if doc.info.get("has_signature") is False and doc.doc_type in (
            "tech_proposal",
            "commercial_proposal",
        ):
            warnings.append(f"{doc.filename}: нет подписи")
    tins = {str(d.info["participant_tin"]) for d in docs if d.info.get("participant_tin")}
    names = {str(d.info["participant_name"]) for d in docs if d.info.get("participant_name")}
    if len(tins) > 1:
        warnings.append(f"Разные ИНН участника в документах: {', '.join(sorted(tins))}")
    if names:
        warnings.append(f"Участник: {sorted(names)[0]}")
    return warnings


def run_check(db: Session, run: Run) -> None:
    project = db.get(Project, run.project_id)
    assert project is not None
    reqs = list(project.requirements)
    docs = [d for d in run.package.documents if d.status == "ready"]
    by_code = {r.code: r for r in reqs}
    deadline = project.submission_deadline

    run.status, run.stage = "running", "facts"
    db.commit()
    with ThreadPoolExecutor(PARALLEL_DOCUMENTS) as pool:
        per_doc = list(pool.map(lambda d: (d, extract_facts(project, d, reqs)), docs))

    facts: dict[int, list[Fact]] = defaultdict(list)
    for doc, results in per_doc:
        for first_page, result in results:
            doc.doc_type = result.doc_type
            doc.info = result.model_dump(exclude={"facts"})
            for found in result.facts:
                req = by_code.get(found.requirement_code)
                if req is None:
                    continue
                hint = found.page + first_page - 1 if found.page else None
                page, verified = quotes.locate(found.quote, doc.page_texts, hint)
                fact = Fact(run_id=run.id, requirement_id=req.id, document_id=doc.id,
                            value=found.value, unit=found.unit, page=page, quote=found.quote,
                            verified=verified, source_rank=_rank(result.doc_type))  # fmt: skip
                fact.document = doc
                db.add(fact)
                facts[req.id].append(fact)

    run.stage = "match"
    db.commit()
    matches: dict[int, Match] = {}
    for req in reqs:
        decided = _rule_match(req, facts.get(req.id, []), deadline)
        if decided:
            matches[req.id] = decided
    pending = [r for r in reqs if r.id not in matches]
    verdicts = _judge(project, run, pending, facts, docs) if pending else {}
    for req in pending:
        verdict = verdicts.get(req.code)
        evidence = [_evidence(f) for f in facts.get(req.id, [])]
        if verdict is None:
            status, why = "review", "Модель не вернула решение по этому пункту"
        else:
            status, why = verdict.status, verdict.reasoning
        # The most expensive error is a false "match" on a mandatory requirement (TZ §12):
        # without evidence found in the bid it goes to a human instead.
        if status == "match" and req.req_type == "mandatory" and not evidence:
            status = "review"
        matches[req.id] = Match(requirement_id=req.id, status=status, ai_status=status,
                                method="llm", reasoning=why, evidence=evidence)  # fmt: skip
    for match in matches.values():
        match.run_id = run.id
        match.requirement = next(r for r in reqs if r.id == match.requirement_id)
        db.add(match)
    run.matches = list(matches.values())
    run.score = {"warnings": _bid_warnings(docs, deadline)}

    run.stage = "report"
    db.commit()
    rescore(run, project.report_language)
    _write_report(project, run)
    rescore(run, project.report_language)
    run.status, run.stage, run.finished_at = "done", None, datetime.now()
    db.commit()


def _write_report(project: Project, run: Run) -> None:
    problems = [m for m in run.matches if m.status in ("partial", "unconfirmed", "mismatch")]
    score = run.score
    numbers = (
        f"Verdict: {score['verdict_label']}. Total compliance: {score['total']}% "
        f"(product {score['product']}%, participant {score['participant']}%). "
        f"Mandatory met: {score['mandatory_done']} of {score['mandatory_total']}. "
        f"Statuses: {score['counts']}. Forecast if all recommendations are done: "
        f"{score['forecast']}%."
    )
    lines = [
        f"[{m.requirement.code}] {m.requirement.req_type} | {m.requirement.parameter} "
        f"{m.requirement.operator} {m.requirement.value or ''} {m.requirement.unit or ''} | "
        f"status {m.status}: {m.reasoning}"
        for m in problems
    ]
    reviews = [
        f"[{m.requirement.code}] {m.requirement.parameter}"
        for m in run.matches
        if m.status == "review"
    ]
    prompt = (
        f"{numbers}\n\nWarnings: {'; '.join(score.get('warnings', [])) or '-'}\n\n"
        f"Problems:\n" + ("\n".join(lines) or "none") +
        f"\n\nNeed human review: {', '.join(reviews) or 'none'}"
    )  # fmt: skip
    result = llm.ask(
        ReportResult,
        system=REPORT_SYSTEM.format(language=llm.LANGUAGES[project.report_language]),
        content=[llm.text_block(prompt)],
        effort="medium",
        metadata={"route": "report", "project": project.id, "run": run.id},
    )
    by_code = {m.requirement.code: m for m in problems}
    for rec in result.recommendations:
        match = by_code.get(rec.requirement_code)
        if match is None:
            continue
        action_type = rec.action_type
        # Guard against "fix the number" advice when the value comes from an official document.
        official = any(e.get("doc_type") in RANK_3 for e in match.evidence)
        if action_type == "fix_data" and match.method == "rule" and official:
            action_type = "replace_product"
        run.recommendations.append(
            Recommendation(run_id=run.id, requirement_id=match.requirement_id,
                           problem=rec.problem, action=rec.action, action_type=action_type,
                           severity=_severity(match.requirement), requirement=match.requirement)
        )  # fmt: skip
    run.summary = result.summary
