from pydantic import BaseModel, HttpUrl, Field


class VisibilityCheckRequest(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="Target website URL to check for visibility",
        examples=["https://example.com"],
    )


class VisibilityCheckResponse(BaseModel):
    url: str = Field(..., description="The checked website URL")
    visibility: str = Field(..., description="Visibility assessment status")
