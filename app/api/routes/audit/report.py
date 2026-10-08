from fastapi import APIRouter, HTTPException, status

from app.schemas.get_questions import GetQuestionsRequest
from app.schemas.report import ReportRequest, VisibilityReport
from app.services.analyze_answer import AnswerAnalysis, BatchAnalyzeError, batch_analyze_all
from app.services.capture_answer import try_capture
from app.services.get_questions import fetch_questions
from app.services.synthesize_report import synthesize_report

router = APIRouter(prefix="/report", tags=["report"])


def _row_from_analysis(
    *,
    item_id: str,
    prompt: str,
    analysis: AnswerAnalysis,
    screenshot_path: str,
    fallback_title: str = "",
    fallback_tag: str = "",
    fallback_outcome: str = "",
    archetype: str = "",
    severity: str = "",
    include_discovery_meta: bool = False,
) -> dict:
    row = {
        "id": item_id,
        "prompt": prompt,
        "status": analysis.status,
        "statusLabel": analysis.statusLabel or analysis.outcome or analysis.tag,
        "screenshotPath": screenshot_path,
        "excerpt": analysis.excerpt,
        "title": analysis.title or fallback_title,
        "outcome": analysis.outcome or analysis.statusLabel or fallback_outcome,
        "tag": analysis.tag or analysis.statusLabel or fallback_tag,
        "citedInstead": analysis.citedInstead,
        "dealLoss": analysis.dealLoss,
    }
    if include_discovery_meta:
        row["archetype"] = archetype
        row["severity"] = severity
    return row


def _capture_error_analysis(item_id: str, detail: str) -> AnswerAnalysis:
    return AnswerAnalysis(
        id=item_id,
        brandCited=False,
        status="error",
        statusLabel="Capture failed",
        excerpt="",
        title="Capture failed",
        outcome=detail,
        tag="Error",
        dealLoss="",
    )


@router.post(
    "/",
    response_model=VisibilityReport,
    status_code=status.HTTP_200_OK,
    summary="Generate brand AI visibility report",
    description=(
        "Convenience orchestrator that chains get_questions → capture → analyze → "
        "synthesize. Prefer the individual /audits/* endpoints when you need to "
        "run or retry each step separately."
    ),
)
async def generate_report(request: ReportRequest) -> VisibilityReport:
    brand_name = request.brandName
    questions = await fetch_questions(GetQuestionsRequest(brandName=brand_name))
    profile = questions.reconstructedProfile

    capture_items: list[dict] = []

    async def _capture_one(
        *,
        item_id: str,
        kind: str,
        query: str,
        fallback_title: str,
        fallback_tag: str,
        fallback_outcome: str,
        archetype: str = "",
        severity: str = "",
    ) -> None:
        result = await try_capture(brand_name, query)
        capture_items.append(
            {
                "id": item_id,
                "kind": kind,
                "query": query,
                "answer_text": result["answer_text"],
                "screenshot_path": result["screenshot_path"],
                "fallback_title": fallback_title,
                "fallback_tag": fallback_tag,
                "fallback_outcome": fallback_outcome,
                "archetype": archetype,
                "severity": severity,
                "capture_error": result["capture_error"],
            }
        )

    for item in questions.brandCrisis:
        await _capture_one(
            item_id=item.id,
            kind="crisis",
            query=item.query,
            fallback_title=item.title,
            fallback_tag=item.tag,
            fallback_outcome=item.outcome,
        )

    for item in questions.queries:
        await _capture_one(
            item_id=item.id,
            kind="discovery",
            query=item.query,
            fallback_title=item.tag,
            fallback_tag=item.tag,
            fallback_outcome=item.outcome,
            archetype=item.archetype,
            severity=item.severity,
        )

    analyze_payload = [
        {
            "id": c["id"],
            "kind": c["kind"],
            "query": c["query"],
            "answer_text": c["answer_text"],
        }
        for c in capture_items
        if not c.get("capture_error")
    ]

    analyses_by_id: dict[str, AnswerAnalysis] = {}
    if analyze_payload:
        try:
            analyses = await batch_analyze_all(
                brand_name=brand_name,
                profile=profile,
                items=analyze_payload,
            )
        except BatchAnalyzeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        analyses_by_id = {a.id: a for a in analyses}

    crisis_rows: list[dict] = []
    prompt_rows: list[dict] = []
    crisis_analyses: list[AnswerAnalysis] = []
    prompt_analyses: list[AnswerAnalysis] = []

    for capture in capture_items:
        if capture.get("capture_error"):
            analysis = _capture_error_analysis(
                capture["id"], capture["capture_error"]
            )
        else:
            analysis = analyses_by_id.get(capture["id"]) or _capture_error_analysis(
                capture["id"], "Per-id analysis missing from batch response"
            )

        # Metrics use all non-error analyses; client-facing arrays omit errors later.
        if capture["kind"] == "crisis":
            crisis_analyses.append(analysis)
            if analysis.status != "error":
                crisis_rows.append(
                    _row_from_analysis(
                        item_id=capture["id"],
                        prompt=capture["query"],
                        analysis=analysis,
                        screenshot_path=capture["screenshot_path"],
                        fallback_title=capture["fallback_title"],
                        fallback_tag=capture["fallback_tag"],
                        fallback_outcome=capture["fallback_outcome"],
                    )
                )
        else:
            prompt_analyses.append(analysis)
            if analysis.status != "error":
                prompt_rows.append(
                    _row_from_analysis(
                        item_id=capture["id"],
                        prompt=capture["query"],
                        analysis=analysis,
                        screenshot_path=capture["screenshot_path"],
                        fallback_title=capture["fallback_title"],
                        fallback_tag=capture["fallback_tag"],
                        fallback_outcome=capture["fallback_outcome"],
                        archetype=capture.get("archetype", ""),
                        severity=capture.get("severity", ""),
                        include_discovery_meta=True,
                    )
                )

    return await synthesize_report(
        brand_name=brand_name,
        questions=questions,
        crisis_rows=crisis_rows,
        prompt_rows=prompt_rows,
        crisis_analyses=crisis_analyses,
        prompt_analyses=prompt_analyses,
    )
