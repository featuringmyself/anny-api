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
        "Runs a single buyer prompt in an empty ChatGPT thread. "
        "returnType=html → answerText + htmlPath; "
        "returnType=png → screenshotPath; "
        "returnType=all (default) → both. Retries once on failure."
    ),
)
async def capture_prompt(request: CaptureRequest) -> CaptureResponse:
    result = await try_capture(
        request.brandName,
        request.prompt,
        return_type=request.returnType,
    )
    return CaptureResponse(
        id=request.id,
        prompt=request.prompt,
        returnType=request.returnType,
        answerText=result["answer_text"],
        htmlPath=result["html_path"],
        screenshotPath=result["screenshot_path"],
        captureError=result["capture_error"],
    )
