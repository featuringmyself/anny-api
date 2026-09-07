from pydantic import BaseModel, Field


class ChatGPTQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Prompt or question to query ChatGPT with",
        examples=["What is the capital of France?"],
    )


class ChatGPTQueryResponse(BaseModel):
    html: str = Field(..., description="Rendered HTML content returned by ChatGPT")
