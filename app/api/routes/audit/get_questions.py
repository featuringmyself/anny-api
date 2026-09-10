from fastapi import APIRouter, status

from app.schemas.get_questions import GetQuestionsRequest, GetQuestionsResponse
from app.services.get_questions import fetch_questions

router = APIRouter(prefix="/get_questions", tags=["get_questions"])


@router.post(
    "/",
    response_model=GetQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get visibility distress audit questions and reconstructed profile",
    description="Reverse-engineers the brand profile and generates visibility distress prompts across brand crisis and discovery archetypes.",
)
async def get_questions(request: GetQuestionsRequest) -> GetQuestionsResponse:
    return await fetch_questions(request)
