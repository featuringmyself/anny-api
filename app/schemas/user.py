from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str


class UserCreateResponse(BaseModel):
    id: int
    name: str
    email: str