from fastapi import APIRouter
from app.engine import query_chatgpt

router = APIRouter(prefix="/llms/chatgpt", tags=["llms/chatgpt"])

@router.post("/query")
async def query_chatgpt_route(question: str):
    html = await query_chatgpt(question)
    return {"html": html}