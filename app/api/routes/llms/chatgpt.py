from fastapi import APIRouter, HTTPException, status
from app.engine import query_chatgpt
from app.schemas.chatgpt import ChatGPTQueryRequest, ChatGPTQueryResponse

router = APIRouter(prefix="/llms/chatgpt", tags=["llms/chatgpt"])


@router.post(
    "/",
    response_model=ChatGPTQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query ChatGPT via headless automation",
    description="Automates a browser session to query ChatGPT with the provided prompt and returns the output HTML.",
)
async def query_chatgpt_route(payload: ChatGPTQueryRequest) -> ChatGPTQueryResponse:
    try:
        return await query_chatgpt(payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
