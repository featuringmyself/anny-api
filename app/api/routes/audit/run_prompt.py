from app.engine import query_chatgpt
from app.schemas.chatgpt import ChatGPTQueryRequest, ReturnType
from app.schemas.run_prompt import RunPromptRequest, RunPromptResponse
from fastapi import APIRouter, status

router = APIRouter(prefix="/run_prompt", tags=["run_prompt"])


@router.post("/", response_model=RunPromptResponse, status_code=status.HTTP_200_OK, summary="Run a prompt", description="Runs a prompt and returns the screenshot path")
async def run_prompt(request: RunPromptRequest) -> RunPromptResponse:
    response = await query_chatgpt(ChatGPTQueryRequest(question=request.prompt, returnType=ReturnType.screenshot, brandName=request.brandName))
    return RunPromptResponse(screenshot_path=response.content)