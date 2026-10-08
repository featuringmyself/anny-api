from pydantic import BaseModel, Field


class CaptureRequest(BaseModel):
    brandName: str = Field(..., description="Brand under audit")
    prompt: str = Field(..., description="Buyer prompt to run in an empty ChatGPT thread")
    id: str = Field(
        default="",
        description="Optional prompt id for client-side correlation",
    )


class CaptureResponse(BaseModel):
    id: str = Field(default="", description="Echo of request id when provided")
    prompt: str = Field(..., description="Prompt that was captured")
    answerText: str = Field(
        default="",
        description="Extracted assistant answer text (empty on capture failure)",
    )
    screenshotPath: str = Field(
        default="",
        description="PNG evidence path (empty on capture failure)",
    )
    captureError: str | None = Field(
        default=None,
        description="Set when capture failed after retry; answerText will be empty",
    )
