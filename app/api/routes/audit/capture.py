from fastapi import APIRouter, status

from app.schemas.capture import CaptureRequest, CaptureResponse
from app.services.capture_answer import try_capture

router = APIRouter(prefix="/capture", tags=["capture"])


@router.post(
    "/",
    response_model=CaptureResponse,
    status_code=status.HTTP_200_OK,
    summary="Capture one buyer prompt answer",
    description=(
        "Runs a single buyer prompt in an empty ChatGPT thread and returns "
        "extracted answer text plus a PNG evidence path. Retries once on failure."
    ),
)
async def capture_prompt(request: CaptureRequest) -> CaptureResponse:
    result = await try_capture(request.brandName, request.prompt)
    return CaptureResponse(
        id=request.id,
        prompt=request.prompt,
        answerText=result["answer_text"],
        screenshotPath=result["screenshot_path"],
        captureError=result["capture_error"],
    )
