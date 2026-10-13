"""Bid package vs approved checklist: facts, matching, score, recommendations (TZ §5-§8)."""

import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app import llm
from app.models import Document, Fact, Match, Project, Recommendation, Requirement, Run
from app.pipeline import quotes, rules, scoring
from app.pipeline.extract import _document_content
from app.schemas.llm import BidDocResult, JudgeResult, ReportResult, SummaryResult, VerdictOut

log = logging.getLogger(__name__)

PARALLEL_DOCUMENTS = 4
JUDGE_BATCH = 30
SOURCE_QUOTE_CHARS = 400

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
# Terms the bidder sets itself (delivery time, payment, validity) are proven by its own forms.
SELF_DECLARED = {"tech_proposal", "commercial_proposal"}
# A whole bid scanned or merged into one PDF: shown instead of a single document type.
BID_PACKAGE = "bid_package"

FACTS_SYSTEM = """You check one file from a bidder's package against the approved checklist \
of a tender. A file is often the whole bid merged into one PDF: cover letter, forms, \
certificates, tax and bankruptcy statements, licenses, registration extracts, contracts, \
invoices, recommendation letters, staff records. Read every page, including scanned pages \
and screenshots.
1. Split the file into sections, one per separate document, with its page range, type and \
requisites (number, date, expiry, issuer, signature, seal). Judge the type by content: a state \
portal statement (my.soliq.uz, my.gov.uz, repo.gov.uz) is a certificate; a notification \
receipt (тасдиқнома, xabarnoma) is not a license unless it says it grants a license for the \
required activity.
2. For every checklist requirement this file addresses, report the actual value written in it \
with a verbatim quote and page. Never infer values that are not written; skip requirements \
the file does not address. For countable requirements (contracts, letters, staff) report each \
item separately with its own value (contract amount, date).
3. List contradictions inside the bidder's own documents, in {language}.
Documents may be in Uzbek, Russian, English, Chinese or other languages; match by meaning \
(a Russian requirement can be confirmed by an English or Chinese datasheet)."""

JUDGE_SYSTEM = """You decide whether a bid complies with tender requirements. For each \
requirement you get its source text in the tender documentation and the facts found in the \
bid. The bid documents list shows every separate document, including documents inside one \
merged PDF, with pages and type: a statement, certificate, license, contract, invoice or \
letter inside the bid file IS a confirming document. Statuses:
- match: the value satisfies the requirement and is confirmed by a suitable document
- partial: only part of the condition is met (2 of 3 certificates) or the confirming document \
expired before the bid submission deadline ({deadline})
- unconfirmed: only the bidder's own statement, no confirming document of the required kind; \
check the kind: a notification for work with precious metals is not a waste-handling license
- mismatch: the value violates the requirement, or the item is missing from the bid
- review: you are not certain, or an expert judgement is needed ("or equivalent" products)
- na: the requirement does not apply to this procurement or is not checked in the bid \
documents: goods-only documents (manufacturer authorization, product brochures and \
passports) when the subject is a service or works; a security of 0%; the bid price when it \
is entered in the e-procurement system's price field rather than in the documents
Offering more than required is not a mismatch. For rated requirements set awarded_points on \
the official scale from the source text (tiers count: the largest single contract of 150 mln \
in a "more than 500 mln - 3, 300-500 mln - 2, less than 300 mln - 1" scale earns 1). When a \
line says "code comparison", the status is already decided: only give awarded_points. Write \
reasoning in {language}: concrete, 1-2 sentences, with the values and pages compared."""

RECOMMEND_SYSTEM = """You are a tender consultant. For every problem in the compliance check \
write a concrete recommendation. action_type is one of add_document, fix_data, \
replace_product, request_clarification, unfixable. Never suggest falsifying facts: if the \
product or the bidder does not meet a requirement, recommend replacing the model, getting the \
real document or asking the customer for clarification, not "fixing the number". fix_data is \
only for inconsistencies between the bidder's own documents. Use unfixable when the bidder \
cannot obtain what is missing before the deadline. Write everything in {language}."""

SUMMARY_SYSTEM = """You are a tender consultant writing a one-page analytical conclusion of \
a compliance check. Structure: one-sentence result with the verdict, percentage and number of \
critical problems; whether the evaluation points reach the passing score (when given) and \
what limits them; critical non-compliances (lead to rejection) first; issues that lower \
evaluation points; risks (expiring documents, contradictions in the bid, ambiguities in the \
tender documentation, items for manual review); strengths; action plan ordered by impact. Use \
exactly the numbers given to you, never compute your own. Requirements marked "not \
applicable" are not problems. Write everything in {language}."""

