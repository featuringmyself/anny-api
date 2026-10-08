from enum import Enum

from pydantic import BaseModel, Field


class CaptureReturnType(str, Enum):
    html = "html"
    png = "png"
    all = "all"


class CaptureRequest(BaseModel):
    brandName: str = Field(..., description="Brand under audit")
    prompt: str = Field(..., description="Buyer prompt to run in an empty ChatGPT thread")
    id: str = Field(
        default="",
        description="Optional prompt id for client-side correlation (from get_questions)",
    )
    returnType: CaptureReturnType = Field(
        default=CaptureReturnType.all,
        description=(
            "Artifacts to return: html (answerText + htmlPath), "
            "png (screenshotPath), or all (both)"
        ),
    )


class CaptureResponse(BaseModel):
    id: str = Field(default="", description="Echo of request id when provided")
    prompt: str = Field(..., description="Prompt that was captured")
    returnType: CaptureReturnType = Field(
        ..., description="Echo of the requested return type"
    )
    answerText: str = Field(
        default="",
        description=(
            "Extracted assistant answer text. Populated for html/all; "
            "empty on capture failure"
        ),
    )
    htmlPath: str = Field(
        default="",
        description="Saved HTML evidence path (html/all only; empty otherwise)",
    )
    screenshotPath: str = Field(
        default="",
        description="PNG evidence path (png/all only; empty otherwise)",
    )
    captureError: str | None = Field(
        default=None,
        description="Set when capture failed after retry; answerText will be empty",
    )
