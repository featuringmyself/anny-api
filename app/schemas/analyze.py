from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.get_questions import ReconstructedProfile
from app.services.analyze_answer import AnswerAnalysis


class AnalyzeItem(BaseModel):
    id: str = Field(..., description="Prompt id")
    kind: Literal["crisis", "discovery"] = Field(
        ..., description="Whether this is a crisis or discovery exhibit"
    )
    query: str = Field(..., description="The buyer prompt that was asked")
    answerText: str = Field(
        ...,
        description="Captured assistant answer text to analyze",
    )


class AnalyzeRequest(BaseModel):
    brandName: str = Field(..., description="Brand under audit")
    profile: ReconstructedProfile = Field(
        ..., description="Reconstructed brand profile from get_questions"
    )
    items: list[AnalyzeItem] = Field(
        ...,
        description="Captured answers to analyze (one object per prompt id)",
    )


class AnalyzeResponse(BaseModel):
    analyses: list[AnswerAnalysis] = Field(
        default_factory=list,
        description="One analysis per input id (missing ids become status=error)",
    )