VERDICT_LABELS = {
    "ru": {"ready": "Готова к подаче", "needs_work": "Требует доработки",
           "rejection_risk": "Риск отклонения"},
    "uz": {"ready": "Topshirishga tayyor", "needs_work": "Qayta ishlash kerak",
           "rejection_risk": "Rad etilish xavfi"},
    "en": {"ready": "Ready to submit", "needs_work": "Needs work",
           "rejection_risk": "Rejection risk"},
}  # fmt: skip

_PASS_WORDS = re.compile(r"o.?tish|проходн|pass|минимал|minim", re.IGNORECASE)


def _requirement_line(req: Requirement) -> str:
    condition = " ".join(x for x in (req.operator, req.value or "", req.unit or "") if x)
    proof = ", ".join(req.proof_documents) or "-"
    pos = f"pos {req.lot_position}" if req.lot_position else "all positions"
    points = f" (max {req.rated_points:g} points)" if req.rated_points else ""
    return (
        f"{req.code} | {pos} | {req.parameter} | {condition} | {req.req_type}{points} | "
        f"proof: {proof}"
    )


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
    system = FACTS_SYSTEM.format(language=llm.LANGUAGES[project.report_language])
    results = []
    for first_page, block in _document_content(doc):
        where = (
            "Page numbers are counted within the attached document."
            if first_page == 1
            else f"This is the part starting at page {first_page} of the file; page numbers "
            "are counted within the attached part."
        )
        prompt = (
            f"File: {doc.filename} ({doc.page_count} pages). {where}\n\n"
            f"Lot positions:\n{positions or '-'}\n\nChecklist:\n{checklist}"
        )
        result = llm.ask(
            BidDocResult,
            system=system,
            content=[block, llm.text_block(prompt)],
            metadata={"route": "bid.extract", "project": project.id, "document": doc.id},
        )
        results.append((first_page, result))
    return results


# ---------------------------------------------------------------- document sections


def _clamp(page: int, doc: Document) -> int:
    return max(1, min(page, doc.page_count or page))


def _sections(doc: Document, first_page: int, result: BidDocResult) -> list[dict[str, Any]]:
    """Sections with page numbers counted in the whole file."""
    sections = []
    for section in result.sections:
        data = section.model_dump()
        data["first_page"] = _clamp(section.first_page + first_page - 1, doc)
        data["last_page"] = _clamp(max(section.last_page, section.first_page) + first_page - 1, doc)
        sections.append(data)
    if not sections:
        last = doc.page_count or first_page
        sections.append({"doc_type": result.doc_type, "first_page": first_page, "last_page": last})
    return sections


def _section_at(sections: list[dict[str, Any]], page: int | None) -> dict[str, Any] | None:
    if page is None:
        return None
    inside = [s for s in sections if s["first_page"] <= page <= s["last_page"]]
    # Nested or overlapping ranges: the narrowest section is the specific document.
    return min(inside, key=lambda s: s["last_page"] - s["first_page"], default=None)


def _apply_doc_results(doc: Document, results: list[tuple[int, BidDocResult]]) -> None:
    """Document type and requisites from all parts of a (possibly split) file."""
    main = results[0][1]
    sections = [s for first, result in results for s in _sections(doc, first, result)]
    types = {s["doc_type"] for s in sections}
    doc.doc_type = main.doc_type if len(types) <= 1 else BID_PACKAGE
    doc.info = main.model_dump(exclude={"facts", "sections", "inconsistencies"}) | {
        "sections": sections,
        "inconsistencies": [text for _, result in results for text in result.inconsistencies],
    }


def _doc_sections(doc: Document) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = doc.info.get("sections") or []
    if sections:
        return sections
    return [{**doc.info, "doc_type": doc.doc_type, "first_page": 1, "last_page": doc.page_count}]


def _expired(info: dict[str, Any], deadline: date | None) -> bool:
    valid_until = _parse_date(info.get("valid_until"))
    return bool(deadline and valid_until and valid_until < deadline)


