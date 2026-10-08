from fastapi import APIRouter, status

from app.schemas.synthesize import SynthesizeRequest, SynthesizeResponse
from app.services.synthesize_report import synthesize_report

router = APIRouter(prefix="/synthesize", tags=["synthesize"])


@router.post(
    "/",
    response_model=SynthesizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize visibility report from analyses",
    description=(
        "Computes grounded discovery-only score/SOV in code, then one ChatGPT "
        "call for narrative fields (executive summary, sprint). Returns the full "
        "VisibilityReport payload."
    ),
)
async def synthesize(request: SynthesizeRequest) -> SynthesizeResponse:
    report = await synthesize_report(
        brand_name=request.brandName,
        questions=request.questions,
        crisis_rows=[r.model_dump() for r in request.crisisRows],
        prompt_rows=[r.model_dump() for r in request.promptRows],
        crisis_analyses=request.crisisAnalyses,
        prompt_analyses=request.promptAnalyses,
    )
    return SynthesizeResponse.model_validate(report.model_dump())
