from pydantic import BaseModel, Field

from app.schemas.get_questions import GetQuestionsResponse
from app.schemas.report import (
    BrandCrisisReportItem,
    PromptAuditItem,
    VisibilityReport,
)
from app.services.analyze_answer import AnswerAnalysis


class SynthesizeRequest(BaseModel):
    brandName: str = Field(..., description="Brand under audit")
    questions: GetQuestionsResponse = Field(
        ...,
        description="Output of get_questions (profile + crisis/discovery prompts)",
    )
    crisisRows: list[BrandCrisisReportItem] = Field(
        default_factory=list,
        description="Crisis exhibit rows (exclude status=error for client display)",
    )
    promptRows: list[PromptAuditItem] = Field(
        default_factory=list,
        description="Discovery exhibit rows (exclude status=error for client display)",
    )
    crisisAnalyses: list[AnswerAnalysis] = Field(
        default_factory=list,
        description="All crisis analyses including errors (errors excluded from metrics)",
    )
    promptAnalyses: list[AnswerAnalysis] = Field(
        default_factory=list,
        description="All discovery analyses including errors (errors excluded from metrics)",
    )


class SynthesizeResponse(VisibilityReport):
    """Full visibility report assembled from grounded metrics + narrative synthesis."""
