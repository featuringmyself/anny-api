from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class ReturnType(Enum):
    html = "html"
    screenshot = "screenshot"

class ChatGPTQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Prompt or question to query ChatGPT with",
        examples=["What is the capital of France?"],
    )
    returnType: ReturnType = Field(
        ...,
        description="Type of content to return",
        examples=[ReturnType.html, ReturnType.screenshot],
    )
    brandName: Optional[str] = Field(
        description="Name of the brand to query ChatGPT for",
        examples=["apple"],
    )


class ChatGPTQueryResponse(BaseModel):
    content: str = Field(..., description="Rendered HTML content returned by ChatGPT")
