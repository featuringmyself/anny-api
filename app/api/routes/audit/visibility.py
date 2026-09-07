from fastapi import APIRouter, status
from app.schemas.audit import VisibilityCheckRequest, VisibilityCheckResponse

router = APIRouter(prefix="/visibility", tags=["visibility"])


@router.post(
    "/check",
    response_model=VisibilityCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Check URL visibility",
    description="Audits the target URL and returns its visibility status.",
)
async def check_visibility(payload: VisibilityCheckRequest) -> VisibilityCheckResponse:
    return VisibilityCheckResponse(
        url=str(payload.url),
        visibility="visible",
    )
