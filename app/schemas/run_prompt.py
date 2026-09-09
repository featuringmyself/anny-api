from pydantic import BaseModel

class RunPromptRequest(BaseModel):
    brandName: str
    prompt: str

class RunPromptResponse(BaseModel):
    screenshot_path: str