def _section_line(doc: Document, section: dict[str, Any], deadline: date | None) -> str:
    pages = f"p.{section['first_page']}"
    if section["last_page"] != section["first_page"]:
        pages += f"-{section['last_page']}"
    parts = [f'"{doc.filename}" {pages}', section.get("doc_type") or "other"]
    for key in ("title", "issuer", "doc_number", "doc_date"):
        if section.get(key):
            parts.append(str(section[key]))
    if section.get("valid_until"):
        expired = " (EXPIRED at deadline)" if _expired(section, deadline) else ""
        parts.append(f"valid until {section['valid_until']}{expired}")
    if section.get("has_signature") is False:
        parts.append("no signature")
    if section.get("has_seal") is False:
        parts.append("no seal")
    return ", ".join(parts)


# ---------------------------------------------------------------- matching


def _confirms(req: Requirement, fact: Fact) -> bool:
    doc_type = fact.doc_type or fact.document.doc_type
    if fact.source_rank == 3 or doc_type in req.proof_documents:
        return True
    return set(req.proof_documents) <= SELF_DECLARED and doc_type in SELF_DECLARED


def _fact_expired(fact: Fact, deadline: date | None) -> bool:
    section = _section_at(_doc_sections(fact.document), fact.page)
    return _expired(section or fact.document.info, deadline)


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
    confirmed = [f for f in facts if _confirms(req, f)]
    if req.proof_documents and not confirmed:
        status, why = "unconfirmed", f"{result.detail}; нет подтверждающего документа"
    elif confirmed and all(_fact_expired(f, deadline) for f in confirmed):
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
        "doc_type": fact.doc_type or fact.document.doc_type,
        "page": fact.page,
        "value": _with_unit(fact.value, fact.unit),
        "quote": fact.quote,
        "verified": fact.verified,
    }


def _source_text(req: Requirement) -> str:
    quote = " … ".join(s["quote"] for s in req.sources if s.get("quote"))
    quote = " ".join(quote.split())
    if len(quote) > SOURCE_QUOTE_CHARS:
        quote = quote[:SOURCE_QUOTE_CHARS] + "…"
    return quote


