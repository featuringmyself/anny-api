from fastapi import APIRouter, HTTPException, status

from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analyze_answer import BatchAnalyzeError, batch_analyze_all

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post(
    "/",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze captured ChatGPT answers",
    description=(
        "One batched ChatGPT call that scores each captured answer for brand "
        "citation status, competitors named instead, excerpts, and deal-loss lines."
    ),
)
async def analyze_answers(request: AnalyzeRequest) -> AnalyzeResponse:
    items = [
        {
            "id": item.id,
            "kind": item.kind,
            "query": item.query,
            "answer_text": item.answerText,
        }
        for item in request.items
    ]
    try:
        analyses = await batch_analyze_all(
            brand_name=request.brandName,
            profile=request.profile,
            items=items,
        )
    except BatchAnalyzeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return AnalyzeResponse(analyses=analyses)
