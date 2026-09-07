from fastapi import APIRouter, status
from app.engine import query_chatgpt
from app.schemas.chatgpt import ChatGPTQueryRequest, ChatGPTQueryResponse

router = APIRouter(prefix="/llms/chatgpt", tags=["llms/chatgpt"])


@router.post(
    "/query",
    response_model=ChatGPTQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query ChatGPT via headless automation",
    description="Automates a browser session to query ChatGPT with the provided prompt and returns the output HTML.",
)
async def query_chatgpt_route(payload: ChatGPTQueryRequest) -> ChatGPTQueryResponse:
    html = await query_chatgpt(payload.question)
    return ChatGPTQueryResponse(html=html)