def _judge(project: Project, run: Run, reqs: list[Requirement], facts: dict[int, list[Fact]],
           docs: list[Document], decided: dict[int, Match]) -> dict[str, VerdictOut]:  # fmt: skip
    deadline = project.submission_deadline
    system = JUDGE_SYSTEM.format(
        deadline=deadline.isoformat() if deadline else "unknown",
        language=llm.LANGUAGES[project.report_language],
    )
    doc_list = "\n".join(
        f"- {_section_line(d, s, deadline)}" for d in docs for s in _doc_sections(d)
    )
    verdicts: dict[str, VerdictOut] = {}
    for start in range(0, len(reqs), JUDGE_BATCH):
        lines = []
        for req in reqs[start : start + JUDGE_BATCH]:
            lines.append(f"[{_requirement_line(req)}] equivalent allowed: {req.equivalent_allowed}")
            if source := _source_text(req):
                lines.append(f'  source: "{source}"')
            if req.id in decided:
                match = decided[req.id]
                lines.append(f"  code comparison: {match.reasoning} -> {match.status} (final)")
            found = facts.get(req.id, [])
            if not found:
                lines.append("  facts: none found in the bid")
            for f in found:
                lines.append(
                    f'  - "{f.document.filename}" ({f.doc_type or f.document.doc_type}) '
                    f'p.{f.page}: value "{f.value or ""} {f.unit or ""}" quote: "{f.quote or ""}"'
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


# ---------------------------------------------------------------- scoring


def _pass_requirement(project: Project, reqs: list[Requirement]) -> tuple[float | None, int | None]:
    """The passing score and the checklist item that states it (decided from points, in code)."""
    candidates = []
    for req in reqs:
        unit = rules.resolve_unit(req.unit, req.value)
        numbers = rules.parse_numbers(req.value)
        if (
            req.operator == "gte"
            and req.req_type == "mandatory"
            and unit
            and unit[0] == "points"
            and numbers
        ):
            candidates.append((req, numbers[0]))
    named = [(r, v) for r, v in candidates if _PASS_WORDS.search(r.parameter)]
    same = [(r, v) for r, v in candidates if v == project.min_pass_score]
    found = (same or named)[:1]
    # The project value is the one the user can correct; the checklist item follows it.
    if project.min_pass_score is not None:
        threshold: float | None = project.min_pass_score
    else:
        threshold = found[0][1] if found else None
    return threshold, found[0][0].id if found else None


def _items(matches: list[Match]) -> list[scoring.Item]:
    return [
        scoring.Item(
            code=m.requirement.code,
            scope=m.requirement.scope,
            category=m.requirement.category,
            req_type=m.requirement.req_type,
            status=m.status,
            rated_points=m.requirement.rated_points,
            points=m.points if m.requirement.req_type == "rated" else None,
        )
        for m in matches
    ]


def score_items(run: Run) -> list[scoring.Item]:
    return _items(run.matches)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


def _decide_pass(match: Match, earned: dict[str, Any]) -> None:
    """The passing-score requirement follows the points range unless a person overrode it."""
    if match.method == "manual":
        return
    status = {True: "match", False: "mismatch", None: "review"}[earned["passed"]]
    match.status = match.ai_status = status
    match.method = "rule"
    sign = {"match": "≥", "mismatch": "<", "review": "?"}[status]
    match.reasoning = (
        f"Баллы заявки {_fmt(earned['min'])}–{_fmt(earned['max'])} из {_fmt(earned['total'])} "
        f"{sign} проходного балла {_fmt(earned['pass'])}"
    )


def rescore(run: Run, project: Project) -> None:
    min_pass, pass_req = _pass_requirement(project, [m.requirement for m in run.matches])
    others = [m for m in run.matches if m.requirement_id != pass_req]
    earned = scoring.points(_items(others), min_pass)
    pass_match = next((m for m in run.matches if m.requirement_id == pass_req), None)
    if pass_match is not None and earned is not None:
        _decide_pass(pass_match, earned)

    items = score_items(run)
    result = scoring.score(items, min_pass)
    fixable = {r.requirement.code for r in run.recommendations if r.action_type != "unfixable"}
    result["forecast"] = scoring.forecast(items, fixable)
    fixed = [replace(i, status="match", points=None) if i.code in fixable else i for i in items]
    after = scoring.points(fixed, min_pass)
    result["points_forecast"] = after["max"] if after else None
    result["verdict_label"] = VERDICT_LABELS[project.report_language][result["verdict"]]
    result["warnings"] = run.score.get("warnings", [])
    for rec in run.recommendations:
        rec.impact = scoring.impact(items, rec.requirement.code)
    run.score = result


def _severity(req: Requirement) -> str:
    return {"mandatory": "high", "rated": "medium"}.get(req.req_type, "low")


def _bid_warnings(docs: list[Document], deadline: date | None) -> list[str]:
    warnings = []
    for doc in docs:
        for section in _doc_sections(doc):
            name = doc.filename
            if len(_doc_sections(doc)) > 1:
                name += f", стр. {section['first_page']}"
            if _expired(section, deadline):
                warnings.append(f"{name}: срок действия истёк до окончания приёма заявок")
            if section.get("has_signature") is False and section.get("doc_type") in SELF_DECLARED:
                warnings.append(f"{name}: нет подписи")
        warnings.extend(f"{doc.filename}: {text}" for text in doc.info.get("inconsistencies", []))
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
        if not results:
            continue
        _apply_doc_results(doc, results)
        sections = _doc_sections(doc)
        for first_page, result in results:
            for found in result.facts:
                req = by_code.get(found.requirement_code)
                if req is None:
                    continue
                hint = found.page + first_page - 1 if found.page else None
                page, verified = quotes.locate(found.quote, doc.page_texts, hint)
                section = _section_at(sections, page)
                doc_type = section["doc_type"] if section else result.doc_type
                fact = Fact(run_id=run.id, requirement_id=req.id, document_id=doc.id,
                            value=found.value, unit=found.unit, page=page, quote=found.quote,
                            verified=verified, doc_type=doc_type,
                            source_rank=_rank(doc_type))  # fmt: skip
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
    # Rated items decided in code still go to the model for points on the official scale.
    to_judge = [r for r in reqs if r.id not in matches or r.req_type == "rated"]
    verdicts = _judge(project, run, to_judge, facts, docs, matches) if to_judge else {}
    for req in to_judge:
        verdict = verdicts.get(req.code)
        if req.id in matches:
            if verdict is not None:
                matches[req.id].points = verdict.awarded_points
            continue
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
        if verdict is not None and req.req_type == "rated":
            matches[req.id].points = verdict.awarded_points
    for match in matches.values():
        match.run_id = run.id
        match.requirement = next(r for r in reqs if r.id == match.requirement_id)
        db.add(match)
    run.matches = list(matches.values())
    run.score = {"warnings": _bid_warnings(docs, deadline)}

    run.stage = "report"
    db.commit()
    rescore(run, project)
    _write_recommendations(project, run)
    rescore(run, project)
    _write_summary(project, run)
    run.status, run.stage, run.finished_at = "done", None, datetime.now()
    db.commit()


# ---------------------------------------------------------------- report


def _problems(run: Run) -> list[Match]:
    return [m for m in run.matches if m.status in ("partial", "unconfirmed", "mismatch")]


def _problem_line(match: Match) -> str:
    req = match.requirement
    points = ""
    if req.rated_points:
        points = f" | points {_fmt(match.points)} of {_fmt(req.rated_points)}"
    return (
        f"[{req.code}] {req.req_type} | {req.parameter} {req.operator} {req.value or ''} "
        f"{req.unit or ''}{points} | status {match.status}: {match.reasoning}"
    )


def _write_recommendations(project: Project, run: Run) -> None:
    problems = _problems(run)
    if not problems:
        return
    prompt = "Problems:\n" + "\n".join(_problem_line(m) for m in problems)
    result = llm.ask(
        ReportResult,
        system=RECOMMEND_SYSTEM.format(language=llm.LANGUAGES[project.report_language]),
        content=[llm.text_block(prompt)],
        effort="medium",
        metadata={"route": "report.plan", "project": project.id, "run": run.id},
    )
    by_code = {m.requirement.code: m for m in problems}
    for rec in result.recommendations:
        match = by_code.pop(rec.requirement_code, None)
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


def _points_line(score: dict[str, Any]) -> str:
    earned = score.get("points")
    if not earned:
        return "Evaluation points: no rated criteria with points."
    line = (
        f"Evaluation points: {_fmt(earned['min'])}–{_fmt(earned['max'])} of "
        f"{_fmt(earned['total'])}; at most {_fmt(score.get('points_forecast'))} if all fixable "
        f"recommendations are done."
    )
    if earned["pass"] is not None:
        outcome = {True: "reached", False: "NOT reachable", None: "undecided"}[earned["passed"]]
        line += f" Passing score {_fmt(earned['pass'])}: {outcome}."
    return line


def _write_summary(project: Project, run: Run) -> None:
    score = run.score
    critical = sum(1 for m in _problems(run) if m.requirement.req_type == "mandatory")
    numbers = (
        f"Verdict: {score['verdict_label']}. Total compliance: {_fmt(score['total'])}% "
        f"(product {_fmt(score['product'])}%, participant {_fmt(score['participant'])}%). "
        f"Mandatory met: {score['mandatory_done']} of {score['mandatory_total']}. "
        f"Critical problems: {critical}. Statuses: {score['counts']}. "
        f"Forecast if all fixable recommendations are done: {_fmt(score['forecast'])}%.\n"
        f"{_points_line(score)}"
    )
    recs = [
        f"[{r.requirement.code}] {r.action_type}: {r.action} (+{r.impact}%)"
        for r in run.recommendations
    ]
    reviews = [f"[{m.requirement.code}] {m.requirement.parameter}: {m.reasoning}"
               for m in run.matches if m.status == "review"]  # fmt: skip
    not_applicable = [f"[{m.requirement.code}] {m.requirement.parameter}"
                      for m in run.matches if m.status == "na"]  # fmt: skip
    prompt = (
        f"{numbers}\n\nWarnings: {'; '.join(score.get('warnings', [])) or '-'}\n\n"
        f"Problems:\n" + ("\n".join(_problem_line(m) for m in _problems(run)) or "none") +
        "\n\nRecommendations:\n" + ("\n".join(recs) or "none") +
        "\n\nNeed human review:\n" + ("\n".join(reviews) or "none") +
        f"\n\nNot applicable: {', '.join(not_applicable) or 'none'}"
    )  # fmt: skip
    result = llm.ask(
        SummaryResult,
        system=SUMMARY_SYSTEM.format(language=llm.LANGUAGES[project.report_language]),
        content=[llm.text_block(prompt)],
        effort="medium",
        metadata={"route": "report.summary", "project": project.id, "run": run.id},
    )
    run.summary = result.summary
