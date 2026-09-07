from fastapi import APIRouter
from fastapi import Request

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(Request: Request):
    return {"message": "Register"}